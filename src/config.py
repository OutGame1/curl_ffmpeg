"""Configuration et chemins de l'application."""
import os

# Le dossier racine contient main.py, ffmpeg.exe et file_attente.json.
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = os.path.join(APP_DIR, "ffmpeg.exe")
QUEUE_FILE = os.path.join(APP_DIR, "file_attente.json")
