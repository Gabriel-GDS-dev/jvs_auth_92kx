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
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from mem0 import AsyncMemoryClient
import logging
import os
import asyncio
import webbrowser
import subprocess
from pathlib import Path
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

PROJECT_DIR = Path(__file__).resolve().parent


def _apply_env_aliases() -> None:
    aliases = {
        "LIVETKIT_API_KEY": "LIVEKIT_API_KEY",
        "LIVETKIT_API_SECRET": "LIVEKIT_API_SECRET",
        "GEMINI_API_KEY": "GOOGLE_API_KEY",
        "GOOGLE_CLOUD_PROJECT_LOCATION": "GOOGLE_CLOUD_LOCATION",
    }
    for source, target in aliases.items():
        value = os.getenv(source)
        if value and not os.getenv(target):
            os.environ[target] = value


def _load_env_files() -> None:
    load_dotenv(PROJECT_DIR / ".env")
    for parent in PROJECT_DIR.parents:
        shared_env = parent / "cerebro_ia" / ".env"
        if shared_env.exists():
            load_dotenv(shared_env, override=False)
            break
    _apply_env_aliases()


def _get_google_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


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


def _jarvis_video_enabled() -> bool:
    return _env_flag("JARVIS_VIDEO_ENABLED", True)


def _get_google_realtime_model() -> str:
    return (
        os.getenv("GOOGLE_REALTIME_MODEL")
        or os.getenv("GEMINI_REALTIME_MODEL")
        or "gemini-2.5-flash-native-audio-preview-12-2025"
    )


def _supports_initial_generate_reply(model: str) -> bool:
    return "3.1" not in model


_load_env_files()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# CHROME + CDP
# ─────────────────────────────────────────

def _get_chrome_path():
    caminhos = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in caminhos:
        if os.path.exists(c):
            return c
    return None

CHROME_PATH = _get_chrome_path()
CDP_URL = "http://localhost:9222"

def _cdp_disponivel() -> bool:
    """Verifica se o Chrome já está rodando com depuração remota."""
    try:
        with _urllib.urlopen(f"{CDP_URL}/json/version", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False

async def _abrir_chrome_com_cdp(url: str = "about:blank"):
    """Abre o Chrome com porta de depuração (CDP) e navega para a URL."""
    if not CHROME_PATH:
        webbrowser.open(url)
        return False
    # Se o Chrome já está aberto COM cdp, só abre nova aba
    if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel():
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context.new_page()
                await page.goto(url)
                await browser.disconnect() # type: ignore
            return True
        except Exception as exc:
            logger.debug("Falha ao reaproveitar Chrome via CDP: %s", exc)
    # Fecha o Chrome e reabre com depuração
   # subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], capture_output=True)
    await asyncio.sleep(1)
    subprocess.Popen([CHROME_PATH, f"--remote-debugging-port=9222", url])
    await asyncio.sleep(2.5)
    return _cdp_disponivel()


# ─────────────────────────────────────────
# AGENTE
# ─────────────────────────────────────────

class Assistant(Agent):
    def __init__(self, chat_ctx: ChatContext | None = None):
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                model=_get_google_realtime_model(),
                api_key=_get_google_api_key() or NOT_GIVEN,
                voice=os.getenv("GOOGLE_REALTIME_VOICE", "Charon"),
                temperature=0.6,
                input_audio_transcription=NOT_GIVEN
                if _env_flag("GOOGLE_REALTIME_TRANSCRIPTION_ENABLED", False)
                else None,
                output_audio_transcription=NOT_GIVEN
                if _env_flag("GOOGLE_REALTIME_TRANSCRIPTION_ENABLED", False)
                else None,
                api_version=os.getenv("GOOGLE_REALTIME_API_VERSION", "v1alpha"),
                conn_options=APIConnectOptions(
                    max_retry=max(1, _env_int("GOOGLE_REALTIME_MAX_RETRIES", 8)),
                    retry_interval=2.0,
                    timeout=max(10.0, _env_float("GOOGLE_REALTIME_TIMEOUT", 30.0)),
                ),
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
                await _abrir_chrome_com_cdp(url)
                return f"Abrindo busca do YouTube por '{consulta}'."

            elif tipo.lower() == "url":
                await _abrir_chrome_com_cdp(consulta)
                return f"Abrindo: {consulta}"

            else: # google (padrão)
                url = f"https://www.google.com/search?q={quote_plus(consulta)}"
                await _abrir_chrome_com_cdp(url)
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
                async with async_playwright() as p:
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

    @agents.function_tool
    async def criar_ou_editar_arquivo(
        self,
        caminho: str,
        modo: str = "w",
        conteudo: str = "",
        conteudo_base64: str | None = None,
        encoding: str = "utf-8",
    ):
        """Cria ou edita arquivos de texto ou binarios. Use conteudo_base64 para binarios."""
        return self.jarvis_control.criar_ou_editar_arquivo(
            caminho=caminho,
            modo=modo,
            conteudo=conteudo,
            conteudo_base64=conteudo_base64,
            encoding=encoding,
        )

    @agents.function_tool
    async def capturar_tela(self):
        """Captura um screenshot da tela atual e salva na pasta runtime do Jarvis."""
        return self.jarvis_control.capturar_tela() # type: ignore

    @agents.function_tool
    async def analisar_tela(self, pergunta: str = ""):
        """Analisa visualmente a tela atual usando Gemini Vision, quando configurado."""
        return self.jarvis_control.analisar_tela(pergunta) # type: ignore

    @agents.function_tool
    async def escrever_na_tela(
        self,
        texto: str,
        limpar_campo: bool = False,
        pressionar_enter: bool = False,
    ):
        """Digita ou cola texto na janela ativa, util para Notion, Word, sites e apps abertos."""
        return self.jarvis_control.escrever_na_tela(texto, limpar_campo, pressionar_enter) # type: ignore

    @agents.function_tool
    async def pressionar_teclas(self, teclas: str):
        """Pressiona uma tecla ou atalho, por exemplo: 'ctrl+s', 'tab', 'enter'."""
        return self.jarvis_control.pressionar_teclas(teclas) # type: ignore

    @agents.function_tool
    async def clicar_na_tela(self, x: int, y: int, duplo: bool = False):
        """Clica nas coordenadas da tela. Use depois de analisar_tela quando necessario."""
        return self.jarvis_control.clicar_na_tela(x, y, duplo) # type: ignore

    @agents.function_tool
    async def abrir_site(self, url: str):
        """Abre um site no Chrome com depuracao remota quando possivel."""
        await _abrir_chrome_com_cdp(url)
        return f"Abrindo site: {url}"

    @agents.function_tool
    async def interagir_site(
        self,
        acao: str,
        seletor: str = "",
        texto: str = "",
        url: str = "",
        tecla: str = "Enter",
    ):
        """
        Interage com sites abertos no Chrome via seletor CSS quando possivel.
        Acoes: clicar, digitar, ler, tecla. Sem seletor, usa a janela ativa.
        """
        try:
            if url:
                await _abrir_chrome_com_cdp(url)

            acao_normalizada = acao.strip().lower()
            if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel() and seletor:
                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(CDP_URL)
                    context = browser.contexts[0] if browser.contexts else await browser.new_context()
                    page = context.pages[-1] if context.pages else await context.new_page()
                    locator = page.locator(seletor).first() # type: ignore

                    if acao_normalizada in {"clicar", "click"}:
                        await locator.click()
                        await browser.disconnect() # type: ignore
                        return f"Clique executado no seletor: {seletor}"

                    if acao_normalizada in {"digitar", "escrever", "preencher"}:
                        await locator.click()
                        await page.keyboard.press("Control+A")
                        await page.keyboard.insert_text(texto)
                        await browser.disconnect() # type: ignore
                        return f"Texto escrito no seletor: {seletor}"

                    if acao_normalizada in {"ler", "texto", "extrair"}:
                        conteudo = await locator.inner_text(timeout=5000)
                        await browser.disconnect() # type: ignore
                        return conteudo[:3000] or "Elemento encontrado, mas sem texto visivel."

                    if acao_normalizada in {"tecla", "pressionar"}:
                        await locator.click()
                        await page.keyboard.press(tecla)
                        await browser.disconnect() # type: ignore
                        return f"Tecla enviada para o seletor {seletor}: {tecla}"

                    await browser.disconnect() # type: ignore
                    return "Acao invalida. Use clicar, digitar, ler ou tecla."

            if acao_normalizada in {"digitar", "escrever", "preencher"}:
                return self.jarvis_control.escrever_na_tela(texto) # type: ignore
            if acao_normalizada in {"tecla", "pressionar"}:
                return self.jarvis_control.pressionar_teclas(tecla) # type: ignore
            return (
                "Para clicar ou ler por seletor, abra o Chrome pelo Jarvis e informe um seletor CSS. "
                "Para interacao visual, use analisar_tela, clicar_na_tela e escrever_na_tela."
            )
        except Exception as e:
            return f"Erro ao interagir com site: {e}"

    @agents.function_tool
    async def obsidian_criar_nota(self, titulo: str, conteudo: str = "", pasta: str = ""):
        """Cria uma nota Markdown dentro do vault do Obsidian."""
        return self.jarvis_control.obsidian_criar_nota(titulo, conteudo, pasta) # type: ignore

    @agents.function_tool
    async def obsidian_adicionar_em_nota(self, titulo: str, conteudo: str, pasta: str = ""):
        """Adiciona conteudo ao final de uma nota do Obsidian."""
        return self.jarvis_control.obsidian_adicionar_em_nota(titulo, conteudo, pasta) # type: ignore

    @agents.function_tool
    async def obsidian_buscar_notas(self, termo: str, limite: int = 10):
        """Busca notas no vault do Obsidian por titulo ou conteudo."""
        return self.jarvis_control.obsidian_buscar_notas(termo, limite) # type: ignore

    @agents.function_tool
    async def obsidian_abrir_nota(self, titulo: str, pasta: str = ""):
        """Abre uma nota do Obsidian."""
        return self.jarvis_control.obsidian_abrir_nota(titulo, pasta) # type: ignore

    @agents.function_tool
    async def notion_abrir(self):
        """Abre o Notion no navegador."""
        return self.jarvis_control.notion_abrir() # type: ignore

    @agents.function_tool
    async def notion_criar_pagina(self, titulo: str, conteudo: str = "", parent_page_id: str = ""):
        """Cria pagina no Notion via API, ou abre o Notion e digita se a API nao estiver configurada."""
        return self.jarvis_control.notion_criar_pagina(titulo, conteudo, parent_page_id) # type: ignore

    @agents.function_tool
    async def word_criar_documento(self, titulo: str, conteudo: str = "", caminho: str = ""):
        """Cria um arquivo .docx e abre no Word."""
        return self.jarvis_control.word_criar_documento(titulo, conteudo, caminho) # type: ignore

    # ────────────────────────────────
    # SISTEMA
    # ────────────────────────────────

    @agents.function_tool
    async def onedrive_autenticar(self):
        """Autentica o OneDrive via Microsoft Graph usando device code."""
        return self.jarvis_control.onedrive_autenticar() # type: ignore

    @agents.function_tool
    async def onedrive_listar(self, pasta: str = "", limite: int = 50):
        """Lista arquivos e pastas do OneDrive. Use pasta vazia para a raiz."""
        return self.jarvis_control.onedrive_listar(pasta, limite) # type: ignore

    @agents.function_tool
    async def onedrive_criar_pasta(self, nome: str, pasta_pai: str = ""):
        """Cria uma pasta no OneDrive dentro da pasta informada ou na raiz."""
        return self.jarvis_control.onedrive_criar_pasta(nome, pasta_pai) # type: ignore

    @agents.function_tool
    async def onedrive_criar_arquivo(
        self,
        caminho: str,
        conteudo: str = "",
        sobrescrever: bool = True,
    ):
        """Cria ou atualiza um arquivo de texto no OneDrive."""
        return self.jarvis_control.onedrive_criar_arquivo(caminho, conteudo, sobrescrever) # type: ignore

    @agents.function_tool
    async def onedrive_ler_arquivo(self, caminho: str, limite_caracteres: int = 8000):
        """Le um arquivo de texto do OneDrive."""
        return self.jarvis_control.onedrive_ler_arquivo(caminho, limite_caracteres) # type: ignore

    @agents.function_tool
    async def onedrive_deletar_item(self, caminho: str, confirmar: bool = False):
        """Deleta arquivo ou pasta do OneDrive. Use confirmar=True somente quando o usuario pedir explicitamente."""
        return self.jarvis_control.onedrive_deletar_item(caminho, confirmar) # type: ignore

    @agents.function_tool
    async def onedrive_baixar_arquivo(self, caminho_onedrive: str, caminho_local: str = ""):
        """Baixa um arquivo do OneDrive para o computador."""
        return self.jarvis_control.onedrive_baixar_arquivo(caminho_onedrive, caminho_local) # type: ignore

    @agents.function_tool
    async def onedrive_enviar_arquivo(self, caminho_local: str, destino_onedrive: str = ""):
        """Envia um arquivo local para o OneDrive."""
        return self.jarvis_control.onedrive_enviar_arquivo(caminho_local, destino_onedrive) # type: ignore

    @agents.function_tool
    async def onedrive_renomear_item(self, caminho: str, novo_nome: str):
        """Renomeia arquivo ou pasta no OneDrive."""
        return self.jarvis_control.onedrive_renomear_item(caminho, novo_nome) # type: ignore

    @agents.function_tool
    async def onedrive_buscar(self, termo: str, limite: int = 20):
        """Busca arquivos e pastas no OneDrive por nome ou conteudo indexado."""
        return self.jarvis_control.onedrive_buscar(termo, limite) # type: ignore

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

    if _supports_initial_generate_reply(_get_google_realtime_model()):
        await session.generate_reply(
            instructions=SESSION_INSTRUCTION + "\nCumprimente o usuário de forma natural e confiante."
        )
    else:
        logger.info("Pulando saudacao inicial: generate_reply nao e compativel com este modelo Gemini Live.")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=os.getenv("LIVEKIT_URL"),
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
            agent_name=os.getenv("AGENT_NAME", ""),
        )
    )
