"""
Percorsi Android - Ottimizzatore di Percorsi
Versione: 1.0.0 (Kivy Puro)
Autore: Mattia Prosperi
"""

import os
import threading
from math import radians, sin, cos, atan2, sqrt
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform
from kivy.properties import StringProperty, NumericProperty, ListProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.uix.checkbox import CheckBox

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# API Key OpenRouteService
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjQwNTQ3OTY0MjI0NjRmMzg4ZTFkNjQ1NTc4MGY4OGZkIiwiaCI6Im11cm11cjY0In0="

# Cache distanze
DIST_CACHE = {}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi/2)**2 + cos(phi1)*cos(phi2)*sin(delta_lambda/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

def parse_coordinates(text):
    coords = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        for sep in [',', ';', '\t', ' ']:
            if sep in line:
                parts = line.split(sep)
                if len(parts) >= 2:
                    try:
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            coords.append((lat, lon))
                            break
                    except:
                        continue
    return coords

def cache_key(lat1, lon1, lat2, lon2, mode):
    return (round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5), mode)

def get_osrm_distance(lat1, lon1, lat2, lon2):
    if not REQUESTS_AVAILABLE:
        return int(haversine(lat1, lon1, lat2, lon2))
    key = cache_key(lat1, lon1, lat2, lon2, "osrm")
    if key in DIST_CACHE:
        return DIST_CACHE[key]
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("code") == "Ok":
            dist = int(data["routes"][0]["distance"])
            DIST_CACHE[key] = dist
            return dist
    except:
        pass
    dist = int(haversine(lat1, lon1, lat2, lon2))
    DIST_CACHE[key] = dist
    return dist

def get_ors_distance(lat1, lon1, lat2, lon2):
    if not REQUESTS_AVAILABLE:
        return int(haversine(lat1, lon1, lat2, lon2))
    key = cache_key(lat1, lon1, lat2, lon2, "ors")
    if key in DIST_CACHE:
        return DIST_CACHE[key]
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Authorization": ORS_API_KEY}
        params = {"start": f"{lon1},{lat1}", "end": f"{lon2},{lat2}"}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        if "features" in data:
            dist = int(data["features"][0]["properties"]["segments"][0]["distance"])
            DIST_CACHE[key] = dist
            return dist
    except:
        pass
    dist = int(haversine(lat1, lon1, lat2, lon2))
    DIST_CACHE[key] = dist
    return dist

def build_matrix(coords, mode="haversine", callback=None):
    n = len(coords)
    matrix = {i: {j: 0 for j in range(n)} for i in range(n)}
    total = n * (n-1) // 2
    done = 0
    for i in range(n):
        for j in range(i+1, n):
            if mode == "osrm":
                d = get_osrm_distance(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            elif mode == "ors":
                d = get_ors_distance(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            else:
                d = int(haversine(coords[i][0], coords[i][1], coords[j][0], coords[j][1]))
            matrix[i][j] = d
            matrix[j][i] = d
            done += 1
            if callback and total > 0:
                callback(done / total)
    return matrix

def nearest_neighbor(matrix, start=0):
    n = len(matrix)
    if n <= 1:
        return list(range(n))
    visited = [False] * n
    tour = [start]
    visited[start] = True
    for _ in range(n-1):
        curr = tour[-1]
        nearest, nearest_d = None, float('inf')
        for j in range(n):
            if not visited[j] and matrix[curr][j] < nearest_d:
                nearest, nearest_d = j, matrix[curr][j]
        if nearest is not None:
            tour.append(nearest)
            visited[nearest] = True
    return tour

def two_opt(tour, matrix, max_iter=500):
    n = len(tour)
    if n < 4:
        return tour
    improved = True
    iters = 0
    while improved and iters < max_iter:
        improved = False
        iters += 1
        for i in range(n-2):
            for j in range(i+2, n):
                if j == n-1 and i == 0:
                    continue
                a, b, c, d = tour[i], tour[i+1], tour[j], tour[(j+1) % n]
                if matrix[a][b] + matrix[c][d] > matrix[a][c] + matrix[b][d]:
                    tour[i+1:j+1] = reversed(tour[i+1:j+1])
                    improved = True
    return tour

def solve_tsp(coords, mode="haversine", callback=None):
    if len(coords) < 2:
        return list(range(len(coords))), 0, [0]*len(coords)
    if callback:
        callback(0.1)
    matrix = build_matrix(coords, mode, lambda p: callback(0.1 + p*0.5) if callback else None)
    if callback:
        callback(0.7)
    tour = nearest_neighbor(matrix, 0)
    tour = two_opt(tour, matrix)
    if callback:
        callback(0.95)
    distances = [0]
    for i in range(1, len(tour)):
        distances.append(matrix[tour[i-1]][tour[i]])
    total = sum(distances)
    if callback:
        callback(1.0)
    return tour, total, distances

def generate_gmaps_link(coords, max_wp=10):
    links = []
    for i in range(0, len(coords), max_wp-1):
        seg = coords[i:i+max_wp]
        if len(seg) < 2:
            continue
        pts = "/".join([f"{lat},{lon}" for lat, lon in seg])
        links.append(f"https://www.google.com/maps/dir/{pts}")
    return links

# UI
KV = '''
ScreenManager:
    HomeScreen:
    InputScreen:
    SettingsScreen:
    ResultsScreen:
    ProcessingScreen:

<HomeScreen>:
    name: 'home'
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 15
        
        Label:
            text: 'PERCORSI'
            font_size: '32sp'
            bold: True
            color: 1, 0.1, 0.4, 1
            size_hint_y: None
            height: 60
        
        Label:
            text: 'Ottimizzatore di Percorsi v1.0'
            font_size: '14sp'
            color: 0.5, 0.5, 0.5, 1
            size_hint_y: None
            height: 30
        
        Widget:
            size_hint_y: 0.1
        
        Button:
            text: 'INSERISCI COORDINATE'
            font_size: '18sp'
            size_hint_y: None
            height: 60
            background_color: 1, 0.1, 0.4, 1
            on_release: app.root.current = 'input'
        
        Button:
            text: 'IMPOSTAZIONI'
            font_size: '18sp'
            size_hint_y: None
            height: 60
            background_color: 0.3, 0.3, 0.3, 1
            on_release: app.root.current = 'settings'
        
        Button:
            text: 'RISULTATI'
            font_size: '18sp'
            size_hint_y: None
            height: 60
            background_color: 0.2, 0.7, 0.3, 1
            on_release: app.show_results()
        
        Widget:
            size_hint_y: 0.3
        
        Label:
            id: stats_label
            text: 'Powered by Mattia Prosperi'
            font_size: '12sp'
            color: 0.5, 0.5, 0.5, 1
            size_hint_y: None
            height: 30

<InputScreen>:
    name: 'input'
    BoxLayout:
        orientation: 'vertical'
        padding: 15
        spacing: 10
        
        BoxLayout:
            size_hint_y: None
            height: 50
            Button:
                text: '< INDIETRO'
                size_hint_x: 0.3
                on_release: app.root.current = 'home'
            Label:
                text: 'Inserisci Coordinate'
                font_size: '18sp'
                bold: True
        
        Label:
            text: 'Coordinate (lat,lon per riga):'
            size_hint_y: None
            height: 30
            halign: 'left'
        
        TextInput:
            id: coords_input
            hint_text: '45.4642,9.1900\\n41.9028,12.4964'
            multiline: True
            size_hint_y: 0.4
        
        Label:
            text: 'Etichette (opzionale):'
            size_hint_y: None
            height: 30
        
        TextInput:
            id: labels_input
            hint_text: 'Milano\\nRoma'
            multiline: True
            size_hint_y: 0.2
        
        BoxLayout:
            size_hint_y: None
            height: 50
            spacing: 10
            Button:
                text: 'ESEMPIO'
                on_release: app.load_example()
            Button:
                text: 'PULISCI'
                on_release: app.clear_input()
        
        Label:
            id: preview_label
            text: 'Coordinate: 0'
            size_hint_y: None
            height: 30
        
        Button:
            text: 'OTTIMIZZA PERCORSO'
            font_size: '18sp'
            size_hint_y: None
            height: 60
            background_color: 1, 0.1, 0.4, 1
            on_release: app.start_optimization()

<SettingsScreen>:
    name: 'settings'
    BoxLayout:
        orientation: 'vertical'
        padding: 15
        spacing: 10
        
        BoxLayout:
            size_hint_y: None
            height: 50
            Button:
                text: '< INDIETRO'
                size_hint_x: 0.3
                on_release: app.root.current = 'home'
            Label:
                text: 'Impostazioni'
                font_size: '18sp'
                bold: True
        
        Label:
            text: 'Modalita calcolo distanze:'
            size_hint_y: None
            height: 40
        
        Spinner:
            id: distance_spinner
            text: 'Haversine (veloce)'
            values: ['Haversine (veloce)', 'OSRM (strade)', 'ORS (preciso)']
            size_hint_y: None
            height: 50
        
        Widget:
            size_hint_y: 0.5
        
        Label:
            text: 'API Key ORS: Preconfigurata'
            size_hint_y: None
            height: 30
            color: 0.5, 0.5, 0.5, 1

<ResultsScreen>:
    name: 'results'
    BoxLayout:
        orientation: 'vertical'
        padding: 15
        spacing: 10
        
        BoxLayout:
            size_hint_y: None
            height: 50
            Button:
                text: '< HOME'
                size_hint_x: 0.3
                on_release: app.root.current = 'home'
            Label:
                text: 'Risultati'
                font_size: '18sp'
                bold: True
        
        Label:
            id: result_summary
            text: 'Distanza totale: -'
            font_size: '20sp'
            bold: True
            color: 0.2, 0.7, 0.3, 1
            size_hint_y: None
            height: 50
        
        ScrollView:
            size_hint_y: 0.6
            Label:
                id: result_list
                text: ''
                size_hint_y: None
                height: self.texture_size[1]
                text_size: self.width, None
        
        Button:
            text: 'APRI GOOGLE MAPS'
