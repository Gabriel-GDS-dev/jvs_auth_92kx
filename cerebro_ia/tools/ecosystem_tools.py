from __future__ import annotations

from pathlib import Path

from automation.desktop import DesktopAutomation
from automation.media_control import MediaControl
from core.autonomous_manager import AutonomousManager
from core.proactive_engine import ProactiveEngine
from core.session_memory import SessionMemory
from memory.semantic_memory import SemanticMemory
from modules.file_gen import JarvisFileGen
from modules.music_id import MusicIdentifier
from modules.path_memory import PathMemory
from modules.search import HybridSearch
from modules.smart_writer import SmartTextAutomation
from providers.multi_ai_providers import MultiAIProviderManager
from routers.intent_router import IntentRouter
from services.audio_rag_briefing import AudioRAGBriefingService
from services.code_mirror import CodeStyleMirror
from services.dev_agent import SandboxDevAgent
from services.git_proactive import GitProactiveService
from services.meeting_scribe import MeetingGhostScribe
from services.ui_explorer import AutonomousUIExplorer
from services.whatsapp_cleaner import SmartWhatsAppCleaner
from services.whatsapp_client import WhatsAppClient
from vision.omniparser_vision import OmniParserVision


class JarvisEcosystem:
    def __init__(self, project_dir: Path, legacy_control=None):
        self.project_dir = Path(project_dir)
        self.legacy_control = legacy_control
        self.desktop = DesktopAutomation(self.project_dir)
        self.media = MediaControl()
        self.vision = OmniParserVision()
        self.writer = SmartTextAutomation()
        self.path_memory = PathMemory(self.project_dir)
        self.search = HybridSearch()
        self.file_gen = JarvisFileGen(self.project_dir / "outputs" / "documents")
        self.whatsapp = WhatsAppClient()
        self.session_memory = SessionMemory()
        self.semantic_memory = SemanticMemory()
        self.providers = MultiAIProviderManager()
        self.router = IntentRouter()
        self.proactive = ProactiveEngine()
        self.autonomous = AutonomousManager(self.project_dir)
        self.dev_agent = SandboxDevAgent()
        self.git = GitProactiveService(self.project_dir.parent)
        self.audio_briefing = AudioRAGBriefingService()
        self.ui_explorer = AutonomousUIExplorer()
        self.meeting_scribe = MeetingGhostScribe()
        self.code_mirror = CodeStyleMirror()
        self.whatsapp_cleaner = SmartWhatsAppCleaner()
        self.music = MusicIdentifier()

    def analisar_tela_contextual(self) -> str:
        return self.vision.parse_screen()

    def pesquisar_e_salvar_pdf(self, consulta: str, nome_arquivo: str = "pesquisa_jarvis.pdf") -> str:
        results = self.search.search(consulta, limit=8)
        if not results:
            sections = [
                ("Introducao", f"Pesquisa externa sem resultados suficientes para: {consulta}."),
                ("Fallback Gemini", "Use o conhecimento interno do Gemini para complementar esta solicitacao."),
            ]
            return self.file_gen.write_pdf(nome_arquivo, consulta, sections)
        sections = []
        for result in results[:5]:
            content = self.search.smart_scrape(result.url, limit_chars=2500)
            sections.append((result.title or result.url, content or result.snippet))
        return self.file_gen.write_pdf(nome_arquivo, consulta, sections)

    def listar_caminhos_salvos(self) -> str:
        return self.path_memory.list_saved()

    def rotear_comando_composto(self, comando: str) -> str:
        return str(self.router.route(comando))

