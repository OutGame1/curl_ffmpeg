"""Inspection des playlists HLS et construction des arguments FFmpeg."""
import re
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
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
            ignored_headers = {
                "if-none-match",
                "if-modified-since",
                "if-match",
                "if-unmodified-since",
                "if-range",
            }

            headers = [
                (k, v)
                for k, v in item["headers"]
                if k.lower() not in ignored_headers
            ]

            if headers:
                opts += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in headers)]

        return opts

    def select_best_hls_variant(self, item):
        """Lit une master playlist HLS et choisit la variante de meilleure qualité.
        Retourne (url_video, url_audio, description). Si ce n'est pas une master
        playlist ou si elle ne peut pas être analysée, retourne (None, None, None)
        pour laisser FFmpeg choisir automatiquement.
        """

        # On retire les éventuels en-têtes conditionnels provenant de cURL.
        # Ils peuvent provoquer une réponse HTTP 304 sans contenu exploitable.
        conditional_headers = {
            "if-none-match",
            "if-modified-since",
            "if-match",
            "if-unmodified-since",
            "if-range",
        }

        request_headers = {
            k: v for k, v in item["headers"]
            if k.lower() not in conditional_headers
        }

        if item["ua"]:
            request_headers["User-Agent"] = item["ua"]

        if item["referer"]:
            request_headers["Referer"] = item["referer"]

        if item["cookies"]:
            request_headers["Cookie"] = item["cookies"]

        # Évite autant que possible une réponse issue d'une validation de cache.
        request_headers["Cache-Control"] = "no-cache"
        request_headers["Pragma"] = "no-cache"

        def read_playlist(context=None):
            print("En-têtes envoyés à la playlist :", list(request_headers.keys()))

            request = Request(item["url"], headers=request_headers)

            print("=== REQUÊTE HLS ===")
            print("URL :", request.full_url)
            print("Méthode :", request.get_method())
            print("En-têtes :", dict(request.header_items()))

            try:
                with urlopen(request, timeout=15, context=context) as response:
                    print("Statut HTTP :", response.status)
                    print("URL finale :", response.url)
                    print("En-têtes réponse :", dict(response.headers.items()))

                    if response.status != 200:
                        raise ValueError(
                            f"Réponse HTTP inattendue : {response.status}"
                        )

                    content = response.read(4 * 1024 * 1024)

                    if not content:
                        raise ValueError("La playlist HLS reçue est vide.")

                    playlist = content.decode("utf-8", errors="replace")

                    print("Taille de la playlist :", len(content))
                    print("Début de la playlist :", repr(playlist[:300]))
                    print("Master playlist :", "#EXT-X-STREAM-INF" in playlist)
                    print("Nombre de variantes :", playlist.count("#EXT-X-STREAM-INF:"))

                    return playlist

            except HTTPError as exc:
                if exc.code == 304:
                    raise ValueError(
                        "Le serveur a renvoyé HTTP 304 malgré la suppression "
                        "des en-têtes conditionnels. Impossible de récupérer "
                        "le contenu de la playlist."
                    ) from exc
                raise

        try:
            # Première tentative avec vérification TLS normale.
            playlist = read_playlist()

        except (ssl.SSLCertVerificationError, URLError) as exc:
            reason = getattr(exc, "reason", exc)

            if not isinstance(reason, ssl.SSLCertVerificationError):
                raise

            # Repli SSL uniquement pour cette lecture de playlist.
            playlist = read_playlist(
                ssl._create_unverified_context()
            )

        if "#EXTM3U" not in playlist:
            return None, None, None

        # Playlist directe : elle contient les segments vidéo.
        if "#EXTINF:" in playlist and "#EXT-X-STREAM-INF:" not in playlist:
            return item["url"], None, "Playlist directe"

        audio_groups = {}

        for line in playlist.splitlines():
            line = line.strip()

            if not line.startswith("#EXT-X-MEDIA:"):
                continue

            attrs = {}

            for match in re.finditer(
                r'([A-Z0-9-]+)=("[^"\n]*"|[^,]*)',
                line.split(":", 1)[1]
            ):
                attrs[match.group(1)] = match.group(2).strip().strip('"')

            if (
                attrs.get("TYPE") == "AUDIO"
                and attrs.get("GROUP-ID")
                and attrs.get("URI")
            ):
                audio_groups.setdefault(attrs["GROUP-ID"], []).append(attrs)

        variants = []
        lines = [line.strip() for line in playlist.splitlines()]

        def resolve_hls_uri(base_url, relative_uri):
            resolved = urljoin(base_url, relative_uri)

            # Certains serveurs signent les URL avec une query-string portée
            # par la master playlist, mais omettent cette query des URI
            # relatives de variantes. On la recopie dans ce cas.
            base_parts = urlsplit(base_url)
            uri_parts = urlsplit(resolved)

            if (
                not uri_parts.query
                and base_parts.query
                and uri_parts.netloc == base_parts.netloc
            ):
                resolved = urlunsplit((
                    uri_parts.scheme,
                    uri_parts.netloc,
                    uri_parts.path,
                    base_parts.query,
                    uri_parts.fragment
                ))

            return resolved

        for index, line in enumerate(lines):

            if not line.startswith("#EXT-X-STREAM-INF:"):
                continue

            attrs = {}

            for match in re.finditer(
                r'([A-Z0-9-]+)=("[^"\n]*"|[^,]*)',
                line.split(":", 1)[1]
            ):
                attrs[match.group(1)] = match.group(2).strip().strip('"')

            uri = next(
                (
                    candidate
                    for candidate in lines[index + 1:]
                    if candidate and not candidate.startswith("#")
                ),
                None
            )

            if not uri:
                continue

            width = height = 0

            resolution = attrs.get("RESOLUTION", "")
            match = re.fullmatch(r"(\d+)x(\d+)", resolution, re.IGNORECASE)

            if match:
                width = int(match.group(1))
                height = int(match.group(2))

            try:
                bandwidth = int(
                    attrs.get("AVERAGE-BANDWIDTH")
                    or attrs.get("BANDWIDTH")
                    or 0
                )
            except ValueError:
                bandwidth = 0

            audio_url = None
            group = attrs.get("AUDIO")

            if group and group in audio_groups:
                renditions = audio_groups[group]

                chosen_audio = next(
                    (
                        audio for audio in renditions
                        if audio.get("DEFAULT", "NO").upper() == "YES"
                    ),
                    renditions[0]
                )

                audio_url = resolve_hls_uri(
                    item["url"],
                    chosen_audio["URI"]
                )

            variants.append({
                "url": resolve_hls_uri(item["url"], uri),
                "audio_url": audio_url,
                "width": width,
                "height": height,
                "bandwidth": bandwidth
            })

        if not variants:
            return None, None, None

        # La résolution prime, puis le débit en cas de résolution identique.
        best = max(
            variants,
            key=lambda v: (
                v["width"] * v["height"],
                v["height"],
                v["width"],
                v["bandwidth"]
            )
        )

        if best["width"] and best["height"]:
            description = f"{best['width']}x{best['height']}"

        elif best["bandwidth"]:
            description = (
                f"débit {best['bandwidth'] // 1000} kbit/s "
                "(résolution non indiquée)"
            )

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

        # Les métadonnées sont passées comme arguments séparés.
        for key, value in item.get("metadata", []):
            if key.strip():
                cmd += ["-metadata", f"{key.strip()}={value}"]

        if item["format"] == "mp4":
            cmd += ["-movflags", "+faststart"]

        cmd += [item["output"]]

        print("=== COMMANDE FFMPEG ===")
        print(repr(cmd))

        return cmd
