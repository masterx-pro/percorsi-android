[app]
title = Percorsi
package.name = percorsi
package.domain = org.mattiaprosperi
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0

# Requirements - IMPORTANT: use specific versions for stability
requirements = python3,kivy==2.3.0,kivymd==2.0.1.dev0,requests,certifi,urllib3,charset-normalizer,idna,pillow,android

# Android configuration
orientation = portrait
fullscreen = 0
android.presplash_color = #FF1DA0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.accept_sdk_license = True
android.enable_androidx = True
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True

# Logcat filters for debugging
android.logcat_filters = *:S python:D

# Build settings
log_level = 2
warn_on_root = 0
