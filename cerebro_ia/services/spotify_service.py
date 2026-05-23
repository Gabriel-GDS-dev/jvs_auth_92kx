from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import unicodedata
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import requests

from core.config import CACHE_DIR


class SpotifyAuthError(RuntimeError):
    pass


class SpotifyService:
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_URL = "https://api.spotify.com/v1"
    DEFAULT_SCOPES = (
        "user-read-playback-state "
        "user-read-currently-playing "
        "user-modify-playback-state "
        "user-read-private "
        "playlist-read-private"
    )

    def __init__(self, token_cache: Path | None = None):
        configured_cache = (os.getenv("SPOTIFY_TOKEN_CACHE") or "").strip()
        if configured_cache:
            cache_path = Path(configured_cache).expanduser()
            if not cache_path.is_absolute():
                cache_path = CACHE_DIR.parent / cache_path
            self.token_cache = cache_path
        else:
            self.token_cache = token_cache or (CACHE_DIR / "spotify_token_cache.json")
        self.timeout = 20

    @property
    def client_id(self) -> str:
        return (os.getenv("SPOTIFY_CLIENT_ID") or "").strip()

    @property
    def client_secret(self) -> str:
        return (os.getenv("SPOTIFY_CLIENT_SECRET") or "").strip()

    @property
    def redirect_uri(self) -> str:
        return (os.getenv("SPOTIFY_REDIRECT_URI") or "http://127.0.0.1:8888/callback").strip()

    @property
    def auth_flow(self) -> str:
        return (os.getenv("SPOTIFY_AUTH_FLOW") or "pkce").strip().lower()

    @property
    def uses_client_secret(self) -> bool:
        return self.auth_flow in {"authorization_code", "code", "secret"}

    @property
    def default_device_id(self) -> str:
        return (os.getenv("SPOTIFY_DEVICE_ID") or "").strip()

    @property
    def market(self) -> str:
        return (os.getenv("SPOTIFY_MARKET") or "BR").strip().upper()

    @property
    def scopes(self) -> str:
        return (os.getenv("SPOTIFY_SCOPES") or self.DEFAULT_SCOPES).strip()

    def _require_config(self) -> None:
        if not self.client_id:
            raise SpotifyAuthError("Spotify nao configurado. Defina SPOTIFY_CLIENT_ID no .env.")
        if self.uses_client_secret and not self.client_secret:
            raise SpotifyAuthError(
                "SPOTIFY_AUTH_FLOW usa Client Secret. Defina SPOTIFY_CLIENT_SECRET ou use SPOTIFY_AUTH_FLOW=pkce."
            )

    def authenticate(self, timeout_seconds: int = 180) -> str:
        try:
            self._require_config()
            parsed = urllib.parse.urlparse(self.redirect_uri)
            if parsed.hostname != "127.0.0.1":
                return (
                    "SPOTIFY_REDIRECT_URI deve usar loopback literal, por exemplo "
                    "http://127.0.0.1:8888/callback. O Spotify nao aceita localhost."
                )

            port = parsed.port or 8888
            path = parsed.path or "/callback"
            state = secrets.token_urlsafe(24)
            verifier = secrets.token_urlsafe(64)
            result: dict[str, str] = {}

            class CallbackHandler(BaseHTTPRequestHandler):
                def log_message(self, format: str, *args: object) -> None:
                    return

                def do_GET(self) -> None:  # noqa: N802 - stdlib API
                    request_path = urllib.parse.urlparse(self.path).path
                    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    if request_path != path:
                        self.send_response(404)
                        self.end_headers()
                        return
                    if query.get("state", [""])[0] != state:
                        result["error"] = "state_mismatch"
                    elif "error" in query:
                        result["error"] = query["error"][0]
                    else:
                        result["code"] = query.get("code", [""])[0]

                    ok = "code" in result and "error" not in result
                    title = "Spotify conectado ao Jarvis" if ok else "Falha ao conectar Spotify"
                    body = "Voce ja pode fechar esta aba." if ok else "Volte ao Jarvis para ver o erro."
                    html = (
                        "<html><body style='font-family: Segoe UI, Arial; padding: 32px;'>"
                        f"<h1>{title}</h1><p>{body}</p></body></html>"
                    ).encode("utf-8")
                    self.send_response(200 if ok else 400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.end_headers()
                    self.wfile.write(html)

            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), CallbackHandler)
            except OSError as exc:
                return (
                    f"Nao consegui abrir o callback local do Spotify na porta {port}: {exc}. "
                    "Troque a porta em SPOTIFY_REDIRECT_URI e cadastre a mesma URL no Spotify Dashboard."
                )

            server.timeout = 1
            auth_url = self._authorization_url(state, verifier)
            webbrowser.open(auth_url)

            deadline = time.time() + max(30, timeout_seconds)
            try:
                while time.time() < deadline and "code" not in result and "error" not in result:
                    server.handle_request()
            finally:
                server.server_close()

            if result.get("error"):
                return f"Autenticacao do Spotify falhou: {result['error']}."
            if not result.get("code"):
                return "Tempo esgotado aguardando login do Spotify."

            self._exchange_code(result["code"], verifier)
            return "Spotify autenticado e token salvo. Pronto para controlar musica."
        except SpotifyAuthError as exc:
            return f"Erro no Spotify: {exc}"
        except requests.RequestException as exc:
            return f"Erro de rede ao autenticar Spotify: {exc}"
        except Exception as exc:
            return f"Erro inesperado ao autenticar Spotify: {exc}"

    def devices(self) -> str:
        try:
            data = self._request("GET", "/me/player/devices")
            devices = data.get("devices", []) if isinstance(data, dict) else []
            if not devices:
                return "Nenhum dispositivo Spotify encontrado. Abra o app Spotify em algum dispositivo."

            lines = ["Dispositivos Spotify:"]
            for device in devices:
                active = "ativo" if device.get("is_active") else "inativo"
                restricted = ", restrito" if device.get("is_restricted") else ""
                volume = device.get("volume_percent")
                volume_text = f", volume {volume}%" if volume is not None else ""
                lines.append(
                    f"- {device.get('name')} ({device.get('type')}, {active}{restricted}{volume_text}) id={device.get('id')}"
                )
            return "\n".join(lines)
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def search_tracks(self, query: str, limit: int = 5) -> str:
        query = str(query).strip()
        if not query:
            return "Informe uma busca para o Spotify."
        try:
            data = self._search(query, "track", limit)
            items = data.get("tracks", {}).get("items", []) if isinstance(data, dict) else []
            if not items:
                return f"Nenhuma musica encontrada para: {query}."
            lines = []
            for idx, item in enumerate(items, start=1):
                artists = ", ".join(artist["name"] for artist in item.get("artists", []))
                lines.append(f"{idx}. {item.get('name')} - {artists} | uri={item.get('uri')}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def play(self, query: str = "", uri: str = "", item_type: str = "musica") -> str:
        query = str(query or "").strip()
        uri = str(uri or "").strip()
        try:
            if not query and not uri:
                return self.resume()

            kind, selected_uri, description = self._resolve_play_target(query, uri, item_type)
            device_id = self._active_or_first_device_id()
            if not device_id:
                return "Nenhum dispositivo Spotify encontrado. Abra o Spotify no PC/celular e tente de novo."

            body: dict[str, Any]
            if kind == "track":
                body = {"uris": [selected_uri]}
            else:
                body = {"context_uri": selected_uri}

            self._request(
                "PUT",
                "/me/player/play",
                params={"device_id": device_id},
                json_body=body,
                expected=(204,),
            )
            return f"Tocando no Spotify: {description}."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def pause(self) -> str:
        try:
            self._request("PUT", "/me/player/pause", params=self._device_params(), expected=(204,))
            return "Spotify pausado."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def resume(self) -> str:
        try:
            device_id = self._active_or_first_device_id()
            if not device_id:
                return "Nenhum dispositivo Spotify encontrado. Abra o Spotify no PC/celular e tente de novo."
            params = {"device_id": device_id}
            self._request("PUT", "/me/player/play", params=params, expected=(204,))
            return "Spotify reproduzindo."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def next_track(self) -> str:
        try:
            self._request("POST", "/me/player/next", params=self._device_params(), expected=(204,))
            return "Pulando para a proxima musica no Spotify."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def previous_track(self) -> str:
        try:
            self._request("POST", "/me/player/previous", params=self._device_params(), expected=(204,))
            return "Voltando para a musica anterior no Spotify."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def volume(self, percent: int) -> str:
        try:
            value = max(0, min(int(percent), 100))
            params = self._device_params()
            params["volume_percent"] = value
            self._request(
                "PUT",
                "/me/player/volume",
                params=params,
                expected=(204,),
            )
            return f"Volume do Spotify ajustado para {value}%."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def shuffle(self, enabled: bool) -> str:
        try:
            params = self._device_params()
            params["state"] = str(bool(enabled)).lower()
            self._request(
                "PUT",
                "/me/player/shuffle",
                params=params,
                expected=(204,),
            )
            return "Modo aleatorio do Spotify ligado." if enabled else "Modo aleatorio do Spotify desligado."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def repeat(self, mode: str) -> str:
        try:
            normalized = self._normalize(mode)
            mapped = {
                "musica": "track",
                "faixa": "track",
                "track": "track",
                "contexto": "context",
                "playlist": "context",
                "album": "context",
                "context": "context",
                "off": "off",
                "desligado": "off",
                "desligar": "off",
            }.get(normalized)
            if not mapped:
                return "Use modo de repeticao: musica, playlist/album ou desligado."
            params = self._device_params()
            params["state"] = mapped
            self._request("PUT", "/me/player/repeat", params=params, expected=(204,))
            return f"Repeticao do Spotify ajustada para {mapped}."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    def current(self) -> str:
        try:
            data = self._request("GET", "/me/player/currently-playing", expected=(200, 204))
            if not data or not data.get("item"):
                return "Nada tocando no Spotify agora."
            item = data["item"]
            item_type = data.get("currently_playing_type") or item.get("type")
            status = "tocando" if data.get("is_playing") else "pausado"
            if item_type == "track":
                description = self._describe_item("track", item)
            else:
                description = item.get("name") or str(item_type)
            return f"Agora no Spotify ({status}): {description}."
        except Exception as exc:
            return f"Erro no Spotify: {exc}"

    @staticmethod
    def spotify_uri_from_input(value: str) -> tuple[str, str] | None:
        text = str(value).strip()
        if text.startswith("spotify:"):
            parts = text.split(":")
            if len(parts) >= 3 and parts[1] in {"track", "album", "artist", "playlist"}:
                return parts[1], ":".join(parts[:3])
            return None

        parsed = urllib.parse.urlparse(text)
        if "open.spotify.com" not in parsed.netloc:
            return None
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"track", "album", "artist", "playlist"}:
            return path_parts[0], f"spotify:{path_parts[0]}:{path_parts[1]}"
        return None

    def _authorization_url(self, state: str, verifier: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        if not self.uses_client_secret:
            params["code_challenge_method"] = "S256"
            params["code_challenge"] = self._code_challenge(verifier)
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _exchange_code(self, code: str, verifier: str) -> dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        headers: dict[str, str] = {}
        if self.uses_client_secret:
            headers["Authorization"] = self._basic_auth_header()
        else:
            data["client_id"] = self.client_id
            data["code_verifier"] = verifier

        response = requests.post(self.TOKEN_URL, data=data, headers=headers, timeout=self.timeout)
        if response.status_code >= 400:
            raise SpotifyAuthError(self._response_error(response))
        token = response.json()
        self._write_token(token)
        return token

    def _refresh_token(self, refresh_token: str) -> dict[str, Any]:
        data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        headers: dict[str, str] = {}
        if self.uses_client_secret:
            headers["Authorization"] = self._basic_auth_header()
        else:
            data["client_id"] = self.client_id

        response = requests.post(self.TOKEN_URL, data=data, headers=headers, timeout=self.timeout)
        if response.status_code >= 400:
            raise SpotifyAuthError("Token do Spotify expirou ou foi revogado. Rode spotify_autenticar.")
        token = response.json()
        token["refresh_token"] = token.get("refresh_token") or refresh_token
        self._write_token(token)
        return token

    def access_token(self) -> str:
        self._require_config()
        token = self._read_token()
        if not token:
            raise SpotifyAuthError("Spotify ainda nao autenticado. Diga: autenticar Spotify.")
        if int(token.get("expires_at", 0)) <= int(time.time()):
            refresh = str(token.get("refresh_token") or "")
            if not refresh:
                raise SpotifyAuthError("Sessao Spotify sem refresh token. Rode spotify_autenticar.")
            token = self._refresh_token(refresh)
        return str(token["access_token"])

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
        retry: bool = True,
    ) -> Any:
        token = self.access_token()
        response = requests.request(
            method,
            f"{self.API_URL}{path}",
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if response.status_code == 401 and retry:
            cached = self._read_token() or {}
            refresh = cached.get("refresh_token")
            if refresh:
                self._refresh_token(str(refresh))
                return self._request(
                    method,
                    path,
                    params=params,
                    json_body=json_body,
                    expected=expected,
                    retry=False,
                )
        if response.status_code in expected:
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        raise RuntimeError(self._response_error(response))

    def _search(self, query: str, item_type: str, limit: int = 1) -> Any:
        return self._request(
            "GET",
            "/search",
            params={
                "q": query,
                "type": item_type,
                "limit": max(1, min(int(limit), 10)),
                "market": self.market,
            },
        )

    def _resolve_play_target(self, query: str, uri: str, item_type: str) -> tuple[str, str, str]:
        direct = self.spotify_uri_from_input(uri or query)
        if direct:
            kind, selected_uri = direct
            return kind, selected_uri, selected_uri

        kind = self._normalize_item_type(item_type)
        data = self._search(query, kind, 1)
        response_key = {
            "track": "tracks",
            "album": "albums",
            "artist": "artists",
            "playlist": "playlists",
        }[kind]
        items = data.get(response_key, {}).get("items", []) if isinstance(data, dict) else []
        items = [item for item in items if item]
        if not items:
            raise RuntimeError(f"Nao encontrei {item_type} no Spotify para: {query}.")
        item = items[0]
        selected_uri = item.get("uri")
        if not selected_uri:
            raise RuntimeError("O resultado do Spotify nao retornou uma URI tocavel.")
        return kind, selected_uri, self._describe_item(kind, item)

    def _active_or_first_device_id(self) -> str | None:
        if self.default_device_id:
            return self.default_device_id
        data = self._request("GET", "/me/player/devices")
        devices = data.get("devices", []) if isinstance(data, dict) else []
        if not devices:
            return None
        for device in devices:
            if device.get("is_active") and device.get("id"):
                return str(device["id"])
        for device in devices:
            if device.get("id") and not device.get("is_restricted"):
                return str(device["id"])
        return None

    def _device_params(self) -> dict[str, Any]:
        return {"device_id": self.default_device_id} if self.default_device_id else {}

    def _read_token(self) -> dict[str, Any] | None:
        if not self.token_cache.exists():
            return None
        try:
            data = json.loads(self.token_cache.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _write_token(self, token: dict[str, Any]) -> None:
        self.token_cache.parent.mkdir(parents=True, exist_ok=True)
        current = self._read_token() or {}
        merged = {**current, **token}
        merged["expires_at"] = int(time.time()) + int(merged.get("expires_in", 3600)) - 60
        self.token_cache.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _basic_auth_header(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @staticmethod
    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value).strip().lower())
        return "".join(char for char in text if not unicodedata.combining(char))

    def _normalize_item_type(self, item_type: str) -> str:
        mapping = {
            "musica": "track",
            "music": "track",
            "track": "track",
            "faixa": "track",
            "album": "album",
            "artista": "artist",
            "artist": "artist",
            "playlist": "playlist",
            "lista": "playlist",
        }
        return mapping.get(self._normalize(item_type), "track")

    def _describe_item(self, kind: str, item: dict[str, Any]) -> str:
        name = item.get("name") or "Sem titulo"
        if kind in {"track", "album"}:
            artists = ", ".join(
                artist.get("name", "")
                for artist in item.get("artists", [])
                if artist.get("name")
            )
            return f"{name} - {artists}" if artists else str(name)
        owner = item.get("owner", {}).get("display_name") if kind == "playlist" else ""
        return f"{name} - {owner}" if owner else str(name)

    def _response_error(self, response: requests.Response) -> str:
        message = response.text.strip()
        try:
            data = response.json()
            error = data.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("reason") or message
            elif isinstance(error, str):
                message = data.get("error_description") or error
        except ValueError:
            pass

        if response.status_code == 401:
            return "Autenticacao Spotify invalida ou expirada. Rode spotify_autenticar novamente."
        if response.status_code == 403:
            return (
                "Spotify recusou o comando. Controle de playback normalmente exige Spotify Premium, "
                "scopes aprovados e um dispositivo Spotify Connect controlavel."
            )
        if response.status_code == 404:
            return "Nenhum player Spotify ativo. Abra o Spotify no PC/celular e tente de novo."
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait = f" Aguarde {retry_after}s." if retry_after else ""
            return f"Limite de requisicoes do Spotify atingido.{wait}"
        return f"Erro Spotify {response.status_code}: {message or 'sem detalhe'}"
