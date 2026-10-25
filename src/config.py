"""Configuration et chemins de l'application."""
import os
import shutil

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = shutil.which("ffmpeg")
QUEUE_FILE = os.path.join(APP_DIR, "file_attente.json")