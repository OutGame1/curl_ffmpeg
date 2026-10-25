"""Persistance JSON de la file d'attente."""
import json
import os
import tempfile
from urllib.parse import urlparse
from tkinter import messagebox
from .config import APP_DIR, QUEUE_FILE

class QueuePersistenceMixin:
        def save_queue(self):
            """Sauvegarde la file dans un JSON local, avec remplacement atomique."""
            data = []
            for item in self.queue_items:
                data.append({
                    "id": item["id"], "url": item["url"], "headers": item["headers"],
                    "ua": item["ua"], "referer": item["referer"], "cookies": item["cookies"],
                    "output": item["output"], "format": item["format"], "status": item["status"],
                    "metadata": item.get("metadata", []),
                })
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=APP_DIR, prefix="file_attente_", suffix=".tmp", delete=False) as f:
                    temp_path = f.name
                    json.dump({"version": 1, "items": data}, f, ensure_ascii=False, indent=2)
                    f.write("\n")
                os.replace(temp_path, QUEUE_FILE)
            except (OSError, TypeError, ValueError) as exc:
                self.log_line(f"\nImpossible de sauvegarder la file d'attente : {exc}\n")
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

        def load_queue(self):
            """Recharge les éléments enregistrés ; un téléchargement interrompu redevient en attente."""
            if not os.path.isfile(QUEUE_FILE):
                return
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                items = saved.get("items", []) if isinstance(saved, dict) else []
                for raw in items:
                    if not isinstance(raw, dict):
                        continue
                    url = str(raw.get("url", "")).strip()
                    output = str(raw.get("output", "")).strip()
                    fmt = str(raw.get("format", "mkv")).lower()
                    if not url or urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
                        continue
                    if not output or fmt not in ("mkv", "mp4"):
                        continue
                    item_id = str(raw.get("id", self.next_item_id))
                    if any(q["id"] == item_id for q in self.queue_items):
                        item_id = str(self.next_item_id)
                    status = raw.get("status", "En attente")
                    if status == "En cours":
                        status = "En attente"
                    if status not in ("En attente", "Terminé", "Erreur", "Arrêté"):
                        status = "En attente"
                    headers = raw.get("headers", [])
                    if not isinstance(headers, list):
                        headers = []
                    clean_headers = [(str(h[0]), str(h[1])) for h in headers if isinstance(h, (list, tuple)) and len(h) == 2]
                    metadata = raw.get("metadata", [])
                    if not isinstance(metadata, list):
                        metadata = []
                    clean_metadata = []
                    for tag in metadata:
                        if isinstance(tag, (list, tuple)) and len(tag) == 2:
                            key, value = str(tag[0]).strip(), str(tag[1])
                            if key:
                                clean_metadata.append((key, value))
                    item = {
                        "id": item_id, "url": url, "headers": clean_headers,
                        "ua": raw.get("ua") or None, "referer": raw.get("referer") or None,
                        "cookies": raw.get("cookies") or None, "output": os.path.abspath(output),
                        "format": fmt, "status": status, "metadata": clean_metadata,
                    }
                    self.queue_items.append(item)
                    self.queue.insert("", "end", iid=item_id, values=(item["output"], item["status"]))
                    try:
                        self.next_item_id = max(self.next_item_id, int(item_id) + 1)
                    except ValueError:
                        self.next_item_id += 1
                if self.queue_items:
                    self.log_line(f"{len(self.queue_items)} élément(s) restauré(s) depuis file_attente.json.\n")
                    self.save_queue()
            except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
                messagebox.showwarning("File d'attente non chargée", f"Le fichier {QUEUE_FILE} n'a pas pu être lu.\n\n{exc}", parent=self)

        def on_close(self):
            if self.worker and self.worker.is_alive():
                if not messagebox.askyesno("Téléchargement en cours", "Un téléchargement est en cours. Fermer la fenêtre arrêtera le programme et le téléchargement. Les éléments seront conservés pour le prochain lancement. Continuer ?"):
                    return
                self.stop_requested = True
                if self.proc and self.proc.poll() is None:
                    try:
                        self.proc.terminate()
                    except OSError:
                        pass
            self.save_queue()
            self.destroy()
