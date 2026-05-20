# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape

from dotenv import load_dotenv


def _load_env_files() -> None:
    current_dir = Path(__file__).resolve().parent
    load_dotenv(current_dir / ".env")

    for parent in current_dir.parents:
        shared_env = parent / "cerebro_ia" / ".env"
        if shared_env.exists():
            load_dotenv(shared_env, override=False)
            break


_load_env_files()


def abrir_caminho(caminho: str | Path) -> None:
    subprocess.Popen(["cmd", "/c", "start", "", str(caminho)], shell=False)


def _safe_filename(nome: str, default: str = "nota") -> str:
    limpo = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(nome)).strip()
    limpo = re.sub(r"\s+", " ", limpo)
    return limpo or default


def _clipboard_copy(texto: str) -> bool:
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(texto)
        return True
    except Exception:
        pass

    try:
        subprocess.run(
            ["cmd", "/c", "clip"],
            input=texto,
            text=True,
            encoding="utf-8",
            check=True,
            capture_output=True,
        )
        return True
    except Exception:
        return False


class DesktopInteractor:
    def abrir_site(self, url: str) -> str:
        url = str(url).strip()
        if not url:
            return "Informe uma URL para abrir."
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            url = "https://" + url
        abrir_caminho(url)
        return f"Abrindo site: {url}"

    def digitar_na_tela(
        self,
        texto: str,
        limpar_campo: bool = False,
        pressionar_enter: bool = False,
        pausa: float = 0.1,
    ) -> str:
        try:
            import pyautogui

            time.sleep(max(0, float(pausa)))
            if limpar_campo:
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)

            if _clipboard_copy(texto):
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.write(texto, interval=0.01)

            if pressionar_enter:
                pyautogui.press("enter")
            return "Texto enviado para a janela ativa."
        except Exception as exc:
            return f"Erro ao digitar na tela: {exc}"

    def pressionar_teclas(self, teclas: str) -> str:
        try:
            import pyautogui

            partes = [p.strip().lower() for p in re.split(r"[+,]", teclas) if p.strip()]
            if not partes:
                return "Informe uma tecla ou atalho."
            if len(partes) == 1:
                pyautogui.press(partes[0])
            else:
                pyautogui.hotkey(*partes)
            return f"Atalho executado: {'+'.join(partes)}"
        except Exception as exc:
            return f"Erro ao pressionar teclas: {exc}"

    def clicar_na_tela(self, x: int, y: int, duplo: bool = False) -> str:
        try:
            import pyautogui

            pyautogui.click(int(x), int(y), clicks=2 if duplo else 1)
            return f"Clique executado em ({x}, {y})."
        except Exception as exc:
            return f"Erro ao clicar na tela: {exc}"


class ScreenVisionService:
    def __init__(self, runtime_dir: str | Path):
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def capturar_tela(self, caminho: str | None = None) -> dict[str, Any]:
        destino = Path(caminho) if caminho else self.runtime_dir / "jarvis_tela.png"
        destino.parent.mkdir(parents=True, exist_ok=True)

        try:
            import pyautogui

            imagem = pyautogui.screenshot()
        except Exception:
            from PIL import ImageGrab

            imagem = ImageGrab.grab()

        imagem.save(destino)
        largura, altura = imagem.size
        return {"path": str(destino), "width": largura, "height": altura}

    def analisar_tela(self, pergunta: str = "") -> str:
        captura = self.capturar_tela()
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return (
                "Screenshot salvo, mas nao encontrei GEMINI_API_KEY/GOOGLE_API_KEY "
                f"para analisar a imagem: {captura['path']}"
            )

        prompt = pergunta.strip() or (
            "Descreva objetivamente o que esta visivel na tela. "
            "Aponte botoes, campos, janelas abertas e a proxima acao util."
        )

        try:
            from google import genai # type: ignore
            from google.genai import types

            with open(captura["path"], "rb") as image_file:
                image_bytes = image_file.read()

            client = genai.Client(api_key=api_key)
            model = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
            image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            response = client.models.generate_content(
                model=model,
                contents=[prompt, image_part],
            )
            texto = getattr(response, "text", "") or str(response)
            return f"Analise da tela:\n{texto}\n\nScreenshot: {captura['path']}"
        except Exception as exc:
            return (
                "Capturei a tela, mas nao consegui enviar para analise visual. "
                f"Arquivo: {captura['path']} | Erro: {exc}"
            )


class ObsidianService:
    def __init__(self, home: str | Path):
        self.home = Path(home)
        self.vault_path = self._get_vault_path()
        self.vault_name = os.getenv("OBSIDIAN_VAULT_NAME") or (
            self.vault_path.name if self.vault_path else ""
        )

    def _get_vault_path(self) -> Path | None:
        configured = os.getenv("OBSIDIAN_VAULT_PATH")
        if configured:
            path = Path(configured).expanduser()
            return path if path.exists() else path

        candidates = [
            self.home / "Documents",
            self.home / "OneDrive" / "Documents",
            self.home / "OneDrive" / "Documentos",
            self.home / "Desktop",
        ]
        for base in candidates:
            if not base.exists():
                continue
            for possible in base.rglob(".obsidian"):
                if possible.is_dir():
                    return possible.parent
        return None

    def _require_vault(self) -> Path:
        if not self.vault_path:
            raise RuntimeError(
                "Vault do Obsidian nao encontrado. Defina OBSIDIAN_VAULT_PATH no .env."
            )
        self.vault_path.mkdir(parents=True, exist_ok=True)
        return self.vault_path

    def _note_path(self, titulo: str, pasta: str = "") -> Path:
        vault = self._require_vault()
        filename = _safe_filename(titulo)
        if not filename.lower().endswith(".md"):
            filename += ".md"
        folder = Path(_safe_filename(pasta, "")) if pasta.strip() else Path()
        return vault / folder / filename

    def criar_nota(self, titulo: str, conteudo: str = "", pasta: str = "") -> str:
        try:
            path = self._note_path(titulo, pasta)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not conteudo.strip():
                conteudo = f"# {titulo}\n\n"
            path.write_text(conteudo, encoding="utf-8")
            return f"Nota criada no Obsidian: {path}"
        except Exception as exc:
            return f"Erro ao criar nota no Obsidian: {exc}"

    def adicionar_em_nota(self, titulo: str, conteudo: str, pasta: str = "") -> str:
        try:
            path = self._note_path(titulo, pasta)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(f"# {titulo}\n\n", encoding="utf-8")
            with path.open("a", encoding="utf-8") as note:
                note.write(f"\n{conteudo.strip()}\n")
            return f"Conteudo adicionado no Obsidian: {path}"
        except Exception as exc:
            return f"Erro ao adicionar conteudo no Obsidian: {exc}"

    def buscar_notas(self, termo: str, limite: int = 10) -> str:
        try:
            vault = self._require_vault()
            termo_lower = termo.lower()
            resultados: list[str] = []
            for path in vault.rglob("*.md"):
                if len(resultados) >= max(1, int(limite)):
                    break
                rel = path.relative_to(vault)
                texto = path.read_text(encoding="utf-8", errors="ignore")
                if termo_lower in rel.as_posix().lower() or termo_lower in texto.lower():
                    resultados.append(f"- {rel}")
            return "\n".join(resultados) if resultados else "Nenhuma nota encontrada."
        except Exception as exc:
            return f"Erro ao buscar notas no Obsidian: {exc}"

    def abrir_nota(self, titulo: str, pasta: str = "") -> str:
        try:
            path = self._note_path(titulo, pasta)
            if not path.exists():
                return f"Nota nao encontrada: {path}"

            if self.vault_name:
                rel = path.relative_to(self._require_vault()).as_posix()
                uri = f"obsidian://open?vault={quote(self.vault_name)}&file={quote(rel)}"
                abrir_caminho(uri)
            else:
                abrir_caminho(path)
            return f"Abrindo nota: {path}"
        except Exception as exc:
            return f"Erro ao abrir nota do Obsidian: {exc}"


class NotionService:
    def __init__(self, desktop: DesktopInteractor):
        self.desktop = desktop

    def abrir_notion(self) -> str:
        return self.desktop.abrir_site(os.getenv("NOTION_URL", "https://www.notion.so"))

    def criar_pagina(self, titulo: str, conteudo: str = "", parent_page_id: str = "") -> str:
        token = os.getenv("NOTION_API_KEY")
        parent = parent_page_id or os.getenv("NOTION_PARENT_PAGE_ID", "")
        if not token or not parent:
            self.abrir_notion()
            if titulo:
                texto = titulo if not conteudo else f"{titulo}\n\n{conteudo}"
                self.desktop.digitar_na_tela(texto)
            return (
                "Notion aberto. Para criar paginas automaticamente via API, defina "
                "NOTION_API_KEY e NOTION_PARENT_PAGE_ID no .env."
            )

        try:
            import requests

            children = []
            for line in conteudo.splitlines() or [""]:
                if not line.strip():
                    continue
                children.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": line[:1900]}}]
                        },
                    }
                )

            payload = {
                "parent": {"page_id": parent},
                "properties": {
                    "title": {
                        "title": [{"type": "text", "text": {"content": titulo[:1900]}}]
                    }
                },
                "children": children[:90],
            }
            response = requests.post(
                "https://api.notion.com/v1/pages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload),
                timeout=20,
            )
            if response.status_code >= 400:
                return f"Erro na API do Notion ({response.status_code}): {response.text[:500]}"
            data = response.json()
            return f"Pagina criada no Notion: {data.get('url', data.get('id'))}"
        except Exception as exc:
            return f"Erro ao criar pagina no Notion: {exc}"


class WordService:
    def __init__(self, documents_dir: str | Path):
        self.documents_dir = Path(documents_dir)

    def criar_documento(self, titulo: str, conteudo: str = "", caminho: str = "") -> str:
        try:
            if caminho:
                path = Path(caminho).expanduser()
            else:
                filename = _safe_filename(titulo)
                if not filename.lower().endswith(".docx"):
                    filename += ".docx"
                path = self.documents_dir / filename
            path.parent.mkdir(parents=True, exist_ok=True)

            paragraphs = [titulo.strip()] + [p for p in conteudo.splitlines()]
            self._write_docx(path, paragraphs)
            abrir_caminho(path)
            return f"Documento Word criado e aberto: {path}"
        except Exception as exc:
            return f"Erro ao criar documento Word: {exc}"

    def _write_docx(self, path: Path, paragraphs: list[str]) -> None:
        body = "\n".join(self._paragraph_xml(p) for p in paragraphs if p is not None)
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}<w:sectPr/></w:body></w:document>"
        )

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as docx:
            docx.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>",
            )
            docx.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="word/document.xml"/>'
                "</Relationships>",
            )
            docx.writestr("word/document.xml", document_xml)

    def _paragraph_xml(self, text: str) -> str:
        return f"<w:p><w:r><w:t>{escape(str(text))}</w:t></w:r></w:p>"


def runtime_dir() -> Path:
    base = os.getenv("JARVIS_RUNTIME_DIR")
    if base:
        root = Path(base)
    else:
        root = Path(__file__).resolve().parent / ".runtime"
    stamp = datetime.now().strftime("%Y%m%d")
    path = root / "jarvis" / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path
