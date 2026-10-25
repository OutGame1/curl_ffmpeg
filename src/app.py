"""Interface Tkinter de l'application cURL vers FFmpeg."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse
from .config import APP_DIR, FFMPEG
from .curl_parser import parse_curl
from .queue_persistence import QueuePersistenceMixin
from .hls import HlsMixin
from .queue_editor import QueueEditorMixin
from .queue_worker import QueueWorkerMixin

class App(tk.Tk, QueuePersistenceMixin, HlsMixin, QueueEditorMixin, QueueWorkerMixin):
        def __init__(self):
            super().__init__()
            self.title("cURL vers FFmpeg — File d'attente")
            self.geometry("1000x820")
            self.minsize(780, 650)
            self.proc = None
            self.worker = None
            self.stop_requested = False
            self.queue_items = []
            self.next_item_id = 1
            self.active_item_id = None
            self.output_base_for_queue = None
            self.next_output_number = 2

            frame = ttk.Frame(self, padding=12)
            frame.pack(fill="both", expand=True)

            ttk.Label(frame, text="Commande cURL (Chrome → Réseau → Copier en tant que cURL)").pack(anchor="w")
            self.curl = tk.Text(frame, height=10, wrap="word")
            self.curl.pack(fill="both", expand=True, pady=(5, 8))
            self.curl.insert("1.0", "curl 'https://exemple.com/video.m3u8' -H 'Referer: https://exemple.com/'")

            row = ttk.Frame(frame)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text="Fichier de sortie :").pack(side="left")
            self.output = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Videos", "video.mkv"))
            ttk.Entry(row, textvariable=self.output).pack(side="left", fill="x", expand=True, padx=6)
            ttk.Button(row, text="Parcourir…", command=self.pick_output).pack(side="left")

            row = ttk.Frame(frame)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text="Format :").pack(side="left")
            self.format = tk.StringVar(value="mkv")
            combo = ttk.Combobox(row, textvariable=self.format, values=("mkv", "mp4"), state="readonly", width=8)
            combo.pack(side="left", padx=6)
            combo.bind("<<ComboboxSelected>>", self.update_extension)

            row = ttk.Frame(frame)
            row.pack(fill="x", pady=(7, 4))
            self.add_btn = ttk.Button(row, text="Ajouter à la file", command=self.add_to_queue)
            self.add_btn.pack(side="left")
            self.start_btn = ttk.Button(row, text="Lancer la file", command=self.start_queue)
            self.start_btn.pack(side="left", padx=8)
            self.stop_btn = ttk.Button(row, text="Arrêter la file", command=self.stop, state="disabled")
            self.stop_btn.pack(side="left")
            ttk.Button(row, text="Effacer le journal", command=self.clear_log).pack(side="right")

            ttk.Label(frame, text="File d'attente — les éléments restent dans la liste après leur traitement").pack(anchor="w", pady=(7, 3))
            columns = ("file", "status")
            self.queue = ttk.Treeview(frame, columns=columns, show="headings", height=7, selectmode="extended")
            self.queue.heading("file", text="Fichier de sortie")
            self.queue.heading("status", text="Statut")
            self.queue.column("file", width=680, anchor="w")
            self.queue.column("status", width=140, anchor="center")
            self.queue.pack(fill="x", expand=False)
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=(4, 8))
            ttk.Button(row, text="Consulter / modifier", command=self.show_selected_item).pack(side="left")
            ttk.Button(row, text="Supprimer la sélection", command=self.remove_selected).pack(side="left", padx=8)
            ttk.Button(row, text="Vider les éléments terminés", command=self.remove_finished).pack(side="left")

            self.queue.bind("<Double-1>", self._queue_double_click)

            ttk.Label(frame, text="Journal FFmpeg").pack(anchor="w")
            self.log = tk.Text(frame, height=8, wrap="word", state="disabled")
            self.log.pack(fill="both", expand=True, pady=(5, 0))
            ttk.Label(frame, text="Les téléchargements sont séquentiels et utilisent -c copy, sans réencodage.", wraplength=940).pack(anchor="w", pady=(8, 0))
            self.load_queue()
            self.protocol("WM_DELETE_WINDOW", self.on_close)
        def pick_output(self):
            ext = self.format.get()
            name = filedialog.asksaveasfilename(defaultextension="." + ext, filetypes=[(ext.upper(), "*." + ext), ("Tous les fichiers", "*.*")])
            if name:
                self.output.set(name)
                selected_ext = os.path.splitext(name)[1].lstrip(".").lower()
                if selected_ext in ("mkv", "mp4"):
                    self.format.set(selected_ext)
                self.update_extension()
        def update_extension(self, _=None):
            path = self.output.get().strip()
            base, ext = os.path.splitext(path)
            if ext.lower() in (".mkv", ".mp4"):
                path = base
            if path:
                self.output.set(path + "." + self.format.get())
        def log_line(self, value):
            self.log.configure(state="normal")
            self.log.insert("end", value)
            self.log.see("end")
            self.log.configure(state="disabled")
        def clear_log(self):
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")
        def add_to_queue(self):
            try:
                url, headers, ua, referer, cookies = parse_curl(self.curl.get("1.0", "end"))
            except ValueError as exc:
                messagebox.showerror("Commande cURL invalide", str(exc))
                return
            output = self.output.get().strip().strip('"')
            if not output:
                messagebox.showerror("Fichier manquant", "Choisis un nom de fichier de sortie.")
                return
            fmt = self.format.get().lower()
            ext = "." + fmt
            if os.path.splitext(output)[1].lower() != ext:
                output = os.path.splitext(output)[0] + ext
                self.output.set(output)
            normalized_output = os.path.normcase(os.path.abspath(output))
            for item in self.queue_items:
                if os.path.normcase(os.path.abspath(item["output"])) == normalized_output:
                    messagebox.showerror("Fichier déjà utilisé", "Ce fichier de sortie est déjà présent dans la file. Choisis un nom différent pour éviter d'écraser un téléchargement.")
                    return

            item_id = str(self.next_item_id)
            self.next_item_id += 1
            item = {
                "id": item_id,
                "url": url,
                "headers": headers,
                "ua": ua,
                "referer": referer,
                "cookies": cookies,
                "output": os.path.abspath(output),
                "format": fmt,
                "status": "En attente",
                "metadata": [],
            }
            self.queue_items.append(item)
            self.queue.insert("", "end", iid=item_id, values=(item["output"], item["status"]))
            self.log_line(f"Ajouté à la file : {item['output']}\n")
            self.save_queue()
            # Prépare un nom différent pour le prochain élément.
            if self.output_base_for_queue is None:
                self.output_base_for_queue = os.path.splitext(output)[0]
                self.next_output_number = 2
            next_path = f"{self.output_base_for_queue}_{self.next_output_number}{ext}"
            while any(os.path.normcase(os.path.abspath(q["output"])) == os.path.normcase(os.path.abspath(next_path)) for q in self.queue_items):
                self.next_output_number += 1
                next_path = f"{self.output_base_for_queue}_{self.next_output_number}{ext}"
            self.output.set(next_path)
            self.next_output_number += 1
        def _queue_double_click(self, _event=None):
            self.show_selected_item()
        def set_item_status(self, item_id, status):
            for item in self.queue_items:
                if item["id"] == item_id:
                    item["status"] = status
                    if self.queue.exists(item_id):
                        self.queue.set(item_id, "status", status)
                    self.save_queue()
                    return
        def remove_selected(self):
            selected = self.queue.selection()
            if not selected:
                messagebox.showinfo("Aucune sélection", "Sélectionne un ou plusieurs éléments à supprimer.")
                return
            if self.worker and self.worker.is_alive():
                active = self.active_item_id
                if active and active in selected:
                    messagebox.showwarning("Téléchargement en cours", "L'élément en cours ne peut pas être supprimé. Arrête d'abord la file.")
                    return
            for item_id in selected:
                self.queue_items = [item for item in self.queue_items if item["id"] != item_id]
                if self.queue.exists(item_id):
                    self.queue.delete(item_id)
            self.log_line(f"{len(selected)} élément(s) supprimé(s) de la file.\n")
            self.save_queue()
        def remove_finished(self):
            if self.worker and self.worker.is_alive():
                messagebox.showwarning("File en cours", "Attends la fin de la file avant de retirer les éléments terminés.")
                return
            removable = [item["id"] for item in self.queue_items if item["status"] in ("Terminé", "Erreur", "Arrêté")]
            for item_id in removable:
                self.queue_items = [item for item in self.queue_items if item["id"] != item_id]
                if self.queue.exists(item_id):
                    self.queue.delete(item_id)
            self.log_line(f"{len(removable)} élément(s) terminé(s), en erreur ou arrêté(s) retiré(s) de la file.\n")
            self.save_queue()
        def stop(self):
            self.stop_requested = True
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except OSError:
                    pass
            self.log_line("\nArrêt demandé : le téléchargement en cours va s'arrêter.\n")

if __name__ == "__main__":
    app = App()
    app.mainloop()
