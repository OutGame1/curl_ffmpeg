"""Fenêtre de consultation et de modification des éléments de la file."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

class QueueEditorMixin:
        def show_selected_item(self):
            selected = self.queue.selection()
            if not selected:
                messagebox.showinfo("Aucun élément sélectionné", "Sélectionne un élément dans la file d'attente.")
                return
            if len(selected) > 1:
                messagebox.showinfo("Sélection multiple", "Sélectionne un seul élément pour consulter ses informations.")
                return
            item_id = selected[0]
            item = next((q for q in self.queue_items if q["id"] == item_id), None)
            if item is None:
                return

            editable = item["status"] == "En attente"
            win = tk.Toplevel(self)
            win.title("Informations de l'élément — " + os.path.basename(item["output"]))
            win.geometry("760x720")
            win.minsize(620, 580)
            win.transient(self)
            win.grab_set()

            root = ttk.Frame(win, padding=12)
            root.pack(fill="both", expand=True)
            ttk.Label(root, text=f"Statut : {item['status']}" + ("" if editable else " — consultation seule")).pack(anchor="w", pady=(0, 8))

            form = ttk.Frame(root)
            form.pack(fill="both", expand=True)
            form.columnconfigure(1, weight=1)

            # Certaines apparences Windows rendent le texte des champs ttk en lecture seule
            # trop pâle. Imposer un contraste lisible pour les éléments en cours/terminés.
            style = ttk.Style(win)
            style.configure("QueueReadonly.TEntry", fieldbackground="#ffffff", foreground="#111111")

            def add_entry(label, value, row, *, show=None, state=None):
                ttk.Label(form, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=5)
                var = tk.StringVar(value=value or "")
                entry_state = state or ("normal" if editable else "readonly")
                entry_style = "QueueReadonly.TEntry" if entry_state == "readonly" else "TEntry"
                entry = ttk.Entry(form, textvariable=var, show=show, state=entry_state, style=entry_style)
                entry.grid(row=row, column=1, sticky="ew", pady=5)
                return var, entry

            url_var, _ = add_entry("URL de la playlist", item["url"], 0)
            ua_var, _ = add_entry("User-Agent", item["ua"], 1)
            referer_var, _ = add_entry("Referer", item["referer"], 2)
            cookie_var, _ = add_entry("Cookies", item["cookies"], 3)

            ttk.Label(form, text="Autres en-têtes").grid(row=4, column=0, sticky="nw", padx=(0, 10), pady=5)
            headers_box = tk.Text(form, height=8, wrap="word")
            headers_box.grid(row=4, column=1, sticky="nsew", pady=5)
            for name, value in item["headers"]:
                headers_box.insert("end", f"{name}: {value}\n")
            if not editable:
                headers_box.configure(state="disabled", disabledforeground="#111111", background="#ffffff")

            ttk.Label(form, text="Métadonnées vidéo").grid(row=5, column=0, sticky="nw", padx=(0, 10), pady=5)
            metadata_box = tk.Text(form, height=6, wrap="word")
            metadata_box.grid(row=5, column=1, sticky="nsew", pady=5)
            metadata_box.insert("end", "\n".join(f"{key}={value}" for key, value in item.get("metadata", [])))
            if not editable:
                metadata_box.configure(state="disabled", disabledforeground="#111111", background="#ffffff")
            ttk.Label(form, text="Une par ligne : clé=valeur. Ex. title=Mon film, artist=Réalisateur, date=2026, genre=Action, comment=Ma description", wraplength=180).grid(row=6, column=0, sticky="nw", padx=(0, 10), pady=5)
            form.rowconfigure(4, weight=1)
            form.rowconfigure(5, weight=1)

            output_row = ttk.Frame(form)
            output_row.grid(row=7, column=1, sticky="ew", pady=5)
            output_row.columnconfigure(0, weight=1)
            output_var = tk.StringVar(value=item["output"])
            output_entry = ttk.Entry(output_row, textvariable=output_var, state="normal" if editable else "readonly")
            output_entry.grid(row=0, column=0, sticky="ew")
            def browse_output():
                chosen = filedialog.asksaveasfilename(
                    parent=win,
                    initialdir=os.path.dirname(output_var.get()) or os.path.expanduser("~"),
                    initialfile=os.path.basename(output_var.get()),
                    defaultextension="." + format_var.get(),
                    filetypes=[("MKV", "*.mkv"), ("MP4", "*.mp4"), ("Tous les fichiers", "*.*")]
                )
                if chosen:
                    output_var.set(chosen)
                    ext = os.path.splitext(chosen)[1].lower()
                    if ext in (".mkv", ".mp4"):
                        format_var.set(ext[1:])
            ttk.Label(form, text="Fichier de sortie").grid(row=7, column=0, sticky="nw", padx=(0, 10), pady=5)
            browse_btn = ttk.Button(output_row, text="Parcourir…", command=browse_output, state="normal" if editable else "disabled")
            browse_btn.grid(row=0, column=1, padx=(6, 0))

            ttk.Label(form, text="Format").grid(row=8, column=0, sticky="nw", padx=(0, 10), pady=5)
            format_var = tk.StringVar(value=item["format"])
            format_box = ttk.Combobox(form, textvariable=format_var, values=("mkv", "mp4"), state="readonly" if editable else "disabled", width=10)
            format_box.grid(row=8, column=1, sticky="w", pady=5)

            def close():
                try:
                    win.grab_release()
                except tk.TclError:
                    pass
                win.destroy()

            buttons = ttk.Frame(root)
            buttons.pack(fill="x", pady=(10, 0))
            if editable:
                def save_changes():
                    new_url = url_var.get().strip()
                    parsed = urlparse(new_url)
                    if parsed.scheme not in ("http", "https") or not parsed.netloc:
                        messagebox.showerror("URL invalide", "Saisis une URL HTTP ou HTTPS valide.", parent=win)
                        return
                    new_output = output_var.get().strip().strip('"')
                    if not new_output:
                        messagebox.showerror("Fichier manquant", "Choisis un fichier de sortie.", parent=win)
                        return
                    new_format = format_var.get().lower()
                    base, ext = os.path.splitext(new_output)
                    if ext.lower() in (".mkv", ".mp4"):
                        new_output = base + "." + new_format
                    else:
                        new_output += "." + new_format
                    normalized = os.path.normcase(os.path.abspath(new_output))
                    for other in self.queue_items:
                        if other["id"] != item_id and os.path.normcase(os.path.abspath(other["output"])) == normalized:
                            messagebox.showerror("Fichier déjà utilisé", "Un autre élément de la file utilise déjà ce fichier de sortie.", parent=win)
                            return
                    new_headers = []
                    for line in headers_box.get("1.0", "end-1c").splitlines():
                        if not line.strip():
                            continue
                        if ":" not in line:
                            messagebox.showerror("En-tête invalide", f"Cette ligne ne contient pas de deux-points :\n{line}", parent=win)
                            return
                        name, value = line.split(":", 1)
                        if not name.strip():
                            messagebox.showerror("En-tête invalide", "Le nom d'un en-tête ne peut pas être vide.", parent=win)
                            return
                        lname = name.strip().lower()
                        if lname in ("user-agent", "referer", "cookie"):
                            messagebox.showerror("En-tête déjà séparé", f"Modifie {name.strip()} dans son champ dédié ci-dessus.", parent=win)
                            return
                        if lname in ("host", "content-length", "connection", "accept-encoding"):
                            messagebox.showerror("En-tête non pris en charge", f"L'en-tête {name.strip()} est géré automatiquement ou ignoré par le programme.", parent=win)
                            return
                        new_headers.append((name.strip(), value.strip()))
                    new_metadata = []
                    seen_metadata_keys = set()
                    for line in metadata_box.get("1.0", "end-1c").splitlines():
                        if not line.strip():
                            continue
                        if "=" not in line:
                            messagebox.showerror("Métadonnée invalide", f"Cette ligne doit être au format clé=valeur :\n{line}", parent=win)
                            return
                        key, value = line.split("=", 1)
                        key = key.strip()
                        if not key:
                            messagebox.showerror("Métadonnée invalide", "La clé d'une métadonnée ne peut pas être vide.", parent=win)
                            return
                        if key.lower() in seen_metadata_keys:
                            messagebox.showerror("Métadonnée en double", f"La clé « {key} » est présente plusieurs fois.", parent=win)
                            return
                        seen_metadata_keys.add(key.lower())
                        new_metadata.append((key, value.strip()))
                    item.update({
                        "url": new_url,
                        "metadata": new_metadata,
                        "ua": ua_var.get().strip() or None,
                        "referer": referer_var.get().strip() or None,
                        "cookies": cookie_var.get().strip() or None,
                        "headers": new_headers,
                        "output": os.path.abspath(new_output),
                        "format": new_format,
                    })
                    self.queue.set(item_id, "file", item["output"])
                    self.queue.set(item_id, "status", item["status"])
                    self.log_line(f"Informations modifiées pour : {item['output']}\n")
                    self.save_queue()
                    close()

                ttk.Button(buttons, text="Enregistrer les modifications", command=save_changes).pack(side="left")
            ttk.Button(buttons, text="Fermer", command=close).pack(side="right")
