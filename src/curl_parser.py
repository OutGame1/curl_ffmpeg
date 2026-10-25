"""Analyse des commandes cURL copiées depuis les outils développeur."""
import os
import re
import shlex
from urllib.parse import urlparse

def parse_curl(text):
    # Chrome sous Windows copie souvent une commande cmd.exe : ^" délimite
    # les guillemets, ^& protège les esperluettes et ^ en fin de ligne continue
    # la commande. Normaliser ce format avant de tokeniser les arguments.
    text = text.strip()
    text = re.sub(r"\\\s*\r?\n", " ", text)
    text = re.sub(r"\^\s*\r?\n", " ", text)
    # Les guillemets internes des en-têtes (sec-ch-ua, etc.) sont écrits \^".
    # Les convertir en guillemets échappés pour shlex, puis traiter les guillemets
    # extérieurs et les caractères protégés par cmd.exe.
    text = text.replace("^\\^" + '"', "\\" + '"')
    text = text.replace('^"', '"')
    text = re.sub(r"\^([&()<>|])", r"\1", text)
    if not text:
        raise ValueError("Colle une commande cURL.")
    try:
        args = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValueError(f"Commande cURL illisible : {exc}") from exc
    if args and (os.path.basename(args[0]).lower() in ("curl", "curl.exe") or args[0].lower().endswith("\\curl.exe")):
        args = args[1:]

    url, user_agent, referer, cookies = None, None, None, None
    headers, method, has_data = [], "GET", False
    value_opts = {
        "--url": "url", "-H": "header", "--header": "header",
        "-A": "ua", "--user-agent": "ua", "-e": "referer", "--referer": "referer",
        "-b": "cookie", "--cookie": "cookie", "-X": "method", "--request": "method",
        "-d": "data", "--data": "data", "--data-raw": "data", "--data-binary": "data",
        "--data-urlencode": "data",
    }
    ignore_value = {"-o", "--output", "-w", "--write-out", "--connect-timeout", "--max-time", "--retry", "--retry-delay", "--proxy", "-x", "--cacert", "--cert", "--key", "--resolve", "--interface"}
    flags = {"-L", "--location", "--compressed", "-s", "--silent", "-S", "--show-error", "-k", "--insecure", "-g", "--globoff", "--http1.1", "--http2", "--path-as-is", "--fail", "--fail-with-body", "-v", "--verbose", "--ipv4", "-4", "--ipv6", "-6"}
    i = 0
    while i < len(args):
        t = args[i]
        if t in value_opts:
            if i + 1 >= len(args):
                raise ValueError(f"Valeur manquante après {t}")
            val, kind = args[i + 1], value_opts[t]
            if kind == "url": url = val
            elif kind == "ua": user_agent = val
            elif kind == "referer": referer = val
            elif kind == "cookie": cookies = val
            elif kind == "method": method = val.upper()
            elif kind == "data": has_data = True
            elif kind == "header" and ":" in val:
                name, value = val.split(":", 1)
                name, value, lname = name.strip(), value.strip(), name.strip().lower()
                if lname == "user-agent": user_agent = value
                elif lname == "referer": referer = value
                elif lname == "cookie": cookies = value
                elif lname not in ("host", "content-length", "connection", "accept-encoding"):
                    headers.append((name, value))
            i += 2
            continue
        # Common attached forms, e.g. -H'Origin: https://example.com'
        attached = False
        for opt, kind in (("-H", "header"), ("-A", "ua"), ("-e", "referer"), ("-b", "cookie")):
            if t.startswith(opt) and t != opt and not t.startswith("--"):
                val = t[len(opt):]
                if kind == "header" and ":" in val:
                    name, value = val.split(":", 1)
                    name, value, lname = name.strip(), value.strip(), name.strip().lower()
                    if lname == "user-agent": user_agent = value
                    elif lname == "referer": referer = value
                    elif lname == "cookie": cookies = value
                    elif lname not in ("host", "content-length", "connection", "accept-encoding"): headers.append((name, value))
                elif kind == "ua": user_agent = val
                elif kind == "referer": referer = val
                elif kind == "cookie": cookies = val
                attached = True
                break
        if attached:
            i += 1
        elif t in ignore_value:
            i += 2
        elif t in flags or t.startswith("--output="):
            i += 1
        elif t.startswith("-"):
            i += 1
        else:
            if url is None and t.startswith(("https://", "http://")): url = t
            i += 1

    if not url or urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
        raise ValueError("Aucune URL HTTP/HTTPS valide trouvée dans la commande.")
    if has_data or method not in ("GET",):
        raise ValueError("Cette commande utilise une requête autre que GET. Cet outil prend en charge les cURL GET de flux vidéo.")
    return url, headers, user_agent, referer, cookies
