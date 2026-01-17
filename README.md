# 📱 Percorsi Android - Ottimizzatore di Percorsi

[![Build Android APK](https://github.com/YOUR_USERNAME/percorsi-android/actions/workflows/build.yml/badge.svg)](https://github.com/YOUR_USERNAME/percorsi-android/actions/workflows/build.yml)

App Android per l'ottimizzazione di percorsi (TSP - Traveling Salesman Problem) con interfaccia Material Design 3.

## 🚀 Come Ottenere l'APK

### Metodo 1: Scarica dalla Release (Consigliato)
1. Vai alla sezione **[Releases](../../releases)** di questo repository
2. Scarica l'APK più recente
3. Installalo sul tuo dispositivo Android

### Metodo 2: Compila Automaticamente
1. **Fork** questo repository
2. Vai su **Actions** → **Build Android APK**
3. Clicca **Run workflow**
4. Attendi ~30 minuti per la compilazione
5. Scarica l'APK da **Artifacts**

## 🛠️ Setup del Repository

### Passo 1: Crea un nuovo repository su GitHub
1. Vai su [github.com/new](https://github.com/new)
2. Nome: `percorsi-android`
3. Pubblico o Privato (entrambi funzionano)
4. **NON** inizializzare con README

### Passo 2: Carica i file
Puoi farlo in due modi:

#### Opzione A: Upload via Web
1. Vai al tuo repository
2. Clicca "Add file" → "Upload files"
3. Trascina tutti i file del progetto
4. Commit

#### Opzione B: Via Git (da terminale)
```bash
git clone https://github.com/TUO_USERNAME/percorsi-android.git
cd percorsi-android
# Copia qui i file del progetto
git add .
git commit -m "Initial commit"
git push
```

### Passo 3: Abilita GitHub Actions
1. Vai su **Settings** → **Actions** → **General**
2. Seleziona "Allow all actions"
3. In fondo, seleziona "Read and write permissions"
4. Salva

### Passo 4: Avvia la Build
1. Vai su **Actions**
2. Clicca su **Build Android APK**
3. Clicca **Run workflow** → **Run workflow**
4. Attendi ~30-40 minuti

### Passo 5: Scarica l'APK
1. Al termine, clicca sulla build completata
2. Scorri fino a **Artifacts**
3. Scarica `percorsi-android-apk`
4. Estrai lo ZIP e installa l'APK

## 📁 Struttura del Progetto

```
percorsi-android/
├── .github/
│   └── workflows/
│       └── build.yml      # GitHub Actions workflow
├── main.py                # Codice sorgente app
├── buildozer.spec         # Configurazione build
└── README.md              # Questo file
```

## ✨ Funzionalità

- **🗺️ Ottimizzazione Percorsi**: Algoritmo Nearest Neighbor + 2-opt
- **📏 3 Modalità Calcolo Distanze**:
  - Haversine (linea d'aria, velocissimo)
  - OSRM (distanze stradali, gratuito)
  - OpenRouteService (più preciso)
- **📤 Export**: Google Maps, GPX, KML, CSV
- **🎨 UI Material Design 3** con KivyMD
- **🔑 API Key ORS Pre-configurata**

## 📖 Come Usare l'App

1. **Home**: Panoramica e statistiche
2. **Input**: Inserisci coordinate (formato: `lat,lon` per riga)
3. **Opzioni**: Configura modalità distanza e punto di partenza
4. **Risultati**: Visualizza percorso ottimizzato ed esporta

### Formati Coordinate Supportati
```
45.4642,9.1900
41.9028;12.4964
43.7696 11.2558
```

## 🔑 API Key

L'app include una chiave API OpenRouteService funzionante.
Per usare la tua chiave personale:
1. Registrati su https://openrouteservice.org/
2. Ottieni una API key gratuita (2000 req/giorno)
3. Modifica la variabile `ORS_API_KEY` in `main.py`

## 🐛 Troubleshooting

### La build fallisce
- Controlla i log in **Actions** → clicca sulla build fallita
- Problema comune: timeout (riavvia la build)

### L'APK non si installa
- Abilita "Origini sconosciute" nelle impostazioni Android
- Verifica che il dispositivo sia arm64 o arm (non x86)

### Errore di rete nell'app
- Verifica connessione internet
- Usa modalità "Haversine" come fallback

## 📄 Licenza

MIT License - Libero uso personale e commerciale.

## 👤 Autore

**Mattia Prosperi**

---

## 🔧 Note Tecniche

- **Framework**: Kivy 2.3.0 + KivyMD 2.0.1
- **Python**: 3.11
- **Target Android**: API 33 (Android 13)
- **Min Android**: API 21 (Android 5.0)
- **Architetture**: arm64-v8a, armeabi-v7a
