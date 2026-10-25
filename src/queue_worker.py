"""Exécution séquentielle des téléchargements FFmpeg."""
import os
import subprocess
import threading
from tkinter import messagebox
from .config import FFMPEG

class QueueWorkerMixin:
        def start_queue(self):
            if self.worker and self.worker.is_alive():
                return
            if not os.path.isfile(FFMPEG):
                messagebox.showerror("FFmpeg manquant", "FFmpeg est nécessaire pour télécharger les vidéos.\n\nPlace ffmpeg.exe dans le même dossier que curl_to_ffmpeg.py, puis relance le programme.\n\nEmplacement attendu :\n" + FFMPEG)
                return
            waiting = [item for item in self.queue_items if item["status"] == "En attente"]
            if not waiting:
                messagebox.showinfo("File vide", "Aucun téléchargement en attente dans la file.")
                return
            self.stop_requested = False
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.log_line(f"\nDémarrage de la file : {len(waiting)} téléchargement(s) en attente.\n")
            self.worker = threading.Thread(target=self.run_queue, daemon=True)
            self.worker.start()

        def run_queue(self):
            while not self.stop_requested:
                # Recherche le prochain élément en attente à chaque tour :
                # les nouveaux éléments ajoutés pendant un téléchargement seront pris en compte.
                item = next((q for q in self.queue_items if q["status"] == "En attente"), None)
                if item is None:
                    break
                item_id = item["id"]
                item["status"] = "En cours"
                self.active_item_id = item_id
                self.after(0, self.set_item_status, item_id, "En cours")
                self.after(0, self.log_line, f"\n--- Téléchargement : {item['output']} ---\n")
                output = item["output"]
                try:
                    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
                    video_url = audio_url = description = None
                    try:
                        self.after(0, self.log_line, "Analyse de la playlist HLS pour sélectionner la meilleure qualité…\n")
                        video_url, audio_url, description = self.select_best_hls_variant(item)
                        if video_url:
                            self.after(0, self.log_line, f"Qualité sélectionnée : {description}\n")
                        else:
                            self.after(0, self.log_line, "Playlist directe ou qualité non détectable : FFmpeg sélectionnera automatiquement le flux vidéo de plus haute résolution.\n")
                    except Exception as playlist_error:
                        self.after(0, self.log_line, f"Analyse de qualité impossible ({playlist_error}). FFmpeg tentera la sélection automatique.\n")
                    cmd = self.build_command(item, video_url, audio_url)
                    self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    for line in self.proc.stdout:
                        self.after(0, self.log_line, line)
                        if self.stop_requested and self.proc.poll() is None:
                            self.proc.terminate()
                    code = self.proc.wait()
                    if self.stop_requested:
                        status = "Arrêté"
                        self.after(0, self.log_line, "\nTéléchargement arrêté par l'utilisateur.\n")
                    elif code == 0:
                        status = "Terminé"
                        self.after(0, self.log_line, "\nTéléchargement terminé.\n")
                    else:
                        status = "Erreur"
                        self.after(0, self.log_line, f"\nFFmpeg a échoué (code {code}).\n")
                except Exception as exc:
                    status = "Erreur"
                    self.after(0, self.log_line, f"\nErreur : {exc}\n")
                finally:
                    self.proc = None
                    item["status"] = status
                    self.after(0, self.set_item_status, item_id, status)
                    self.active_item_id = None
            self.after(0, self.queue_finished)

        def queue_finished(self):
            self.start_btn.configure(state="normal")
            self.add_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            if self.stop_requested:
                self.log_line("\nFile arrêtée. Les autres éléments restent en attente.\n")
            else:
                remaining = sum(1 for item in self.queue_items if item["status"] == "En attente")
                self.log_line(f"\nFile traitée. Éléments encore en attente : {remaining}.\n")
