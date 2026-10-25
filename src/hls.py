"""Inspection des playlists HLS et construction des arguments FFmpeg."""
import re
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import URLError
from .config import FFMPEG

class HlsMixin:
        def input_options(self, item):
            opts = []
            if item["ua"]:
                opts += ["-user_agent", item["ua"]]
            if item["referer"]:
                opts += ["-referer", item["referer"]]
            if item["cookies"]:
                opts += ["-cookies", item["cookies"]]
            if item["headers"]:
                opts += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in item["headers"])]
            return opts

        def select_best_hls_variant(self, item):
            """Lit une master playlist HLS et choisit la variante de meilleure qualité.
            Retourne (url_video, url_audio, description). Si ce n'est pas une master
            playlist ou si elle ne peut pas être analysée, retourne (None, None, None)
            pour laisser FFmpeg choisir automatiquement les flux.
            """
            request_headers = {k: v for k, v in item["headers"]}
            if item["ua"]:
                request_headers["User-Agent"] = item["ua"]
            if item["referer"]:
                request_headers["Referer"] = item["referer"]
            if item["cookies"]:
                request_headers["Cookie"] = item["cookies"]
            request = Request(item["url"], headers=request_headers)
            try:
                # Tente d'abord une connexion TLS normale. Si le serveur présente
                # explicitement un certificat expiré, on ne contourne la vérification
                # que pour cette lecture de playlist, pas pour tout le programme.
                with urlopen(request, timeout=15) as response:
                    playlist = response.read(4 * 1024 * 1024).decode("utf-8-sig", errors="replace")
            except (ssl.SSLCertVerificationError, URLError) as exc:
                reason = getattr(exc, "reason", exc)
                if not isinstance(reason, ssl.SSLCertVerificationError):
                    raise
                # Certains serveurs HLS ont un certificat expiré. Ce repli permet
                # uniquement d'inspecter la playlist; FFmpeg gère ensuite ses entrées.
                with urlopen(request, timeout=15, context=ssl._create_unverified_context()) as response:
                    playlist = response.read(4 * 1024 * 1024).decode("utf-8-sig", errors="replace")
            if "#EXTM3U" not in playlist or "#EXT-X-STREAM-INF" not in playlist:
                return None, None, None

            audio_groups = {}
            for line in playlist.splitlines():
                line = line.strip()
                if not line.startswith("#EXT-X-MEDIA:"):
                    continue
                attrs = {}
                for match in re.finditer(r'([A-Z0-9-]+)=("[^"\n]*"|[^,]*)', line.split(":", 1)[1]):
                    attrs[match.group(1)] = match.group(2).strip().strip('"')
                if attrs.get("TYPE") == "AUDIO" and attrs.get("GROUP-ID") and attrs.get("URI"):
                    audio_groups.setdefault(attrs["GROUP-ID"], []).append(attrs)

            variants = []
            lines = [line.strip() for line in playlist.splitlines()]
            for index, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF:"):
                    continue
                attrs = {}
                for match in re.finditer(r'([A-Z0-9-]+)=("[^"\n]*"|[^,]*)', line.split(":", 1)[1]):
                    attrs[match.group(1)] = match.group(2).strip().strip('"')
                uri = next((candidate for candidate in lines[index + 1:] if candidate and not candidate.startswith("#")), None)
                if not uri:
                    continue
                width = height = 0
                resolution = attrs.get("RESOLUTION", "")
                match = re.fullmatch(r"(\d+)x(\d+)", resolution, re.IGNORECASE)
                if match:
                    width, height = int(match.group(1)), int(match.group(2))
                try:
                    bandwidth = int(attrs.get("AVERAGE-BANDWIDTH") or attrs.get("BANDWIDTH") or 0)
                except ValueError:
                    bandwidth = 0
                def resolve_hls_uri(base_url, relative_uri):
                    resolved = urljoin(base_url, relative_uri)
                    # Certains serveurs signent les URL avec une query-string portée
                    # par la master playlist, mais omettent cette query des URI
                    # relatives de variantes. La recopier évite de perdre le jeton.
                    base_parts = urlsplit(base_url)
                    uri_parts = urlsplit(resolved)
                    if not uri_parts.query and base_parts.query and uri_parts.netloc == base_parts.netloc:
                        resolved = urlunsplit((uri_parts.scheme, uri_parts.netloc, uri_parts.path,
                                               base_parts.query, uri_parts.fragment))
                    return resolved

                audio_url = None
                group = attrs.get("AUDIO")
                if group and group in audio_groups:
                    renditions = audio_groups[group]
                    chosen_audio = next((a for a in renditions if a.get("DEFAULT", "NO").upper() == "YES"), renditions[0])
                    audio_url = resolve_hls_uri(item["url"], chosen_audio["URI"])
                variants.append({"url": resolve_hls_uri(item["url"], uri), "audio_url": audio_url,
                                 "width": width, "height": height, "bandwidth": bandwidth})
            if not variants:
                return None, None, None
            # La résolution prime, puis le débit en cas de résolution identique.
            best = max(variants, key=lambda v: (v["width"] * v["height"], v["height"], v["width"], v["bandwidth"]))
            if best["width"] and best["height"]:
                description = f"{best['width']}x{best['height']}"
            elif best["bandwidth"]:
                description = f"débit {best['bandwidth'] // 1000} kbit/s (résolution non indiquée)"
            else:
                description = "variante la plus élevée selon la playlist"
            return best["url"], best["audio_url"], description

        def build_command(self, item, video_url=None, audio_url=None):
            cmd = [FFMPEG, "-hide_banner", "-y", "-nostdin"]
            cmd += self.input_options(item)
            cmd += ["-i", video_url or item["url"]]
            if audio_url:
                cmd += self.input_options(item)
                cmd += ["-i", audio_url, "-map", "0:v:0", "-map", "1:a:0?"]
            elif video_url:
                cmd += ["-map", "0:v:0", "-map", "0:a?"]
            # Si l'analyse de la master playlist échoue, ne pas forcer -map 0 :
            # FFmpeg choisit automatiquement le flux vidéo de plus haute résolution.
            cmd += ["-c", "copy"]
            # Les métadonnées sont passées comme arguments séparés pour préserver espaces et caractères spéciaux.
            for key, value in item.get("metadata", []):
                if key.strip():
                    cmd += ["-metadata", f"{key.strip()}={value}"]
            if item["format"] == "mp4":
                cmd += ["-movflags", "+faststart"]
            cmd += [item["output"]]
            return cmd
