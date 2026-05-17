from __future__ import annotations

import os
import re
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests
from dotenv import load_dotenv


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
MAX_SIMPLE_UPLOAD_BYTES = 250 * 1024 * 1024
RESERVED_SCOPES = {"offline_access", "openid", "profile"}


def _load_env_files() -> None:
    current_dir = Path(__file__).resolve().parent
    load_dotenv(current_dir / ".env")

    for parent in [current_dir, *current_dir.parents]:
        shared_env = parent / "Jarvis- Aula 01" / ".env"
        if shared_env.exists():
            load_dotenv(shared_env, override=False)
            break


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_name(name: str, default: str = "Novo item") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(name)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or default


class OneDriveService:
    def __init__(self, project_dir: str | Path, downloads_dir: str | Path | None = None):
        _load_env_files()
        self.project_dir = Path(project_dir).resolve()
        self.downloads_dir = Path(downloads_dir).expanduser() if downloads_dir else Path.home() / "Downloads"
        self.client_id = os.getenv("ONEDRIVE_CLIENT_ID", "").strip()
        self.tenant_id = os.getenv("ONEDRIVE_TENANT_ID", "consumers").strip() or "consumers"
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = self._scopes()
        self.token_cache_path = self._token_cache_path()
        self.auth_flow = os.getenv("ONEDRIVE_AUTH_FLOW", "device_code").strip().lower()

    def _scopes(self) -> list[str]:
        configured = os.getenv("ONEDRIVE_SCOPES", "")
        if configured.strip():
            return [
                scope
                for scope in configured.replace(",", " ").split()
                if scope and scope not in RESERVED_SCOPES
            ]
        return ["Files.ReadWrite.All", "User.Read"]

    def _token_cache_path(self) -> Path:
        configured = os.getenv("ONEDRIVE_TOKEN_CACHE", "").strip()
        if configured:
            path = Path(configured).expanduser()
            if not path.is_absolute():
                path = self.project_dir / path
            return path
        return self.project_dir / "onedrive_token_cache.bin"

    def _missing_config_message(self) -> str:
        return (
            "OneDrive ainda nao esta configurado. Crie um app no Microsoft Entra, "
            "copie o Application (client) ID e defina ONEDRIVE_CLIENT_ID no .env. "
            "Depois reinicie o Jarvis e chame onedrive_autenticar."
        )

    def _require_client_id(self) -> None:
        if not self.client_id:
            raise RuntimeError(self._missing_config_message())

    def _create_msal_app(self) -> tuple[Any, Any]:
        try:
            import msal  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Dependencia msal nao instalada. Rode: pip install msal"
            ) from exc

        cache = msal.SerializableTokenCache()
        if self.token_cache_path.exists():
            cache.deserialize(self.token_cache_path.read_text(encoding="utf-8"))

        app = msal.PublicClientApplication(
            self.client_id,
            authority=self.authority,
            token_cache=cache,
        )
        return app, cache

    def _save_cache(self, cache: Any) -> None:
        if getattr(cache, "has_state_changed", False):
            self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_cache_path.write_text(cache.serialize(), encoding="utf-8")

    def _interactive_port(self) -> int | None:
        configured_port = os.getenv("ONEDRIVE_REDIRECT_PORT", "").strip()
        if configured_port:
            try:
                return int(configured_port)
            except ValueError:
                return None

        redirect_uri = os.getenv("ONEDRIVE_REDIRECT_URI", "").strip()
        if redirect_uri:
            parsed = urlparse(redirect_uri)
            return parsed.port
        return None

    def _format_auth_error(self, result: Any) -> str:
        if not isinstance(result, dict):
            return str(result)

        description = result.get("error_description") or result.get("error") or str(result)
        lowered = str(description).lower()

        if "aadsts700016" in lowered or "application with identifier" in lowered:
            return (
                f"{description}\n\n"
                "O Application (client) ID nao foi encontrado para esse tipo de conta/tenant. "
                "Confira se ONEDRIVE_CLIENT_ID e o Application (client) ID do app Jarvis OneDrive sao identicos. "
                "Para conta pessoal, use ONEDRIVE_TENANT_ID=consumers e o app precisa aceitar Personal Microsoft accounts. "
                "Para conta corporativa/escolar, use ONEDRIVE_TENANT_ID=organizations ou o Tenant ID da organizacao."
            )

        if "aadsts50020" in lowered or "use your work or school account" in lowered:
            return (
                f"{description}\n\n"
                "A conta usada nao combina com o Supported account types do app. "
                "Se voce quer OneDrive pessoal, configure o app para Personal Microsoft accounts "
                "ou Accounts in any organizational directory and personal Microsoft accounts. "
                "Se quer OneDrive corporativo, troque ONEDRIVE_TENANT_ID para organizations ou para o Tenant ID correto."
            )

        if "public client" in lowered or "unauthorized_client" in lowered:
            return (
                f"{description}\n\n"
                "O app precisa ser um cliente publico. No App Registration, em Authentication, "
                "adicione a plataforma Mobile and desktop applications e ative Allow public client flows."
            )

        if "aadsts70002" in lowered or "must be marked as 'mobile'" in lowered:
            return (
                f"{description}\n\n"
                "O App Registration foi encontrado, mas nao esta marcado como app Mobile/Desktop. "
                "No Azure, abra Authentication, clique em Add a platform, escolha Mobile and desktop applications, "
                "adicione http://localhost e salve. Depois ative Allow public client flows."
            )

        return str(description)

    def _acquire_interactive_token(self, app: Any) -> dict[str, Any]:
        port = self._interactive_port()
        kwargs: dict[str, Any] = {
            "scopes": self.scopes,
            "timeout": 300,
            "prompt": "select_account",
        }
        if port:
            kwargs["port"] = port
        if self.tenant_id in {"consumers", "organizations"}:
            kwargs["domain_hint"] = self.tenant_id
        return app.acquire_token_interactive(**kwargs)

    def _acquire_device_code_token(self, app: Any) -> dict[str, Any]:
        flow = app.initiate_device_flow(scopes=self.scopes)
        if "user_code" not in flow:
            raise RuntimeError(
                "Falha ao iniciar login do OneDrive: "
                + self._format_auth_error(flow)
            )

        message = flow.get("message", "")
        verification_uri = flow.get("verification_uri") or flow.get("verification_uri_complete")
        print(message)
        if verification_uri and _env_flag("ONEDRIVE_OPEN_BROWSER", True):
            webbrowser.open(verification_uri)

        return app.acquire_token_by_device_flow(flow)

    def _access_token(self, interactive: bool = True) -> str:
        self._require_client_id()
        app, cache = self._create_msal_app()
        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(self.scopes, account=accounts[0])

        if not result and interactive:
            if self.auth_flow in {"interactive", "browser", "localhost"}:
                result = self._acquire_interactive_token(app)
            else:
                result = self._acquire_device_code_token(app)

        self._save_cache(cache)

        if not result or "access_token" not in result:
            raise RuntimeError(
                "Nao foi possivel autenticar no OneDrive: "
                + self._format_auth_error(result)
            )

        return result["access_token"]

    def autenticar(self) -> str:
        token = self._access_token(interactive=True)
        return "OneDrive autenticado com sucesso." if token else "Falha ao autenticar OneDrive."

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        if extra:
            headers.update(extra)
        return headers

    def _graph_url(self, endpoint: str) -> str:
        return GRAPH_ROOT + endpoint

    def _graph_error(self, response: requests.Response) -> str:
        try:
            payload = response.json()
            error = payload.get("error", {})
            message = error.get("message") or payload
        except Exception:
            message = response.text[:700]
        return f"Microsoft Graph retornou {response.status_code}: {message}"

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_body: Any = None,
        data: bytes | str | None = None,
        headers: dict[str, str] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> requests.Response:
        request_headers = self._headers(headers)
        if json_body is not None:
            request_headers["Content-Type"] = "application/json"

        response = requests.request(
            method,
            self._graph_url(endpoint),
            headers=request_headers,
            json=json_body,
            data=data,
            timeout=90,
            allow_redirects=True,
        )
        if response.status_code not in expected:
            raise RuntimeError(self._graph_error(response))
        return response

    @staticmethod
    def _drive_path(path: str = "") -> str:
        normalized = str(path or "").strip().strip("\"'")
        normalized = normalized.replace("\\", "/").strip("/")
        normalized = re.sub(r"/+", "/", normalized)
        return "" if normalized in {"", "."} else normalized

    @classmethod
    def _encoded_path(cls, path: str = "") -> str:
        normalized = cls._drive_path(path)
        if not normalized:
            return ""
        return "/".join(quote(part, safe="") for part in normalized.split("/"))

    def _item_endpoint(self, path: str = "") -> str:
        encoded = self._encoded_path(path)
        return "/me/drive/root" if not encoded else f"/me/drive/root:/{encoded}:"

    def _children_endpoint(self, path: str = "") -> str:
        encoded = self._encoded_path(path)
        return "/me/drive/root/children" if not encoded else f"/me/drive/root:/{encoded}:/children"

    def _content_endpoint(self, path: str) -> str:
        encoded = self._encoded_path(path)
        if not encoded:
            raise ValueError("Informe o caminho de um arquivo no OneDrive.")
        return f"/me/drive/root:/{encoded}:/content"

    @staticmethod
    def _item_kind(item: dict[str, Any]) -> str:
        if "folder" in item:
            return "pasta"
        if "file" in item:
            return "arquivo"
        return "item"

    def _format_item(self, item: dict[str, Any]) -> str:
        kind = self._item_kind(item)
        size = item.get("size", 0)
        modified = item.get("lastModifiedDateTime", "")
        name = item.get("name", "(sem nome)")
        return f"- {name} | {kind} | {size} bytes | modificado: {modified}"

    def listar(self, pasta: str = "", limite: int = 50) -> str:
        response = self._request("GET", self._children_endpoint(pasta))
        items = response.json().get("value", [])
        if not items:
            return "A pasta do OneDrive esta vazia ou nao foi encontrada."

        max_items = max(1, min(int(limite), 100))
        lines = [self._format_item(item) for item in items[:max_items]]
        if len(items) > max_items:
            lines.append(f"... mais {len(items) - max_items} item(ns).")
        return "\n".join(lines)

    def criar_pasta(self, nome: str, pasta_pai: str = "") -> str:
        body = {
            "name": _safe_name(nome, "Nova pasta"),
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename",
        }
        response = self._request(
            "POST",
            self._children_endpoint(pasta_pai),
            json_body=body,
            expected=(200, 201),
        )
        data = response.json()
        return f"Pasta criada no OneDrive: {data.get('name', nome)}"

    def criar_arquivo(self, caminho: str, conteudo: str = "", sobrescrever: bool = True) -> str:
        if not sobrescrever:
            metadata = self.obter_item(caminho, silencioso=True)
            if metadata:
                return f"Arquivo ja existe no OneDrive: {caminho}"

        data = str(conteudo or "").encode("utf-8")
        response = self._request(
            "PUT",
            self._content_endpoint(caminho),
            data=data,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            expected=(200, 201),
        )
        item = response.json()
        return f"Arquivo salvo no OneDrive: {item.get('name', caminho)} ({item.get('size', len(data))} bytes)"

    def ler_arquivo(self, caminho: str, limite_caracteres: int = 8000) -> str:
        response = self._request("GET", self._content_endpoint(caminho))
        content = response.content
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("cp1252")
            except UnicodeDecodeError:
                return (
                    "Arquivo baixado do OneDrive, mas parece ser binario. "
                    "Use onedrive_baixar_arquivo para salvar uma copia local."
                )

        limit = max(500, min(int(limite_caracteres), 30000))
        if len(text) > limit:
            return text[:limit] + f"\n\n... conteudo truncado ({len(text)} caracteres no total)."
        return text

    def obter_item(self, caminho: str, silencioso: bool = False) -> dict[str, Any] | None:
        try:
            response = self._request("GET", self._item_endpoint(caminho))
            return response.json()
        except Exception:
            if silencioso:
                return None
            raise

    def deletar_item(self, caminho: str, confirmar: bool = False) -> str:
        if not confirmar:
            return (
                "Para deletar do OneDrive, chame novamente com confirmar=True "
                "apenas se o usuario pediu explicitamente a exclusao."
            )
        self._request("DELETE", self._item_endpoint(caminho), expected=(204,))
        return f"Item deletado do OneDrive: {caminho}"

    def baixar_arquivo(self, caminho_onedrive: str, caminho_local: str = "") -> str:
        response = self._request("GET", self._content_endpoint(caminho_onedrive))
        if caminho_local:
            target = Path(caminho_local).expanduser()
            raw_target = str(caminho_local).strip().replace("\\", "/")
            if target.exists() and target.is_dir() or raw_target.endswith("/"):
                target = target / Path(self._drive_path(caminho_onedrive)).name
        else:
            target = self.downloads_dir / Path(self._drive_path(caminho_onedrive)).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return f"Arquivo baixado do OneDrive para: {target}"

    def enviar_arquivo(self, caminho_local: str, destino_onedrive: str = "") -> str:
        source = Path(caminho_local).expanduser()
        if not source.exists() or not source.is_file():
            return f"Arquivo local nao encontrado: {source}"
        size = source.stat().st_size
        if size > MAX_SIMPLE_UPLOAD_BYTES:
            return (
                "Este arquivo tem mais de 250 MB. A integracao atual usa upload simples; "
                "para arquivos maiores, implemente upload session."
            )
        raw_destination = str(destino_onedrive or "").strip().replace("\\", "/")
        if not raw_destination:
            target = source.name
        elif raw_destination.endswith("/"):
            folder = self._drive_path(raw_destination)
            target = f"{folder}/{source.name}" if folder else source.name
        else:
            target = self._drive_path(raw_destination)
        data = source.read_bytes()
        response = self._request(
            "PUT",
            self._content_endpoint(target),
            data=data,
            headers={"Content-Type": "application/octet-stream"},
            expected=(200, 201),
        )
        item = response.json()
        return f"Arquivo enviado para o OneDrive: {item.get('name', target)} ({item.get('size', size)} bytes)"

    def renomear_item(self, caminho: str, novo_nome: str) -> str:
        response = self._request(
            "PATCH",
            self._item_endpoint(caminho),
            json_body={"name": _safe_name(novo_nome)},
            expected=(200,),
        )
        item = response.json()
        return f"Item renomeado no OneDrive: {item.get('name', novo_nome)}"

    def buscar(self, termo: str, limite: int = 20) -> str:
        query = str(termo or "").strip().replace("'", " ")
        if not query:
            return "Informe um termo para buscar no OneDrive."
        encoded = quote(query, safe="")
        response = self._request("GET", f"/me/drive/root/search(q='{encoded}')")
        items = response.json().get("value", [])
        if not items:
            return "Nenhum item encontrado no OneDrive."
        max_items = max(1, min(int(limite), 50))
        return "\n".join(self._format_item(item) for item in items[:max_items])
