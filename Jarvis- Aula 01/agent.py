from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext, llm, NOT_GIVEN
from livekit.plugins import noise_cancellation, google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from mem0 import AsyncMemoryClient
import logging
import os
import asyncio
import webbrowser
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
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

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleRealtimeSettings:
    def __init__(
        self,
        *,
        model: str,
        voice: str,
        temperature: float,
        vertexai: bool,
        api_key: str | None = None,
        project: str | None = None,
        location: str | None = None,
    ):
        self.model = model
        self.voice = voice
        self.temperature = temperature
        self.vertexai = vertexai
        self.api_key = api_key
        self.project = project
        self.location = location


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_google_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


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

    if use_vertexai:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
        return GoogleRealtimeSettings(
            model=model,
            voice=voice,
            temperature=temperature,
            vertexai=True,
            project=project,
            location=location,
        )

    api_key = _get_google_api_key()
    if not api_key:
        raise RuntimeError(
            "Nenhuma credencial do Gemini foi encontrada. Defina GEMINI_API_KEY ou GOOGLE_API_KEY no arquivo .env."
        )

    return GoogleRealtimeSettings(
        model=model,
        voice=voice,
        temperature=temperature,
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
            "Nenhuma credencial do Gemini foi encontrada. Defina GEMINI_API_KEY ou GOOGLE_API_KEY no arquivo .env."
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
        if "reported as leaked" in details_lower or "api key was reported as leaked" in details_lower:
            raise RuntimeError(
                "A chave do Gemini configurada foi bloqueada pelo Google por vazamento. Gere uma nova chave e salve em GEMINI_API_KEY ou GOOGLE_API_KEY no arquivo .env."
            ) from exc
        raise RuntimeError(
            f"Falha ao validar a chave do Gemini ({exc.code}). Revise a credencial e o modelo configurado."
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            "Nao foi possivel validar a conexao com a API do Gemini. Verifique sua internet e tente novamente."
        ) from exc


def _validate_startup_configuration() -> None:
    try:
        _validate_google_realtime_credentials()
    except RuntimeError as exc:
        logger.error(str(exc))
        raise SystemExit(1) from exc

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
    except:
        return False

async def _abrir_brave_com_cdp(url: str = "about:blank"):
    """Abre o Brave com porta de depuração (CDP) e navega para a URL."""
    if not BRAVE_PATH:
        webbrowser.open(url)
        return False
    # Se o Brave já está aberto COM cdp, só abre nova aba
    if _cdp_disponivel():
        try:
            async with async_playwright() as p: # type: ignore
                browser = await p.chromium.connect_over_cdp(CDP_URL)
                page = await browser.contexts[0].new_page()
                await page.goto(url)
                await browser.disconnect() # type: ignore
            return True
        except:
            pass
    # Fecha o Brave e reabre com depuração
   # subprocess.run(["taskkill", "/f", "/im", "brave.exe"], capture_output=True)
    await asyncio.sleep(1)
    subprocess.Popen([BRAVE_PATH, f"--remote-debugging-port=9222", url])
    await asyncio.sleep(2.5)
    return _cdp_disponivel()


# ─────────────────────────────────────────
# AGENTE
# ─────────────────────────────────────────

class Assistant(Agent, llm.ToolContext): # type: ignore
    def __init__(self, chat_ctx: ChatContext = None): # type: ignore
        llm.ToolContext.__init__(self, [])
        realtime_settings = _get_google_realtime_settings()
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                model=realtime_settings.model,
                api_key=realtime_settings.api_key if realtime_settings.api_key is not None else NOT_GIVEN,
                voice=realtime_settings.voice,
                temperature=realtime_settings.temperature,
                vertexai=realtime_settings.vertexai,
                project=realtime_settings.project if realtime_settings.project is not None else NOT_GIVEN,
                location=realtime_settings.location if realtime_settings.location is not None else NOT_GIVEN,
            ),
            chat_ctx=chat_ctx,
        )
        self.jarvis_control = JarvisControl()

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
    async def fechar_programa(self, programa: str):
        """Fecha um programa pelo nome (ex: 'chrome', 'notepad', 'spotify')."""
        exe = programa if programa.lower().endswith(".exe") else f"{programa}.exe"
        res = subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True)
        if res.returncode == 0:
            return f"Programa '{programa}' fechado com sucesso."
        return f"Não foi possível fechar '{programa}'. Verifique o nome do processo."

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
        return self.jarvis_control.energia_pc(acao)

    @agents.function_tool
    async def abrir_aplicativo(self, nome_app: str):
        """Abre aplicativos conhecidos pelo nome (ex: 'spotify', 'vscode', 'calculadora')."""
        return self.jarvis_control.abrir_aplicativo(nome_app)


# ─────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────

async def entrypoint(ctx: agents.JobContext):

    mem0_client = AsyncMemoryClient()
    user_id = "GabrielGoulartdeSouza"

    await ctx.connect()

    session = AgentSession()
    agent = Assistant(chat_ctx=ChatContext())

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # ── Carregar Memória de Longo Prazo ─────────────────
    # NOTA: Na API v2 do Mem0, user_id vai dentro de 'filters'
    try:
        logger.info(f"[Mem0] Carregando memórias para '{user_id}'...")
        response = await mem0_client.search(
            query="histórico, preferências e informações pessoais do usuário",
            filters={"user_id": user_id},
            limit=20,
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
        try:
            msgs = []
            for item in session._agent.chat_ctx.items: # type: ignore
                if not hasattr(item, "content") or not item.content: # type: ignore
                    continue
                if item.role not in ("user", "assistant"): # type: ignore
                    continue
                conteudo = "".join(item.content) if isinstance(item.content, list) else str(item.content) # type: ignore
                conteudo = conteudo.strip()
                if conteudo:
                    msgs.append({"role": item.role, "content": conteudo}) # type: ignore
            if msgs:
                await mem0_client.add(msgs, user_id=user_id)
                logger.info(f"[Mem0] {len(msgs)} mensagens salvas na memória.")
        except Exception as e:
            logger.warning(f"[Mem0] Erro ao salvar memória: {e}")

    ctx.add_shutdown_callback(shutdown_hook)

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION + "\nCumprimente o usuário de forma natural e confiante."
    )


if __name__ == "__main__":
    _validate_startup_configuration()
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
