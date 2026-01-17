"""
Percorsi Android - Ottimizzatore di Percorsi per Android
Versione: 1.0.0
Autore: Mattia Prosperi
Framework: Kivy + KivyMD
"""

import os
import threading
from math import radians, sin, cos, atan2, sqrt
from datetime import datetime

# Kivy configuration
os.environ['KIVY_LOG_LEVEL'] = 'info'

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform
from kivy.properties import StringProperty, NumericProperty, ListProperty, BooleanProperty

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.progressindicator import MDCircularProgressIndicator, MDLinearProgressIndicator
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogContentContainer, MDDialogButtonContainer
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.divider import MDDivider
from kivymd.uix.navigationbar import MDNavigationBar, MDNavigationItem
from kivymd.uix.appbar import MDTopAppBar, MDTopAppBarTitle, MDActionItems

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ====== CONFIGURAZIONE API ======
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjQwNTQ3OTY0MjI0NjRmMzg4ZTFkNjQ1NTc4MGY4OGZkIiwiaCI6Im11cm11cjY0In0="

# ====== UTILITY FUNCTIONS ======

def haversine(lat1, lon1, lat2, lon2):
    """Calcola distanza in metri tra due coordinate usando formula Haversine"""
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def parse_coordinates(text):
    """Analizza testo e estrae coordinate"""
    coords = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for sep in [',', ';', '\t', ' ']:
            if sep in line:
                parts = line.split(sep)
                if len(parts) >= 2:
                    try:
                        lat = float(parts[0].strip().replace(',', '.'))
                        lon = float(parts[1].strip().replace(',', '.'))
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            coords.append((lat, lon))
                            break
                    except ValueError:
                        continue
    return coords


def centroid(coords):
    """Calcola il centroide di una lista di coordinate"""
    if not coords:
        return (0, 0)
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return (lat, lon)


def nearest_to_point(coords, ref):
    """Trova l'indice della coordinata più vicina a un punto"""
    best_idx, best_dist = 0, float('inf')
    for i, (lat, lon) in enumerate(coords):
        d = haversine(lat, lon, ref[0], ref[1])
        if d < best_dist:
            best_dist, best_idx = d, i
    return best_idx


# ====== CACHE ======
DIST_CACHE = {}

def cache_key(lat1, lon1, lat2, lon2, mode):
    return (round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5), mode)


# ====== API ROUTING ======

def get_ors_distance(lat1, lon1, lat2, lon2, api_key=ORS_API_KEY):
    """Ottiene distanza stradale da OpenRouteService"""
    if not REQUESTS_AVAILABLE:
        return int(haversine(lat1, lon1, lat2, lon2))
    
    key = cache_key(lat1, lon1, lat2, lon2, "ors")
    if key in DIST_CACHE:
        return DIST_CACHE[key]
    
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Authorization": api_key}
        params = {"start": f"{lon1},{lat1}", "end": f"{lon2},{lat2}"}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "features" in data and data["features"]:
            distance = data["features"][0]["properties"]["segments"][0]["distance"]
            DIST_CACHE[key] = int(distance)
            return int(distance)
    except Exception as e:
        print(f"ORS Error: {e}")
    
    dist = int(haversine(lat1, lon1, lat2, lon2))
    DIST_CACHE[key] = dist
    return dist


def get_osrm_distance(lat1, lon1, lat2, lon2):
    """Ottiene distanza stradale da OSRM"""
    if not REQUESTS_AVAILABLE:
        return int(haversine(lat1, lon1, lat2, lon2))
    
    key = cache_key(lat1, lon1, lat2, lon2, "osrm")
    if key in DIST_CACHE:
        return DIST_CACHE[key]
    
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        params = {"overview": "false"}
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == "Ok" and data.get("routes"):
            distance = data["routes"][0]["distance"]
            DIST_CACHE[key] = int(distance)
            return int(distance)
    except Exception as e:
        print(f"OSRM Error: {e}")
    
    dist = int(haversine(lat1, lon1, lat2, lon2))
    DIST_CACHE[key] = dist
    return dist


# ====== MATRICE DISTANZE ======

def build_distance_matrix(coords, mode="haversine", progress_callback=None):
    """Costruisce la matrice delle distanze"""
    n = len(coords)
    matrix = {i: {j: 0 for j in range(n)} for i in range(n)}
    total_ops = n * (n - 1) // 2
    completed = 0
    
    for i in range(n):
        for j in range(i + 1, n):
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[j]
            
            if mode == "haversine":
                dist = int(haversine(lat1, lon1, lat2, lon2))
            elif mode == "osrm":
                dist = get_osrm_distance(lat1, lon1, lat2, lon2)
            elif mode == "ors":
                dist = get_ors_distance(lat1, lon1, lat2, lon2)
            else:
                dist = int(haversine(lat1, lon1, lat2, lon2))
            
            matrix[i][j] = dist
            matrix[j][i] = dist
            completed += 1
            if progress_callback and total_ops > 0:
                progress_callback(completed / total_ops)
    
    return matrix


# ====== ALGORITMO TSP ======

def solve_tsp_nearest_neighbor(matrix, start_idx=0):
    """Risolve TSP con algoritmo Nearest Neighbor"""
    n = len(matrix)
    if n <= 1:
        return list(range(n))
    
    visited = [False] * n
    tour = [start_idx]
    visited[start_idx] = True
    
    for _ in range(n - 1):
        current = tour[-1]
        nearest = None
        nearest_dist = float('inf')
        
        for j in range(n):
            if not visited[j] and matrix[current][j] < nearest_dist:
                nearest = j
                nearest_dist = matrix[current][j]
        
        if nearest is not None:
            tour.append(nearest)
            visited[nearest] = True
    
    return tour


def two_opt_improvement(tour, matrix, max_iterations=1000):
    """Migliora il tour usando l'algoritmo 2-opt"""
    n = len(tour)
    if n < 4:
        return tour
    
    improved = True
    iterations = 0
    
    while improved and iterations < max_iterations:
        improved = False
        iterations += 1
        
        for i in range(n - 2):
            for j in range(i + 2, n):
                if j == n - 1 and i == 0:
                    continue
                
                a, b = tour[i], tour[i + 1]
                c, d = tour[j], tour[(j + 1) % n]
                
                current_dist = matrix[a][b] + matrix[c][d]
                new_dist = matrix[a][c] + matrix[b][d]
                
                if new_dist < current_dist:
                    tour[i + 1:j + 1] = reversed(tour[i + 1:j + 1])
                    improved = True
    
    return tour


def solve_tsp(coords, start_mode="first", start_index=0, closed_loop=False, 
              progress_callback=None, distance_mode="haversine"):
    """Risolve il problema del commesso viaggiatore"""
    n = len(coords)
    if n == 0:
        return [], 0, []
    if n == 1:
        return [0], 0, [0]
    
    if progress_callback:
        progress_callback(0.1)
    
    matrix = build_distance_matrix(
        coords, mode=distance_mode,
        progress_callback=lambda p: progress_callback(0.1 + p * 0.5) if progress_callback else None
    )
    
    if progress_callback:
        progress_callback(0.6)
    
    if start_mode == "centroid":
        start_idx = nearest_to_point(coords, centroid(coords))
    elif start_mode == "index":
        start_idx = max(0, min(start_index, n - 1))
    else:
        start_idx = 0
    
    tour = solve_tsp_nearest_neighbor(matrix, start_idx)
    
    if progress_callback:
        progress_callback(0.8)
    
    tour = two_opt_improvement(tour, matrix)
    
    if progress_callback:
        progress_callback(0.95)
    
    distances = [0]
    for i in range(1, len(tour)):
        distances.append(matrix[tour[i-1]][tour[i]])
    
    if closed_loop and n > 1:
        distances.append(matrix[tour[-1]][tour[0]])
    
    total_distance = sum(distances)
    
    if progress_callback:
        progress_callback(1.0)
    
    return tour, total_distance, distances


# ====== EXPORT ======

def generate_google_maps_link(coords, max_waypoints=10):
    """Genera link Google Maps per navigazione"""
    links = []
    for i in range(0, len(coords), max_waypoints - 1):
        segment = coords[i:i + max_waypoints]
        if len(segment) < 2:
            continue
        waypoints = "/".join([f"{lat},{lon}" for lat, lon in segment])
        link = f"https://www.google.com/maps/dir/{waypoints}"
        links.append(link)
    return links


def export_to_gpx(coords, labels=None):
    """Esporta coordinate in formato GPX"""
    gpx = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gpx version="1.1" creator="PercorsiAndroid">']
    for i, (lat, lon) in enumerate(coords):
        name = labels[i] if labels and i < len(labels) else f"Tappa {i+1}"
        gpx.append(f'  <wpt lat="{lat}" lon="{lon}"><name>{name}</name></wpt>')
    gpx.append('  <trk><name>Percorso</name><trkseg>')
    for lat, lon in coords:
        gpx.append(f'    <trkpt lat="{lat}" lon="{lon}"/>')
    gpx.append('  </trkseg></trk></gpx>')
    return '\n'.join(gpx)


def export_to_kml(coords, labels=None):
    """Esporta coordinate in formato KML"""
    kml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<kml xmlns="http://www.opengis.net/kml/2.2">',
           '<Document><name>Percorso</name>']
    for i, (lat, lon) in enumerate(coords):
        name = labels[i] if labels and i < len(labels) else f"Tappa {i+1}"
        kml.append(f'  <Placemark><name>{name}</name>')
        kml.append(f'    <Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>')
    coords_str = ' '.join([f"{lon},{lat},0" for lat, lon in coords])
    kml.append(f'  <Placemark><name>Traccia</name>')
    kml.append(f'    <LineString><coordinates>{coords_str}</coordinates></LineString></Placemark>')
    kml.append('</Document></kml>')
    return '\n'.join(kml)


def export_to_csv(coords, distances, labels=None):
    """Esporta risultato in CSV"""
    lines = ["Progressione,Latitudine,Longitudine,Etichetta,Distanza_m,Distanza_Cumulata_m"]
    cumulative = 0
    for i, (lat, lon) in enumerate(coords):
        label = labels[i] if labels and i < len(labels) else ""
        dist = distances[i] if i < len(distances) else 0
        cumulative += dist
        lines.append(f"{i+1},{lat},{lon},{label},{dist},{cumulative}")
    return '\n'.join(lines)


# ====== KV LANGUAGE UI ======

KV = '''
#:import get_color_from_hex kivy.utils.get_color_from_hex

<RoundedCard@MDCard>:
    style: "elevated"
    radius: [16, 16, 16, 16]
    padding: "16dp"
    spacing: "8dp"
    md_bg_color: self.theme_cls.surfaceContainerLowColor

MDScreenManager:
    id: screen_manager
    
    MDScreen:
        name: "home"
        md_bg_color: self.theme_cls.surfaceColor
        
        MDBoxLayout:
            orientation: "vertical"
            
            MDTopAppBar:
                MDTopAppBarTitle:
                    text: "Percorsi"
                    pos_hint: {"center_x": 0.5}
            
            MDScrollView:
                do_scroll_x: False
                
                MDBoxLayout:
                    orientation: "vertical"
                    padding: "16dp"
                    spacing: "16dp"
                    adaptive_height: True
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        md_bg_color: get_color_from_hex("#FF1DA0")
                        
                        MDLabel:
                            text: "Ottimizzatore Percorsi"
                            font_style: "Headline"
                            role: "small"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 1
                            halign: "center"
                            adaptive_height: True
                        
                        MDLabel:
                            text: "v1.0 Android - Powered by Mattia Prosperi"
                            font_style: "Body"
                            role: "medium"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 0.8
                            halign: "center"
                            adaptive_height: True
                    
                    RoundedCard:
                        id: status_card
                        orientation: "horizontal"
                        adaptive_height: True
                        spacing: "12dp"
                        
                        MDIcon:
                            id: status_icon
                            icon: "circle"
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex("#2ECC71")
                            pos_hint: {"center_y": 0.5}
                        
                        MDLabel:
                            id: status_label
                            text: "Pronto"
                            font_style: "Title"
                            role: "medium"
                            adaptive_height: True
                            pos_hint: {"center_y": 0.5}
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "12dp"
                        
                        MDLabel:
                            text: "Azioni Rapide"
                            font_style: "Title"
                            role: "large"
                            adaptive_height: True
                        
                        MDDivider:
                        
                        MDButton:
                            style: "filled"
                            on_release: app.go_to_input()
                            MDButtonText:
                                text: "Inserisci Coordinate"
                        
                        MDButton:
                            style: "outlined"
                            on_release: app.go_to_settings()
                            MDButtonText:
                                text: "Impostazioni Routing"
                    
                    RoundedCard:
                        id: stats_card
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "8dp"
                        
                        MDLabel:
                            text: "Ultimo Calcolo"
                            font_style: "Title"
                            role: "medium"
                            adaptive_height: True
                        
                        MDDivider:
                        
                        MDLabel:
                            id: stats_coords
                            text: "Coordinate: -"
                            font_style: "Body"
                            role: "large"
                            adaptive_height: True
                        
                        MDLabel:
                            id: stats_distance
                            text: "Distanza totale: -"
                            font_style: "Body"
                            role: "large"
                            adaptive_height: True
        
        MDNavigationBar:
            on_switch_tabs: app.on_nav_switch(*args)
            
            MDNavigationItem:
                icon: "home"
                text: "Home"
                active: True
            
            MDNavigationItem:
                icon: "map-marker-plus"
                text: "Input"
            
            MDNavigationItem:
                icon: "cog"
                text: "Opzioni"
            
            MDNavigationItem:
                icon: "map"
                text: "Risultati"
    
    MDScreen:
        name: "input"
        md_bg_color: self.theme_cls.surfaceColor
        
        MDBoxLayout:
            orientation: "vertical"
            
            MDTopAppBar:
                MDActionItems:
                    MDIconButton:
                        icon: "arrow-left"
                        on_release: app.go_home()
                MDTopAppBarTitle:
                    text: "Inserisci Coordinate"
            
            MDScrollView:
                do_scroll_x: False
                
                MDBoxLayout:
                    orientation: "vertical"
                    padding: "16dp"
                    spacing: "16dp"
                    adaptive_height: True
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "12dp"
                        
                        MDLabel:
                            text: "Coordinate (lat,lon)"
                            font_style: "Title"
                            role: "medium"
                            adaptive_height: True
                        
                        MDTextField:
                            id: coords_input
                            mode: "outlined"
                            multiline: True
                            size_hint_y: None
                            height: "200dp"
                            MDTextFieldHintText:
                                text: "45.4642,9.1900"
                        
                        MDLabel:
                            text: "Una coordinata per riga"
                            font_style: "Body"
                            role: "small"
                            theme_text_color: "Secondary"
                            adaptive_height: True
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "8dp"
                        
                        MDLabel:
                            text: "Etichette (opzionale)"
                            font_style: "Title"
                            role: "medium"
                            adaptive_height: True
                        
                        MDTextField:
                            id: labels_input
                            mode: "outlined"
                            multiline: True
                            size_hint_y: None
                            height: "100dp"
                            MDTextFieldHintText:
                                text: "Milano"
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "12dp"
                        
                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"
                            
                            MDButton:
                                style: "filled"
                                on_release: app.parse_and_preview()
                                MDButtonText:
                                    text: "Anteprima"
                            
                            MDButton:
                                style: "tonal"
                                on_release: app.clear_input()
                                MDButtonText:
                                    text: "Pulisci"
                            
                            MDButton:
                                style: "outlined"
                                on_release: app.load_example()
                                MDButtonText:
                                    text: "Esempio"
                        
                        MDLabel:
                            id: preview_label
                            text: "Coordinate trovate: 0"
                            font_style: "Body"
                            role: "medium"
                            adaptive_height: True
                    
                    MDButton:
                        style: "filled"
                        size_hint_x: 1
                        on_release: app.start_optimization()
                        md_bg_color: get_color_from_hex("#FF1DA0")
                        MDButtonText:
                            text: "OTTIMIZZA PERCORSO"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 1
    
    MDScreen:
        name: "settings"
        md_bg_color: self.theme_cls.surfaceColor
        
        MDBoxLayout:
            orientation: "vertical"
            
            MDTopAppBar:
                MDActionItems:
                    MDIconButton:
                        icon: "arrow-left"
                        on_release: app.go_home()
                MDTopAppBarTitle:
                    text: "Impostazioni"
            
            MDScrollView:
                do_scroll_x: False
                
                MDBoxLayout:
                    orientation: "vertical"
                    padding: "16dp"
                    spacing: "16dp"
                    adaptive_height: True
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "12dp"
                        
                        MDLabel:
                            text: "Calcolo Distanze"
                            font_style: "Title"
                            role: "large"
                            adaptive_height: True
                        
                        MDDivider:
                        
                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"
                            
                            MDLabel:
                                text: "Modalita:"
                                adaptive_height: True
                                pos_hint: {"center_y": 0.5}
                            
                            MDButton:
                                id: distance_mode_btn
                                style: "outlined"
                                on_release: app.show_distance_menu()
                                MDButtonText:
                                    id: distance_mode_text
                                    text: "Haversine"
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "12dp"
                        
                        MDLabel:
                            text: "Opzioni Percorso"
                            font_style: "Title"
                            role: "large"
                            adaptive_height: True
                        
                        MDDivider:
                        
                        MDBoxLayout:
                            adaptive_height: True
                            
                            MDLabel:
                                text: "Percorso ad anello"
                                adaptive_height: True
                                pos_hint: {"center_y": 0.5}
                            
                            MDSwitch:
                                id: closed_loop_switch
                                pos_hint: {"center_y": 0.5}
                        
                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"
                            
                            MDLabel:
                                text: "Partenza:"
                                adaptive_height: True
                                pos_hint: {"center_y": 0.5}
                            
                            MDButton:
                                id: start_mode_btn
                                style: "outlined"
                                on_release: app.show_start_menu()
                                MDButtonText:
                                    id: start_mode_text
                                    text: "Primo punto"
    
    MDScreen:
        name: "results"
        md_bg_color: self.theme_cls.surfaceColor
        
        MDBoxLayout:
            orientation: "vertical"
            
            MDTopAppBar:
                MDActionItems:
                    MDIconButton:
                        icon: "arrow-left"
                        on_release: app.go_home()
                MDTopAppBarTitle:
                    text: "Risultati"
                MDActionItems:
                    MDIconButton:
                        icon: "share-variant"
                        on_release: app.share_results()
            
            MDScrollView:
                do_scroll_x: False
                
                MDBoxLayout:
                    orientation: "vertical"
                    padding: "16dp"
                    spacing: "16dp"
                    adaptive_height: True
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "8dp"
                        md_bg_color: get_color_from_hex("#2ECC71")
                        
                        MDLabel:
                            text: "Percorso Ottimizzato"
                            font_style: "Headline"
                            role: "small"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 1
                            halign: "center"
                            adaptive_height: True
                        
                        MDLabel:
                            id: result_total_distance
                            text: "Distanza: -"
                            font_style: "Title"
                            role: "large"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 1
                            halign: "center"
                            adaptive_height: True
                        
                        MDLabel:
                            id: result_total_stops
                            text: "Tappe: -"
                            font_style: "Body"
                            role: "large"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 0.9
                            halign: "center"
                            adaptive_height: True
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "8dp"
                        
                        MDLabel:
                            text: "Ordine Tappe"
                            font_style: "Title"
                            role: "large"
                            adaptive_height: True
                        
                        MDDivider:
                        
                        MDBoxLayout:
                            id: stops_list
                            orientation: "vertical"
                            adaptive_height: True
                            spacing: "4dp"
                    
                    RoundedCard:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "12dp"
                        
                        MDLabel:
                            text: "Esporta"
                            font_style: "Title"
                            role: "large"
                            adaptive_height: True
                        
                        MDDivider:
                        
                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"
                            
                            MDButton:
                                style: "filled"
                                on_release: app.open_google_maps()
                                MDButtonText:
                                    text: "Google Maps"
                            
                            MDButton:
                                style: "tonal"
                                on_release: app.export_gpx()
                                MDButtonText:
                                    text: "GPX"
                            
                            MDButton:
                                style: "tonal"
                                on_release: app.export_kml()
                                MDButtonText:
                                    text: "KML"
    
    MDScreen:
        name: "processing"
        md_bg_color: self.theme_cls.surfaceColor
        
        MDBoxLayout:
            orientation: "vertical"
            padding: "32dp"
            spacing: "24dp"
            
            Widget:
            
            MDCircularProgressIndicator:
                size_hint: None, None
                size: "80dp", "80dp"
                pos_hint: {"center_x": 0.5}
            
            MDLabel:
                text: "Ottimizzazione..."
                font_style: "Title"
                role: "large"
                halign: "center"
                adaptive_height: True
            
            MDLinearProgressIndicator:
                id: progress_bar
                value: 0
                size_hint_x: 0.8
                pos_hint: {"center_x": 0.5}
            
            MDLabel:
                id: progress_text
                text: "0%"
                font_style: "Body"
                role: "medium"
                halign: "center"
                adaptive_height: True
            
            Widget:
            
            MDButton:
                style: "text"
                pos_hint: {"center_x": 0.5}
                on_release: app.cancel_optimization()
                MDButtonText:
                    text: "Annulla"
'''


# ====== MAIN APP ======

class PercorsiApp(MDApp):
    
    coords = ListProperty([])
    labels = ListProperty([])
    optimized_coords = ListProperty([])
    optimized_labels = ListProperty([])
    distances = ListProperty([])
    total_distance = NumericProperty(0)
    distance_mode = StringProperty("haversine")
    start_mode = StringProperty("first")
    closed_loop = BooleanProperty(False)
    is_processing = BooleanProperty(False)
    processing_thread = None
    
    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Pink"
        if platform not in ('android', 'ios'):
            Window.size = (400, 700)
        return Builder.load_string(KV)
    
    def on_start(self):
        self.distance_menu = MDDropdownMenu(
            caller=self.root.ids.distance_mode_btn,
            items=[
                {"text": "Haversine", "on_release": lambda x="haversine": self.set_distance_mode(x, "Haversine")},
                {"text": "OSRM", "on_release": lambda x="osrm": self.set_distance_mode(x, "OSRM")},
                {"text": "ORS", "on_release": lambda x="ors": self.set_distance_mode(x, "ORS")},
            ],
        )
        self.start_menu = MDDropdownMenu(
            caller=self.root.ids.start_mode_btn,
            items=[
                {"text": "Primo punto", "on_release": lambda x="first": self.set_start_mode(x, "Primo punto")},
                {"text": "Centroide", "on_release": lambda x="centroid": self.set_start_mode(x, "Centroide")},
            ],
        )
    
    def on_nav_switch(self, bar, item, item_icon, item_text):
        screens = {"Home": "home", "Input": "input", "Opzioni": "settings", "Risultati": "results"}
        if item_text in screens:
            if item_text == "Risultati" and not self.optimized_coords:
                self.show_snackbar("Nessun risultato")
                return
            self.root.current = screens[item_text]
    
    def go_home(self):
        self.root.current = "home"
    
    def go_to_input(self):
        self.root.current = "input"
    
    def go_to_settings(self):
        self.root.current = "settings"
    
    def go_to_results(self):
        if self.optimized_coords:
            self.root.current = "results"
    
    def parse_and_preview(self):
        text = self.root.ids.coords_input.text
        self.coords = parse_coordinates(text)
        labels_text = self.root.ids.labels_input.text
        self.labels = [l.strip() for l in labels_text.split('\n') if l.strip()]
        count = len(self.coords)
        self.root.ids.preview_label.text = f"Coordinate trovate: {count}"
        self.show_snackbar(f"{count} coordinate" if count else "Nessuna coordinata")
    
    def clear_input(self):
        self.root.ids.coords_input.text = ""
        self.root.ids.labels_input.text = ""
        self.root.ids.preview_label.text = "Coordinate trovate: 0"
        self.coords = []
        self.labels = []
    
    def load_example(self):
        self.root.ids.coords_input.text = "45.4642,9.1900\n41.9028,12.4964\n43.7696,11.2558\n44.4949,11.3426\n45.4384,10.9916\n40.8518,14.2681"
        self.root.ids.labels_input.text = "Milano\nRoma\nFirenze\nBologna\nVerona\nNapoli"
        self.parse_and_preview()
    
    def show_distance_menu(self):
        self.distance_menu.open()
    
    def show_start_menu(self):
        self.start_menu.open()
    
    def set_distance_mode(self, mode, text):
        self.distance_mode = mode
        self.root.ids.distance_mode_text.text = text
        self.distance_menu.dismiss()
    
    def set_start_mode(self, mode, text):
        self.start_mode = mode
        self.root.ids.start_mode_text.text = text
        self.start_menu.dismiss()
    
    def start_optimization(self):
        if not self.coords:
            self.parse_and_preview()
        if len(self.coords) < 2:
            self.show_snackbar("Minimo 2 coordinate")
            return
        
        self.closed_loop = self.root.ids.closed_loop_switch.active
        self.root.current = "processing"
        self.is_processing = True
        self.update_status("Elaborazione...", "#F1C40F")
        
        self.processing_thread = threading.Thread(target=self._run_optimization)
        self.processing_thread.daemon = True
        self.processing_thread.start()
    
    def _run_optimization(self):
        try:
            start_time = datetime.now()
            
            def progress_cb(p):
                Clock.schedule_once(lambda dt: self._update_progress(p), 0)
            
            tour, total_dist, distances = solve_tsp(
                self.coords, start_mode=self.start_mode,
                closed_loop=self.closed_loop, progress_callback=progress_cb,
                distance_mode=self.distance_mode
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            opt_coords = [self.coords[i] for i in tour]
            opt_labels = [self.labels[i] if i < len(self.labels) else f"Tappa {i+1}" for i in tour]
            
            Clock.schedule_once(lambda dt: self._optimization_complete(opt_coords, opt_labels, distances, total_dist, elapsed), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self._optimization_error(str(e)), 0)
    
    def _update_progress(self, progress):
        percent = int(progress * 100)
        self.root.ids.progress_bar.value = percent
        self.root.ids.progress_text.text = f"{percent}%"
    
    def _optimization_complete(self, coords, labels, distances, total_dist, elapsed):
        self.is_processing = False
        self.optimized_coords = coords
        self.optimized_labels = labels
        self.distances = distances
        self.total_distance = total_dist
        
        self.root.ids.stats_coords.text = f"Coordinate: {len(coords)}"
        self.root.ids.stats_distance.text = f"Distanza: {self._format_distance(total_dist)}"
        self.root.ids.result_total_distance.text = f"Distanza: {self._format_distance(total_dist)}"
        self.root.ids.result_total_stops.text = f"Tappe: {len(coords)}"
        
        stops_box = self.root.ids.stops_list
        stops_box.clear_widgets()
        
        cumulative = 0
        for i, (coord, label) in enumerate(zip(coords, labels)):
            dist = distances[i] if i < len(distances) else 0
            cumulative += dist
            
            item = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing="8dp", padding=["0dp", "4dp"])
            item.add_widget(MDLabel(text=f"{i+1}. {label}", font_style="Body", role="large", adaptive_height=True))
            item.add_widget(MDLabel(text=self._format_distance(cumulative), font_style="Body", role="small", 
                                   theme_text_color="Secondary", halign="right", size_hint_x=None, width="80dp", adaptive_height=True))
            stops_box.add_widget(item)
        
        self.update_status("Completato", "#2ECC71")
        self.root.current = "results"
        self.show_snackbar("Ottimizzazione completata!")
    
    def _optimization_error(self, error):
        self.is_processing = False
        self.update_status("Errore", "#E74C3C")
        self.root.current = "input"
        self.show_snackbar(f"Errore: {error}")
    
    def cancel_optimization(self):
        self.is_processing = False
        self.update_status("Annullato", "#E67E22")
        self.root.current = "input"
    
    def _format_distance(self, meters):
        return f"{meters/1000:.1f} km" if meters >= 1000 else f"{int(meters)} m"
    
    def open_google_maps(self):
        if not self.optimized_coords:
            return
        links = generate_google_maps_link(self.optimized_coords)
        if links:
            import webbrowser
            webbrowser.open(links[0])
    
    def export_gpx(self):
        if not self.optimized_coords:
            return
        content = export_to_gpx(self.optimized_coords, self.optimized_labels)
        self._save_file(content, "percorso.gpx")
    
    def export_kml(self):
        if not self.optimized_coords:
            return
        content = export_to_kml(self.optimized_coords, self.optimized_labels)
        self._save_file(content, "percorso.kml")
    
    def _save_file(self, content, filename):
        try:
            if platform == 'android':
                from android.storage import primary_external_storage_path
                path = os.path.join(primary_external_storage_path(), 'Download', filename)
            else:
                path = os.path.join(os.path.expanduser('~'), filename)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.show_snackbar(f"Salvato: {filename}")
        except Exception as e:
            self.show_snackbar(f"Errore: {e}")
    
    def share_results(self):
        if not self.optimized_coords:
            return
        text = f"Percorso ({self._format_distance(self.total_distance)}):\n"
        for i, label in enumerate(self.optimized_labels):
            text += f"{i+1}. {label}\n"
        
        if platform == 'android':
            try:
                from jnius import autoclass
                Intent = autoclass('android.content.Intent')
                String = autoclass('java.lang.String')
                intent = Intent(Intent.ACTION_SEND)
                intent.putExtra(Intent.EXTRA_TEXT, String(text))
                intent.setType("text/plain")
                from android import mActivity
                mActivity.startActivity(Intent.createChooser(intent, String("Condividi")))
            except:
                pass
        self.show_snackbar("Condivisione...")
    
    def update_status(self, text, color):
        from kivy.utils import get_color_from_hex
        self.root.ids.status_label.text = text
        self.root.ids.status_icon.text_color = get_color_from_hex(color)
    
    def show_snackbar(self, text):
        MDSnackbar(MDSnackbarText(text=text), y="24dp", pos_hint={"center_x": 0.5}, size_hint_x=0.9).open()


if __name__ == '__main__':
    PercorsiApp().run()
