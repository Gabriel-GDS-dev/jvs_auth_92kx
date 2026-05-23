# pyright: reportMissingImports=false, reportMissingModuleSource=false
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    APIConnectOptions,
    AgentSession,
    Agent,
    ChatContext,
    NOT_GIVEN,
    room_io,
)
from livekit.plugins import noise_cancellation, google
from livekit.agents.voice.agent_session import VoiceActivityVideoSampler
from livekit.agents.utils import images as lk_images
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from mem0 import AsyncMemoryClient
import logging
import os
import asyncio
import webbrowser
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
import urllib.request as _urllib

try:
    import yt_dlp
    YT_DLP_DISPONIVEL = True
except ImportError:
    YT_DLP_DISPONIVEL = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_DISPONIVEL = True
except ImportError:
    PLAYWRIGHT_DISPONIVEL = False

from automacao_jarvis import JarvisControl
from core.config import canonicalize_gemini_environment
from core.session_memory import SessionMemory
from tools.ecosystem_tools import JarvisEcosystem

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env", override=True, encoding="utf-8-sig")
canonicalize_gemini_environment()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _apply_env_aliases() -> None:
    aliases = {
        "LIVETKIT_API_KEY": "LIVEKIT_API_KEY",
        "LIVETKIT_API_SECRET": "LIVEKIT_API_SECRET",
        "GOOGLE_CLOUD_PROJECT_LOCATION": "GOOGLE_CLOUD_LOCATION",
    }
    for source, target in aliases.items():
        value = os.getenv(source)
        if value and not os.getenv(target):
            os.environ[target] = value
    canonicalize_gemini_environment()


_apply_env_aliases()


def _looks_like_livekit_url(value: str) -> bool:
    normalized = value.lower()
    return normalized.startswith(("ws://", "wss://", "http://", "https://")) or "livekit.cloud" in normalized


def _validate_livekit_configuration() -> tuple[str, str, str]:
    livekit_url = (os.getenv("LIVEKIT_URL") or "").strip().rstrip("/")
    api_key = (os.getenv("LIVEKIT_API_KEY") or "").strip()
    api_secret = (os.getenv("LIVEKIT_API_SECRET") or "").strip()

    missing = [
        name
        for name, value in (
            ("LIVEKIT_URL", livekit_url),
            ("LIVEKIT_API_KEY", api_key),
            ("LIVEKIT_API_SECRET", api_secret),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Configuracao do LiveKit incompleta. Defina no .env: "
            + ", ".join(missing)
            + "."
        )

    parsed_url = urlparse(livekit_url)
    if parsed_url.scheme not in ("ws", "wss", "http", "https") or not parsed_url.netloc:
        raise RuntimeError(
            "LIVEKIT_URL invalida. Use a URL do projeto LiveKit, por exemplo: "
            "wss://seu-projeto.livekit.cloud"
        )

    if _looks_like_livekit_url(api_key):
        raise RuntimeError(
            "LIVEKIT_API_KEY parece conter uma URL ou dominio LiveKit. "
            "No painel LiveKit Cloud, copie somente a API Key do projeto; "
            "a URL deve ficar apenas em LIVEKIT_URL."
        )

    if _looks_like_livekit_url(api_secret):
        raise RuntimeError(
            "LIVEKIT_API_SECRET parece conter uma URL ou dominio LiveKit. "
            "Copie o API Secret do mesmo par de chaves usado em LIVEKIT_API_KEY."
        )

    if os.getenv("LIVETKIT_API_KEY") or os.getenv("LIVETKIT_API_SECRET"):
        logger.warning(
            "Variaveis antigas LIVETKIT_* encontradas no ambiente. "
            "Use LIVEKIT_API_KEY e LIVEKIT_API_SECRET; as variaveis corretas tem prioridade."
        )

    os.environ["LIVEKIT_URL"] = livekit_url
    os.environ["LIVEKIT_API_KEY"] = api_key
    os.environ["LIVEKIT_API_SECRET"] = api_secret
    return livekit_url, api_key, api_secret


class GoogleRealtimeSettings:
    def __init__(
        self,
        *,
        model: str,
        voice: str,
        temperature: float,
        timeout: float,
        max_retries: int,
        transcription_enabled: bool,
        vertexai: bool,
        api_key: str | None = None,
        project: str | None = None,
        location: str | None = None,
    ):
        self.model = model
        self.voice = voice
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.transcription_enabled = transcription_enabled
        self.vertexai = vertexai
        self.api_key = api_key
        self.project = project
        self.location = location


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _get_google_api_key() -> str | None:
    return canonicalize_gemini_environment()


def _jarvis_video_enabled() -> bool:
    return _env_flag("JARVIS_VIDEO_ENABLED", False)


def _jarvis_video_sampler() -> VoiceActivityVideoSampler:
    speaking_fps = _env_float("JARVIS_VIDEO_MAX_FPS", 1.0)
    silent_fps = _env_float("JARVIS_VIDEO_SILENT_FPS", 0.2)
    return VoiceActivityVideoSampler(
        speaking_fps=max(0.05, min(speaking_fps, 3.0)),
        silent_fps=max(0.0, min(silent_fps, 1.0)),
    )


def _jarvis_image_encode_options() -> lk_images.EncodeOptions:
    max_width = max(320, min(_env_int("JARVIS_VIDEO_MAX_WIDTH", 960), 1600))
    quality = max(35, min(_env_int("JARVIS_VIDEO_JPEG_QUALITY", 65), 85))
    return lk_images.EncodeOptions(
        format="JPEG",
        quality=quality,
        resize_options=lk_images.ResizeOptions(
            width=max_width,
            height=max_width,
            strategy="scale_aspect_fit",
        ),
    )


def _get_google_realtime_settings() -> GoogleRealtimeSettings:
    use_vertexai = _env_flag("GOOGLE_GENAI_USE_VERTEXAI")
    model = os.getenv("GOOGLE_REALTIME_MODEL") or os.getenv("GEMINI_REALTIME_MODEL")
    if not model:
        model = (
            "gemini-live-2.5-flash-native-audio"
            if use_vertexai
            else "gemini-2.5-flash-native-audio-preview-12-2025"
        )

    voice = os.getenv("GOOGLE_REALTIME_VOICE", "Charon")
    temperature = 0.6
    timeout = _env_float("GOOGLE_REALTIME_TIMEOUT", 30.0)
    max_retries = _env_int("GOOGLE_REALTIME_MAX_RETRIES", 8)
    transcription_enabled = _env_flag("GOOGLE_REALTIME_TRANSCRIPTION_ENABLED", False)

    if use_vertexai:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
        return GoogleRealtimeSettings(
            model=model,
            voice=voice,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
            transcription_enabled=transcription_enabled,
            vertexai=True,
            project=project,
            location=location,
        )

    api_key = _get_google_api_key()
    if not api_key:
        raise RuntimeError(
            "Nenhuma credencial do Gemini foi encontrada. Defina GEMINI_API_KEY no arquivo .env."
        )

    return GoogleRealtimeSettings(
        model=model,
        voice=voice,
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
        transcription_enabled=transcription_enabled,
        vertexai=False,
        api_key=api_key,
    )


def _validate_google_realtime_credentials() -> None:
    settings = _get_google_realtime_settings()
    if settings.vertexai:
        return

    api_key = settings.api_key
    if not api_key:
        raise RuntimeError(
            "Nenhuma credencial do Gemini foi encontrada. Defina GEMINI_API_KEY no arquivo .env."
        )

    request = _urllib.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={quote_plus(api_key)}"
    )
    try:
        with _urllib.urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(
                    "Nao foi possivel validar a chave do Gemini antes de iniciar a sessao."
                )
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        details_lower = details.lower()
        if "api_key_invalid" in details_lower or "api key not valid" in details_lower:
            raise RuntimeError(
                "A chave do Gemini configurada no .env nao e valida. Gere uma nova chave no Google AI Studio e substitua GEMINI_API_KEY."
            ) from exc
        if "reported as leaked" in details_lower or "api key was reported as leaked" in details_lower:
            raise RuntimeError(
                "A chave do Gemini configurada foi bloqueada pelo Google por vazamento. Gere uma nova chave e salve em GEMINI_API_KEY no arquivo .env."
            ) from exc
        if "resource_exhausted" in details_lower or "quota" in details_lower:
            raise RuntimeError(
                "A cota da API Gemini foi excedida. Aguarde o limite resetar, reduza o uso ou aumente a cota/faturamento no Google AI Studio."
            ) from exc
        raise RuntimeError(
            f"Falha ao validar a chave do Gemini ({exc.code}). Revise a credencial e o modelo configurado."
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            "Nao foi possivel validar a conexao com a API do Gemini. Verifique sua internet e tente novamente."
        ) from exc


def _validate_startup_configuration() -> tuple[str, str, str]:
    try:
        livekit_config = _validate_livekit_configuration()
        _validate_google_realtime_credentials()
    except RuntimeError as exc:
        logger.error(str(exc))
        raise SystemExit(1) from exc
    return livekit_config


def _supports_initial_generate_reply(model: str) -> bool:
    return "3.1" not in model

# ─────────────────────────────────────────
# BRAVE + CDP
# ─────────────────────────────────────────

def _get_brave_path():
    caminhos = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for c in caminhos:
        if os.path.exists(c):
            return c
    return None

BRAVE_PATH = _get_brave_path()
CDP_URL = "http://localhost:9222"

def _cdp_disponivel() -> bool:
    """Verifica se o Brave já está rodando com depuração remota."""
    try:
        with _urllib.urlopen(f"{CDP_URL}/json/version", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False

async def _abrir_brave_com_cdp(url: str = "about:blank"):
    """Abre o Brave com porta de depuração (CDP) e navega para a URL."""
    if not BRAVE_PATH:
        webbrowser.open(url)
        return False
    # Se o Brave já está aberto COM cdp, só abre nova aba
    if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel():
        try:
            async with async_playwright() as p: # type: ignore
                browser = await p.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context.new_page()
                await page.goto(url)
                await browser.disconnect() # type: ignore
            return True
        except Exception as exc:
            logger.debug("Falha ao reaproveitar Brave via CDP: %s", exc)
    # Fecha o Brave e reabre com depuração
   # subprocess.run(["taskkill", "/f", "/im", "brave.exe"], capture_output=True)
    await asyncio.sleep(1)
    subprocess.Popen([BRAVE_PATH, f"--remote-debugging-port=9222", url])
    await asyncio.sleep(2.5)
    return _cdp_disponivel()


# ─────────────────────────────────────────
# AGENTE
# ─────────────────────────────────────────

class Assistant(Agent):
    def __init__(self, chat_ctx: ChatContext | None = None):
        realtime_settings = _get_google_realtime_settings()
        api_version = (os.getenv("GOOGLE_REALTIME_API_VERSION") or "").strip()
        self.session_memory = SessionMemory()
        memory_summary = self.session_memory.summary()
        instructions = AGENT_INSTRUCTION
        if memory_summary:
            instructions = (
                AGENT_INSTRUCTION
                + "\n\n# Contexto restaurado da ultima sessao\n"
                + memory_summary
            )
        super().__init__(
            instructions=instructions,
            llm=google.beta.realtime.RealtimeModel(
                model=realtime_settings.model,
                api_key=realtime_settings.api_key if realtime_settings.api_key is not None else NOT_GIVEN,
                voice=realtime_settings.voice,
                temperature=realtime_settings.temperature,
                vertexai=realtime_settings.vertexai,
                project=realtime_settings.project if realtime_settings.project is not None else NOT_GIVEN,
                location=realtime_settings.location if realtime_settings.location is not None else NOT_GIVEN,
                input_audio_transcription=NOT_GIVEN
                if realtime_settings.transcription_enabled
                else None,
                output_audio_transcription=NOT_GIVEN
                if realtime_settings.transcription_enabled
                else None,
                api_version=api_version if api_version else NOT_GIVEN,
                image_encode_options=_jarvis_image_encode_options(),
                conn_options=APIConnectOptions(
                    max_retry=max(1, realtime_settings.max_retries),
                    retry_interval=2.0,
                    timeout=max(10.0, realtime_settings.timeout),
                ),
            ),
            chat_ctx=chat_ctx,
        )
        self.jarvis_control = JarvisControl()
        self.ecosystem = JarvisEcosystem(PROJECT_DIR, self.jarvis_control)

    # ────────────────────────────────
    # MÍDIA E WEB
    # ────────────────────────────────

    @agents.function_tool
    async def pesquisar_na_web(self, consulta: str, tipo: str = "google"):
        """
        Faz uma busca ou abre o YouTube.
        tipo = 'google' → busca no Google
        tipo = 'youtube' → abre a busca no YouTube (não inicia um vídeo automaticamente)
        tipo = 'url' → abre a URL diretamente
        """
        try:
            if tipo.lower() == "youtube":
                # Abre a BUSCA no YouTube, não um vídeo aleatório
                url = f"https://www.youtube.com/results?search_query={quote_plus(consulta)}"
                await _abrir_brave_com_cdp(url)
                return f"Abrindo busca do YouTube por '{consulta}'."

            elif tipo.lower() == "url":
                await _abrir_brave_com_cdp(consulta)
                return f"Abrindo: {consulta}"

            else: # google (padrão)
                url = f"https://www.google.com/search?q={quote_plus(consulta)}"
                await _abrir_brave_com_cdp(url)
                return f"Pesquisando '{consulta}' no Google."
        except Exception as e:
            return f"Erro na pesquisa: {e}"

    @agents.function_tool
    async def pausar_retomar_youtube(self):
        """Pausa ou retoma o vídeo do YouTube que estiver tocando no Chrome."""
        try:
            # Estratégia 1: Keyboard shortcut via pygetwindow (mais confiável)
            try:
                import pygetwindow as gw
                import pyautogui
                import time

                # Procura janelas do Chrome que contenham "YouTube"
                janelas_yt = [w for w in gw.getAllWindows()
                              if "youtube" in w.title.lower() and w.visible]

                if janelas_yt:
                    janela = janelas_yt[0]
                    janela.activate()   # traz o Chrome para frente
                    time.sleep(0.4)     # aguarda o foco
                    pyautogui.press("k")  # 'K' = play/pause no YouTube
                    return "Play/Pause alternado no YouTube ✓"
            except ImportError:
                pass  # pygetwindow/pyautogui não instalados, tenta CDP

            # Estratégia 2: CDP (só funciona se Chrome foi aberto com --remote-debugging-port)
            if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel():
                async with async_playwright() as p: # type: ignore
                    browser = await p.chromium.connect_over_cdp(CDP_URL)
                    for ctx in browser.contexts:
                        for page in ctx.pages:
                            if "youtube.com/watch" in page.url:
                                await page.evaluate(
                                    "const v = document.querySelector('video'); if(v) { v.paused ? v.play() : v.pause(); }"
                                )
                                await browser.disconnect() # type: ignore
                                return "Play/Pause alternado via CDP ✓"
                    await browser.disconnect() # type: ignore
                return "Nenhum vídeo do YouTube encontrado no Chrome."

            return ("Não foi possível controlar o YouTube. "
                    "Instale pygetwindow e pyautogui: pip install pygetwindow pyautogui")
        except Exception as e:
            return f"Erro no controle de mídia: {e}"

    @agents.function_tool
    async def fechar_programa(self, programa: str, confirmar: bool = False):
        """Fecha um programa pelo nome (ex: 'chrome', 'notepad', 'spotify')."""
        return self.ecosystem.desktop.fechar_programa_inteligente(programa, confirmar)

    @agents.function_tool
    async def abrir_programa(self, comando: str):
        """Abre um programa ou executável pelo nome ou caminho (ex: 'notepad', 'calc')."""
        try:
            subprocess.Popen(comando, shell=True)
            return f"'{comando}' aberto."
        except Exception as e:
            return f"Erro ao abrir '{comando}': {e}"

    # ────────────────────────────────
    # ARQUIVOS E PASTAS
    # ────────────────────────────────

    @agents.function_tool
    async def criar_pasta(self, caminho: str):
        """
        Cria uma pasta. Exemplos de comandos válidos:
        - 'Projetos' → cria na Área de Trabalho
        - 'Projetos/Python' → cria subpasta na Área de Trabalho
        - 'Desktop/Projetos' → equivale a Área de Trabalho
        NÃO inclua 'C:/' ou caminhos absolutos, apenas o nome da pasta.
        """
        return self.jarvis_control.cria_pasta(caminho)

    @agents.function_tool
    async def deletar_item(self, caminho: str):
        """Deleta um arquivo ou pasta pelo nome ou caminho."""
        return self.jarvis_control.deletar_arquivo(caminho)

    @agents.function_tool
    async def limpar_diretorio(self, caminho: str):
        """Remove todo o conteúdo de uma pasta, sem deletar a pasta em si."""
        return self.jarvis_control.limpar_diretorio(caminho)

    @agents.function_tool
    async def mover_item(self, origem: str, destino: str):
        """Move um arquivo ou pasta de origem para destino."""
        return self.jarvis_control.mover_item(origem, destino)

    @agents.function_tool
    async def copiar_item(self, origem: str, destino: str):
        """Copia um arquivo ou pasta para um novo local."""
        return self.jarvis_control.copiar_item(origem, destino)

    @agents.function_tool
    async def renomear_item(self, caminho: str, novo_nome: str):
        """Renomeia um arquivo ou pasta."""
        return self.jarvis_control.renomear_item(caminho, novo_nome)

    @agents.function_tool
    async def organizar_pasta(self, caminho: str):
        """Organiza os arquivos de uma pasta por tipo (Imagens, Documentos, etc.)."""
        return self.jarvis_control.organizar_pasta(caminho)

    @agents.function_tool
    async def compactar_pasta(self, caminho: str):
        """Compacta uma pasta em um arquivo .zip."""
        return self.jarvis_control.compactar_pasta(caminho)

    @agents.function_tool
    async def abrir_pasta(self, nome_pasta: str):
        """Abre uma pasta no Explorador de Arquivos pelo nome."""
        return self.jarvis_control.abrir_pasta(nome_pasta)

    @agents.function_tool
    async def buscar_e_abrir_arquivo(self, nome_arquivo: str):
        """Busca um arquivo por nome e o abre automaticamente."""
        return self.jarvis_control.buscar_e_abrir_arquivo(nome_arquivo)

    # ────────────────────────────────
    # AGENDA
    # ────────────────────────────────

    @agents.function_tool
    async def autenticar_google_calendar(self):
        """Autentica o Google Calendar usando OAuth local ou service account configurada no ambiente."""
        return self.jarvis_control.autenticar_google_calendar()

    @agents.function_tool
    async def agendar_no_google_calendar(
        self,
        titulo: str,
        inicio: str,
        fim: str = "",
        descricao: str = "",
        local: str = "",
        dia_inteiro: bool = False,
        lembrete_minutos: int = 30,
    ):
        """
        Cria um evento no Google Calendar.

        Exemplos:
        - dia inteiro: inicio='2026-12-25', dia_inteiro=True
        - com horário: inicio='2026-05-10 14:00', fim='2026-05-10 15:30'
        """
        return self.jarvis_control.agendar_evento_google_calendar(
            titulo=titulo,
            inicio=inicio,
            fim=fim or None,
            descricao=descricao,
            local=local,
            dia_inteiro=dia_inteiro,
            lembrete_minutos=lembrete_minutos,
        )

    @agents.function_tool
    async def listar_eventos_google_calendar(self, inicio: str = "", fim: str = "", limite: int = 10):
        """Lista eventos futuros do Google Calendar, com filtro opcional por intervalo."""
        return self.jarvis_control.listar_eventos_google_calendar(
            inicio=inicio or None,
            fim=fim or None,
            limite=limite,
        )

    @agents.function_tool
    async def remover_evento_google_calendar(self, evento_id: str):
        """Remove um evento do Google Calendar pelo ID retornado na listagem ou criação."""
        return self.jarvis_control.remover_evento_google_calendar(evento_id)

    @agents.function_tool
    async def criar_ou_editar_arquivo(
        self,
        caminho: str,
        modo: str = "w",
        conteudo: str = "",
        conteudo_base64: str | None = None,
        encoding: str = "utf-8",
    ):
        """
        Cria ou edita arquivos usando open() com with.

        Use modos como:
        - 'w' para criar ou sobrescrever arquivos de texto
        - 'a' para adicionar conteúdo ao final
        - 'r+' para editar um arquivo existente desde o início
        - 'wb', 'ab' ou 'rb+' para arquivos binários

        Para arquivos binários, envie o conteúdo em base64 no campo conteudo_base64.
        """
        return self.jarvis_control.criar_ou_editar_arquivo(
            caminho=caminho,
            modo=modo,
            conteudo=conteudo,
            conteudo_base64=conteudo_base64,
            encoding=encoding,
        )

    # ────────────────────────────────
    # SISTEMA
    # ────────────────────────────────

    @agents.function_tool
    async def onedrive_autenticar(self):
        """Autentica o OneDrive via Microsoft Graph usando device code."""
        return self.jarvis_control.onedrive_autenticar()

    @agents.function_tool
    async def onedrive_listar(self, pasta: str = "", limite: int = 50):
        """Lista arquivos e pastas do OneDrive. Use pasta vazia para a raiz."""
        return self.jarvis_control.onedrive_listar(pasta, limite)

    @agents.function_tool
    async def onedrive_criar_pasta(self, nome: str, pasta_pai: str = ""):
        """Cria uma pasta no OneDrive dentro da pasta informada ou na raiz."""
        return self.jarvis_control.onedrive_criar_pasta(nome, pasta_pai)

    @agents.function_tool
    async def onedrive_criar_arquivo(
        self,
        caminho: str,
        conteudo: str = "",
        sobrescrever: bool = True,
    ):
        """Cria ou atualiza um arquivo de texto no OneDrive."""
        return self.jarvis_control.onedrive_criar_arquivo(caminho, conteudo, sobrescrever)

    @agents.function_tool
    async def onedrive_ler_arquivo(self, caminho: str, limite_caracteres: int = 8000):
        """Le um arquivo de texto do OneDrive."""
        return self.jarvis_control.onedrive_ler_arquivo(caminho, limite_caracteres)

    @agents.function_tool
    async def onedrive_deletar_item(self, caminho: str, confirmar: bool = False):
        """Deleta arquivo ou pasta do OneDrive. Use confirmar=True somente quando o usuario pedir explicitamente."""
        return self.jarvis_control.onedrive_deletar_item(caminho, confirmar)

    @agents.function_tool
    async def onedrive_baixar_arquivo(self, caminho_onedrive: str, caminho_local: str = ""):
        """Baixa um arquivo do OneDrive para o computador."""
        return self.jarvis_control.onedrive_baixar_arquivo(caminho_onedrive, caminho_local)

    @agents.function_tool
    async def onedrive_enviar_arquivo(self, caminho_local: str, destino_onedrive: str = ""):
        """Envia um arquivo local para o OneDrive."""
        return self.jarvis_control.onedrive_enviar_arquivo(caminho_local, destino_onedrive)

    @agents.function_tool
    async def onedrive_renomear_item(self, caminho: str, novo_nome: str):
        """Renomeia arquivo ou pasta no OneDrive."""
        return self.jarvis_control.onedrive_renomear_item(caminho, novo_nome)

    @agents.function_tool
    async def onedrive_buscar(self, termo: str, limite: int = 20):
        """Busca arquivos e pastas no OneDrive por nome ou conteudo indexado."""
        return self.jarvis_control.onedrive_buscar(termo, limite)

    @agents.function_tool
    async def controle_volume(self, nivel: int):
        """Ajusta o volume do sistema de 0 a 100."""
        return self.jarvis_control.controle_volume(nivel)

    @agents.function_tool
    async def controle_brilho(self, nivel: int):
        """Ajusta o brilho da tela de 0 a 100."""
        return self.jarvis_control.controle_brilho(nivel)

    @agents.function_tool
    async def energia_pc(self, acao: str):
        """Controla a energia do PC. Ações: 'desligar', 'reiniciar', 'bloquear'."""
        if acao.lower() in {"desligar", "reiniciar"}:
            return "Confirmacao necessaria para alterar energia do PC. Use energia_pc_confirmado."
        return self.jarvis_control.energia_pc(acao)

    @agents.function_tool
    async def energia_pc_confirmado(self, acao: str, confirmar: bool = False):
        """Executa desligar/reiniciar/bloquear. Use confirmar=True somente apos confirmacao do usuario."""
        if acao.lower() in {"desligar", "reiniciar"} and not confirmar:
            return "Confirmacao necessaria para desligar ou reiniciar."
        return self.jarvis_control.energia_pc(acao)

    @agents.function_tool
    async def abrir_aplicativo(self, nome_app: str):
        """Abre aplicativos conhecidos pelo nome (ex: 'spotify', 'vscode', 'calculadora')."""
        return self.ecosystem.desktop.abrir_aplicativo_memorizado(nome_app)

    @agents.function_tool
    async def spam_click(self, quantidade: int = 10, intervalo_ms: int = 20):
        """Executa uma rajada de cliques na posicao viva atual do cursor."""
        return self.ecosystem.desktop.spam_click(quantidade, intervalo_ms)

    @agents.function_tool
    async def clicar_no_cursor(self):
        """Clica exatamente na posicao viva atual do cursor."""
        return self.ecosystem.desktop.click_live_cursor()

    @agents.function_tool
    async def analisar_tela_contextual(self):
        """Analisa a tela atual com janela ativa, movimento e OCR quando disponivel."""
        return self.ecosystem.analisar_tela_contextual()

    @agents.function_tool
    async def controle_midia(self, acao: str, valor: str = ""):
        """Controla midia ativa: toggle, avancar, retroceder, velocidade, proxima, anterior."""
        return await self.ecosystem.media.control(acao, valor)

    @agents.function_tool
    async def identificar_musica(self, segundos: int = 8):
        """Identifica a musica tocando pelo audio do sistema quando ShazamIO e captura estiverem configurados."""
        return await self.ecosystem.music.identify(segundos)

    @agents.function_tool
    async def spotify_autenticar(self):
        """Abre o login do Spotify e salva o token local para controlar playback."""
        return await asyncio.to_thread(self.ecosystem.spotify.authenticate)

    @agents.function_tool
    async def spotify_tocar(self, consulta: str = "", uri: str = "", tipo: str = "musica"):
        """Toca musica, album, artista ou playlist no Spotify. Use tipo: musica, album, artista ou playlist."""
        return await asyncio.to_thread(self.ecosystem.spotify.play, consulta, uri, tipo)

    @agents.function_tool
    async def spotify_pausar(self):
        """Pausa o Spotify."""
        return await asyncio.to_thread(self.ecosystem.spotify.pause)

    @agents.function_tool
    async def spotify_retomar(self):
        """Retoma o Spotify."""
        return await asyncio.to_thread(self.ecosystem.spotify.resume)

    @agents.function_tool
    async def spotify_proxima(self):
        """Pula para a proxima musica no Spotify."""
        return await asyncio.to_thread(self.ecosystem.spotify.next_track)

    @agents.function_tool
    async def spotify_anterior(self):
        """Volta para a musica anterior no Spotify."""
        return await asyncio.to_thread(self.ecosystem.spotify.previous_track)

    @agents.function_tool
    async def spotify_volume(self, porcentagem: int):
        """Ajusta o volume do Spotify de 0 a 100."""
        return await asyncio.to_thread(self.ecosystem.spotify.volume, porcentagem)

    @agents.function_tool
    async def spotify_aleatorio(self, ligado: bool):
        """Liga ou desliga o modo aleatorio do Spotify."""
        return await asyncio.to_thread(self.ecosystem.spotify.shuffle, ligado)

    @agents.function_tool
    async def spotify_repetir(self, modo: str):
        """Ajusta repeticao do Spotify. Modos: musica, playlist, album ou desligado."""
        return await asyncio.to_thread(self.ecosystem.spotify.repeat, modo)

    @agents.function_tool
    async def spotify_buscar(self, consulta: str, limite: int = 5):
        """Busca musicas no Spotify e lista as melhores opcoes."""
        return await asyncio.to_thread(self.ecosystem.spotify.search_tracks, consulta, limite)

    @agents.function_tool
    async def spotify_atual(self):
        """Informa a musica atual do Spotify."""
        return await asyncio.to_thread(self.ecosystem.spotify.current)

    @agents.function_tool
    async def spotify_dispositivos(self):
        """Lista dispositivos Spotify Connect disponiveis."""
        return await asyncio.to_thread(self.ecosystem.spotify.devices)

    @agents.function_tool
    async def escrever_texto(self, texto: str, alvo: str = ""):
        """Escreve texto no campo ativo ou executa hotkeys no formato {CTRL+A}, {DELETE}, {ENTER}."""
        return self.ecosystem.writer.execute_smart_writing(texto, alvo)

    @agents.function_tool
    async def pesquisar_e_salvar_pdf(self, consulta: str, nome_arquivo: str = "pesquisa_jarvis.pdf"):
        """Pesquisa na web, estrutura conteudo e salva um PDF profissional."""
        return self.ecosystem.pesquisar_e_salvar_pdf(consulta, nome_arquivo)

    @agents.function_tool
    async def enviar_whatsapp_msg(self, contato: str, mensagem: str, confirmar: bool = False):
        """Prepara ou envia mensagem no WhatsApp. Envios exigem confirmar=True."""
        return self.ecosystem.whatsapp.enviar(contato, mensagem, confirmar)

    @agents.function_tool
    async def ler_whatsapp_pendente(self):
        """Le mensagens pendentes do servico local de WhatsApp."""
        return self.ecosystem.whatsapp.pendentes()

    @agents.function_tool
    async def confirmar_envio_whatsapp(self):
        """Confirma o ultimo envio pendente do WhatsApp."""
        return self.ecosystem.whatsapp.confirmar_envio()

    @agents.function_tool
    async def ensinar_contato_whatsapp(self, apelido: str, contato_ou_jid: str):
        """Ensina um apelido de contato ao resolver do WhatsApp."""
        return self.ecosystem.whatsapp.ensinar(apelido, contato_ou_jid)

    @agents.function_tool
    async def listar_caminhos_salvos(self):
        """Lista caminhos de apps e processos memorizados."""
        return self.ecosystem.listar_caminhos_salvos()

    @agents.function_tool
    async def executar_codigo_sandbox(self, codigo_python: str):
        """Executa codigo Python em sandbox local controlado."""
        return self.ecosystem.dev_agent.run_python(codigo_python)

    @agents.function_tool
    async def sugerir_commit_git_proativo(self):
        """Sugere uma mensagem de commit Conventional Commits com base no git status."""
        return self.ecosystem.git.suggest_commit()

    @agents.function_tool
    async def executar_commit_git(self, mensagem: str, confirmar: bool = False):
        """Executa git commit. Exige confirmar=True."""
        return self.ecosystem.git.commit(mensagem, confirmar)

    @agents.function_tool
    async def acionar_especialista_codigo(self, prompt: str, modelo: str = "deepseek/deepseek-r1"):
        """Aciona especialista de codigo via OpenRouter."""
        try:
            resposta = self.ecosystem.providers.openrouter_code(prompt, modelo)
            return resposta.content
        except Exception as e:
            return f"Erro no especialista de codigo: {e}"

    @agents.function_tool
    async def gerar_e_ouvir_boletim_documento(self, caminho_documento: str):
        """Gera boletim executivo em audio quando Cohere e Cartesia estiverem configurados."""
        try:
            return self.ecosystem.audio_briefing.generate(caminho_documento)
        except Exception as e:
            return f"Erro no boletim de audio: {e}"

    @agents.function_tool
    async def explorar_e_aprender_interface(self, nome_app: str = "active"):
        """Explora a interface visivel e salva um mapa em cache/ui_maps."""
        return self.ecosystem.ui_explorer.explore(nome_app)

    @agents.function_tool
    async def verificar_e_redigir_ata_reuniao(self):
        """Detecta reuniao ativa e redige uma ata executiva inicial."""
        return self.ecosystem.meeting_scribe.draft_minutes()

    @agents.function_tool
    async def espelhar_estilo_codigo_chefe(self, caminho_raiz: str):
        """Aprende estilo de codigo local e salva guia para especialistas."""
        return self.ecosystem.code_mirror.learn(caminho_raiz)

    @agents.function_tool
    async def faxinar_caixa_whatsapp(self, confirmar: bool = False):
        """Analisa e limpa WhatsApp. Exige confirmar=True."""
        return self.ecosystem.whatsapp_cleaner.clean(confirmar)

    @agents.function_tool
    async def rotear_comando_composto(self, comando: str):
        """Divide comandos compostos em subcomandos sequenciais."""
        return self.ecosystem.rotear_comando_composto(comando)


class _DisabledMemoryClient:
    disabled = True

    async def search(self, *args, **kwargs):
        return []

    async def add(self, *args, **kwargs):
        return None


def _create_mem0_client():
    if not (os.getenv("MEM0_API_KEY") or "").strip():
        logger.warning("[Mem0] MEM0_API_KEY nao definida; memoria de longo prazo desativada.")
        return _DisabledMemoryClient()

    try:
        client = AsyncMemoryClient()
        setattr(client, "disabled", False)
        return client
    except Exception as e:
        logger.warning(f"[Mem0] Memoria de longo prazo desativada: {e}")
        return _DisabledMemoryClient()


# ─────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────

async def entrypoint(ctx: agents.JobContext):

    mem0_client = _create_mem0_client()
    user_id = "GabrielGoulartdeSouza"

    await ctx.connect()

    session = AgentSession(
        video_sampler=_jarvis_video_sampler(),
        max_tool_steps=max(1, min(_env_int("JARVIS_MAX_TOOL_STEPS", 6), 12)),
    )
    agent = Assistant(chat_ctx=ChatContext())
    video_enabled = _jarvis_video_enabled()
    logger.info(
        "Entrada de video LiveKit %s.",
        "ativada" if video_enabled else "desativada por padrao",
    )

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
            video_input=video_enabled,
        ),
    )

    # ── Carregar Memória de Longo Prazo ─────────────────
    # NOTA: Na API v2 do Mem0, user_id vai dentro de 'filters'
    try:
        memory_limit = max(1, min(_env_int("MEM0_MEMORY_LIMIT", 8), 20))
        logger.info(f"[Mem0] Carregando memórias para '{user_id}'...")
        response = await mem0_client.search(
            query="histórico, preferências e informações pessoais do usuário",
            filters={"user_id": user_id},
            limit=memory_limit,
        )
        # O retorno da v2 pode ser dict com "results" ou lista direta
        if isinstance(response, dict):
            results = response.get("results", [])
        elif isinstance(response, list):
            results = response
        else:
            results = []

        logger.info(f"[Mem0] {len(results)} memórias encontradas.")

        if results:
            memorias = []
            for r in results:
                texto = None
                if isinstance(r, dict):
                    texto = r.get("memory") or r.get("text") or r.get("content")
                if texto:
                    memorias.append(f"- {texto}")

            if memorias:
                bloco = "\n".join(memorias)
                ctx_copia = agent.chat_ctx.copy()
                ctx_copia.add_message(
                    role="assistant",
                    content=f"[Memória carregada — informações sobre o usuário]\n{bloco}"
                )
                await agent.update_chat_ctx(ctx_copia)
                logger.info(f"[Mem0] {len(memorias)} memórias injetadas no contexto.")
    except Exception as e:
        logger.error(f"[Mem0] Erro ao carregar memória: {e}")

    # ── Salvar Memória ao Desligar ───────────────────────
    async def shutdown_hook():
        if getattr(mem0_client, "disabled", False):
            return

        try:
            msgs = []
            save_limit = max(1, min(_env_int("MEM0_SAVE_LIMIT", 20), 50))
            for item in agent.chat_ctx.items[-save_limit:]:
                if not hasattr(item, "content") or not item.content: # type: ignore
                    continue
                if item.role not in ("user", "assistant"): # type: ignore
                    continue
                conteudo = "".join(item.content) if isinstance(item.content, list) else str(item.content) # type: ignore
                conteudo = conteudo.strip()
                if conteudo.startswith("[Mem"):
                    continue
                if conteudo:
                    msgs.append({"role": item.role, "content": conteudo}) # type: ignore
            if msgs:
                await mem0_client.add(msgs, user_id=user_id)
                logger.info(f"[Mem0] {len(msgs)} mensagens salvas na memória.")
        except Exception as e:
            logger.warning(f"[Mem0] Erro ao salvar memória: {e}")

    ctx.add_shutdown_callback(shutdown_hook)

    if _supports_initial_generate_reply(_get_google_realtime_settings().model):
        await session.generate_reply(
            instructions=SESSION_INSTRUCTION + "\nCumprimente o usuário de forma natural e confiante."
        )
    else:
        logger.info("Pulando saudacao inicial: generate_reply nao e compativel com este modelo Gemini Live.")


if __name__ == "__main__":
    livekit_url, livekit_api_key, livekit_api_secret = _validate_startup_configuration()
    agent_name = (os.getenv("AGENT_NAME") or "").strip()
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=livekit_url,
            api_key=livekit_api_key,
            api_secret=livekit_api_secret,
            agent_name=agent_name,
            port=_env_int("LIVEKIT_WORKER_PORT", 0),
        )
    )
