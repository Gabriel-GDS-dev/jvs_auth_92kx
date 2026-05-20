# pyright: reportMissingImports=false, reportMissingModuleSource=false
import os
import shutil
import subprocess
import base64
import sys
from pathlib import Path
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import screen_brightness_control as sbc
from integracoes_jarvis import (
    DesktopInteractor,
    NotionService,
    ObsidianService,
    ScreenVisionService,
    WordService,
    runtime_dir,
)

for _parent in Path(__file__).resolve().parents:
    _integracoes_dir = _parent / "integracoes"
    if (_integracoes_dir / "onedrive_jarvis.py").exists():
        sys.path.insert(0, str(_integracoes_dir))
        break

from onedrive_jarvis import OneDriveService


def _abrir_caminho(caminho):
    subprocess.Popen(["cmd", "/c", "start", "", str(caminho)], shell=False)


class JarvisControl:
    def __init__(self):
        self.shortcuts = {
            "youtube": "https://www.youtube.com",
            "github": "https://www.github.com",
            "chatgpt": "https://chat.openai.com",
            "notion": os.getenv("NOTION_URL", "https://www.notion.so"),
            "google": "https://www.google.com",
            "instagram": "https://www.instagram.com"
        }
        self.home = os.path.expanduser('~')
        self.desktop = os.path.join(self.home, 'Desktop')
        self.documents = os.path.join(self.home, 'Documents')
        self.downloads = os.path.join(self.home, 'Downloads')
        self.onedrive = OneDriveService(os.path.dirname(os.path.abspath(__file__)), self.downloads)
        self.base_folders = {
            "area de trabalho": self.desktop,
            "área de trabalho": self.desktop,
            "desktop": self.desktop,
            "documentos": self.documents,
            "documents": self.documents,
            "downloads": self.downloads
        }
        self.ignore_folders = {
            "venv", ".venv", "env", "node_modules", "__pycache__", ".git", ".idea", ".vscode"
        }
        self.runtime_dir = runtime_dir()
        self.desktop_interactor = DesktopInteractor()
        self.screen_vision = ScreenVisionService(self.runtime_dir)
        self.obsidian = ObsidianService(self.home)
        self.notion = NotionService(self.desktop_interactor)
        self.word = WordService(self.documents)

    def _resolver_caminho(self, caminho):
        """Traduz apelidos (como 'Área de Trabalho') para caminhos reais e garante caminhos absolutos."""
        caminho = caminho.strip('\'"').replace('\\', '/')
        caminho_lower = caminho.lower()

        # Verifica se o caminho começa com um dos apelidos (ex: "desktop/pasta" ou "desktop")
        for alias, real_path in self.base_folders.items():
            if caminho_lower == alias:
                return real_path
            if caminho_lower.startswith(alias + "/"):
                # Substitui o alias pelo caminho real no início da string
                return os.path.abspath(os.path.join(real_path, caminho[len(alias)+1:]))
        
        # Se for um caminho relativo simples, assume que é no Desktop por padrão
        if not os.path.isabs(caminho) and not caminho.startswith('.'):
            return os.path.abspath(os.path.join(self.desktop, caminho))
            
        return os.path.abspath(os.path.expanduser(caminho))

    def _walk_seguro(self, base):
        """os.walk que ignora pastas irrelevantes para performance e segurança."""
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in self.ignore_folders and not d.startswith('.')]
            yield dirpath, dirnames, filenames

    # --- Manipulação de Arquivos e Pastas ---

    def cria_pasta(self, caminho):
        try:
            caminho_abs = self._resolver_caminho(caminho)
            os.makedirs(caminho_abs, exist_ok=True)
            return f"Pasta criada com sucesso: {caminho_abs}"
        except Exception as e:
            return f"Erro ao criar pasta: {str(e)}"

    def abrir_pasta(self, nome_pasta):
        """Tenta encontrar e abrir uma pasta pelo nome nos locais principais."""
        try:
            # Caso o usuário passe o nome de um local conhecido
            caminho_direto = self.base_folders.get(nome_pasta.lower())
            if caminho_direto and os.path.exists(caminho_direto):
                _abrir_caminho(caminho_direto)
                return f"Abrindo {nome_pasta}."

            # Busca recursiva nos locais base
            for base_name, base_path in self.base_folders.items():
                if base_name in ["area de trabalho", "documentos", "downloads"]:
                    for dirpath, dirnames, _ in self._walk_seguro(base_path):
                        for d in dirnames:
                            if d.lower() == nome_pasta.lower():
                                full_path = os.path.join(dirpath, d)
                                _abrir_caminho(full_path)
                                return f"Pasta encontrada e aberta em: {full_path}"
            
            return f"Pasta '{nome_pasta}' não encontrada nos locais padrão."
        except Exception as e:
            return f"Erro ao abrir pasta: {str(e)}"

    def buscar_e_abrir_arquivo(self, nome_arquivo):
        """Busca um arquivo por nome e abre o primeiro resultado."""
        try:
            for _, base_path in self.base_folders.items():
                for dirpath, _, filenames in self._walk_seguro(base_path):
                    for f in filenames:
                        if nome_arquivo.lower() in f.lower():
                            full_path = os.path.join(dirpath, f)
                            _abrir_caminho(full_path)
                            return f"Arquivo encontrado e aberto: {full_path}"
            return f"Arquivo '{nome_arquivo}' não encontrado."
        except Exception as e:
            return f"Erro ao buscar/abrir arquivo: {str(e)}"

    def deletar_arquivo(self, caminho):
        try:
            path_abs = self._resolver_caminho(caminho)
            if os.path.isfile(path_abs):
                os.remove(path_abs)
                return f"Arquivo deletado: {path_abs}"
            elif os.path.isdir(path_abs):
                shutil.rmtree(path_abs)
                return f"Diretório deletado: {path_abs}"
            return f"Caminho não encontrado: {path_abs}"
        except Exception as e:
            return f"Erro ao deletar: {str(e)}"

    def limpar_diretorio(self, caminho):
        try:
            path_abs = self._resolver_caminho(caminho)
            if os.path.exists(path_abs):
                for item in os.listdir(path_abs):
                    item_path = os.path.join(path_abs, item)
                    if os.path.isfile(item_path): os.remove(item_path)
                    elif os.path.isdir(item_path): shutil.rmtree(item_path)
                return f"Diretório limpo: {path_abs}"
            return "Diretório não encontrado."
        except Exception as e:
            return f"Erro ao limpar diretório: {str(e)}"

    def mover_item(self, origem, destino):
        try:
            origem_abs = self._resolver_caminho(origem)
            destino_abs = self._resolver_caminho(destino)
            shutil.move(origem_abs, destino_abs)
            return f"Movido de {origem_abs} para {destino_abs}."
        except Exception as e:
            return f"Erro ao mover: {str(e)}"

    def copiar_item(self, origem, destino):
        try:
            origem_abs = self._resolver_caminho(origem)
            destino_abs = self._resolver_caminho(destino)
            if os.path.isdir(origem_abs): shutil.copytree(origem_abs, destino_abs)
            else: shutil.copy2(origem_abs, destino_abs)
            return f"Copiado de {origem_abs} para {destino_abs}."
        except Exception as e:
            return f"Erro ao copiar: {str(e)}"

    def renomear_item(self, caminho, novo_nome):
        try:
            path_abs = self._resolver_caminho(caminho)
            diretorio = os.path.dirname(path_abs)
            novo_caminho = os.path.join(diretorio, novo_nome)
            os.rename(path_abs, novo_caminho)
            return f"Renomeado para {novo_nome}."
        except Exception as e:
            return f"Erro ao renomear: {str(e)}"

    def organizar_pasta(self, caminho):
        try:
            path_abs = self._resolver_caminho(caminho)
            extensoes = {
                'Imagens': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
                'Documentos': ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.pptx', '.csv'],
                'Videos': ['.mp4', '.mkv', '.avi', '.mov'],
                'Musicas': ['.mp3', '.wav', '.flac'],
                'Compactados': ['.zip', '.rar', '.7z'],
                'Executaveis': ['.exe', '.msi', '.bat']
            }

            for item in os.listdir(path_abs):
                item_path = os.path.join(path_abs, item)
                if os.path.isfile(item_path):
                    ext = os.path.splitext(item)[1].lower()
                    movido = False
                    for pasta, exts in extensoes.items():
                        if ext in exts:
                            pasta_destino = os.path.join(path_abs, pasta)
                            os.makedirs(pasta_destino, exist_ok=True)
                            shutil.move(item_path, os.path.join(pasta_destino, item))
                            movido = True
                            break
                    if not movido:
                        pasta_outros = os.path.join(path_abs, 'Outros')
                        os.makedirs(pasta_outros, exist_ok=True)
                        shutil.move(item_path, os.path.join(pasta_outros, item))
            return "Pasta organizada com sucesso."
        except Exception as e:
            return f"Erro ao organizar pasta: {str(e)}"

    def compactar_pasta(self, caminho):
        try:
            path_abs = self._resolver_caminho(caminho).rstrip('/\\')
            shutil.make_archive(path_abs, 'zip', path_abs)
            return f"Compactado em: {path_abs}.zip"
        except Exception as e:
            return f"Erro ao compactar: {str(e)}"

    def criar_ou_editar_arquivo(self, caminho, modo='w', conteudo=None, conteudo_base64=None, encoding='utf-8'):
        """
        Cria ou edita arquivos usando open() com gerenciador de contexto.

        Modos de texto: w, a, x, r+, w+, a+, x+
        Modos binarios: wb, ab, xb, rb+, r+b, wb+, ab+, xb+
        """
        path_abs = ""
        try:
            path_abs = self._resolver_caminho(caminho)
            modo = modo.strip().lower()
            modos_validos = {
                'w', 'a', 'x', 'r+', 'w+', 'a+', 'x+',
                'wb', 'ab', 'xb', 'rb+', 'r+b', 'wb+', 'ab+', 'xb+'
            }
            if modo not in modos_validos:
                return "Modo de arquivo invalido. Use: " + ", ".join(sorted(modos_validos))

            existe_antes = os.path.exists(path_abs)
            diretorio_pai = os.path.dirname(path_abs)
            if diretorio_pai and any(flag in modo for flag in ('w', 'a', 'x')):
                os.makedirs(diretorio_pai, exist_ok=True)

            if 'b' in modo:
                dados_binarios = None
                if conteudo_base64 is not None:
                    dados_binarios = base64.b64decode(conteudo_base64)

                with open(path_abs, modo) as arquivo:
                    if dados_binarios is not None:
                        if '+' in modo and 'a' not in modo:
                            arquivo.seek(0)
                        arquivo.write(dados_binarios)
                        if 'r+' in modo or 'rb+' in modo or 'r+b' in modo:
                            arquivo.truncate()

                acao = 'criado' if not existe_antes and os.path.exists(path_abs) else 'atualizado'
                tamanho = os.path.getsize(path_abs) if os.path.exists(path_abs) else 0
                return f"Arquivo binario {acao}: {path_abs} ({tamanho} bytes)."

            texto = conteudo if conteudo is not None else ''
            with open(path_abs, modo, encoding=encoding) as arquivo:
                if '+' in modo and 'a' not in modo:
                    arquivo.seek(0)
                arquivo.write(texto)
                if 'r+' in modo:
                    arquivo.truncate()

            acao = 'criado' if not existe_antes and os.path.exists(path_abs) else 'atualizado'
            return f"Arquivo {acao} com sucesso: {path_abs}"
        except FileNotFoundError:
            return f"Arquivo nao encontrado para edicao: {path_abs}"
        except Exception as e:
            return f"Erro ao criar/editar arquivo: {str(e)}"

    # --- Integracoes e tela ---

    def capturar_tela(self):
        try:
            captura = self.screen_vision.capturar_tela()
            return (
                f"Screenshot salvo em {captura['path']} "
                f"({captura['width']}x{captura['height']})."
            )
        except Exception as e:
            return f"Erro ao capturar tela: {str(e)}"

    def analisar_tela(self, pergunta=""):
        return self.screen_vision.analisar_tela(pergunta)

    def abrir_site(self, url):
        return self.desktop_interactor.abrir_site(url)

    def escrever_na_tela(self, texto, limpar_campo=False, pressionar_enter=False):
        return self.desktop_interactor.digitar_na_tela(texto, limpar_campo, pressionar_enter)

    def pressionar_teclas(self, teclas):
        return self.desktop_interactor.pressionar_teclas(teclas)

    def clicar_na_tela(self, x, y, duplo=False):
        return self.desktop_interactor.clicar_na_tela(x, y, duplo)

    def obsidian_criar_nota(self, titulo, conteudo="", pasta=""):
        return self.obsidian.criar_nota(titulo, conteudo, pasta)

    def obsidian_adicionar_em_nota(self, titulo, conteudo, pasta=""):
        return self.obsidian.adicionar_em_nota(titulo, conteudo, pasta)

    def obsidian_buscar_notas(self, termo, limite=10):
        return self.obsidian.buscar_notas(termo, limite)

    def obsidian_abrir_nota(self, titulo, pasta=""):
        return self.obsidian.abrir_nota(titulo, pasta)

    def notion_abrir(self):
        return self.notion.abrir_notion()

    def notion_criar_pagina(self, titulo, conteudo="", parent_page_id=""):
        return self.notion.criar_pagina(titulo, conteudo, parent_page_id)

    def word_criar_documento(self, titulo, conteudo="", caminho=""):
        return self.word.criar_documento(titulo, conteudo, caminho)

    def onedrive_autenticar(self):
        try:
            return self.onedrive.autenticar()
        except Exception as e:
            return f"Erro ao autenticar OneDrive: {str(e)}"

    def onedrive_listar(self, pasta="", limite=50):
        try:
            return self.onedrive.listar(pasta, limite)
        except Exception as e:
            return f"Erro ao listar OneDrive: {str(e)}"

    def onedrive_criar_pasta(self, nome, pasta_pai=""):
        try:
            return self.onedrive.criar_pasta(nome, pasta_pai)
        except Exception as e:
            return f"Erro ao criar pasta no OneDrive: {str(e)}"

    def onedrive_criar_arquivo(self, caminho, conteudo="", sobrescrever=True):
        try:
            return self.onedrive.criar_arquivo(caminho, conteudo, sobrescrever)
        except Exception as e:
            return f"Erro ao criar arquivo no OneDrive: {str(e)}"

    def onedrive_ler_arquivo(self, caminho, limite_caracteres=8000):
        try:
            return self.onedrive.ler_arquivo(caminho, limite_caracteres)
        except Exception as e:
            return f"Erro ao ler arquivo do OneDrive: {str(e)}"

    def onedrive_deletar_item(self, caminho, confirmar=False):
        try:
            return self.onedrive.deletar_item(caminho, confirmar)
        except Exception as e:
            return f"Erro ao deletar item do OneDrive: {str(e)}"

    def onedrive_baixar_arquivo(self, caminho_onedrive, caminho_local=""):
        try:
            caminho_destino = self._resolver_caminho(caminho_local) if caminho_local else ""
            return self.onedrive.baixar_arquivo(caminho_onedrive, caminho_destino)
        except Exception as e:
            return f"Erro ao baixar arquivo do OneDrive: {str(e)}"

    def onedrive_enviar_arquivo(self, caminho_local, destino_onedrive=""):
        try:
            caminho_origem = self._resolver_caminho(caminho_local)
            return self.onedrive.enviar_arquivo(caminho_origem, destino_onedrive)
        except Exception as e:
            return f"Erro ao enviar arquivo para o OneDrive: {str(e)}"

    def onedrive_renomear_item(self, caminho, novo_nome):
        try:
            return self.onedrive.renomear_item(caminho, novo_nome)
        except Exception as e:
            return f"Erro ao renomear item no OneDrive: {str(e)}"

    def onedrive_buscar(self, termo, limite=20):
        try:
            return self.onedrive.buscar(termo, limite)
        except Exception as e:
            return f"Erro ao buscar no OneDrive: {str(e)}"

    # --- Controle de Sistema ---

    def controle_volume(self, nivel):
        """Define o volume entre 0 e 100"""
        try:
            nivel = max(0, min(100, int(nivel)))
            import comtypes
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None) # type: ignore
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(nivel / 100, None) # type: ignore
            return f"Volume ajustado para {nivel}%."
        except Exception as e:
            return f"Erro ao ajustar volume: {str(e)}"

    def controle_brilho(self, nivel):
        """Define o brilho entre 0 e 100"""
        try:
            nivel = max(0, min(100, int(nivel)))
            sbc.set_brightness(nivel)
            return f"Brilho ajustado para {nivel}%."
        except Exception as e:
            return f"Erro ao ajustar brilho: {str(e)}"

    def abrir_aplicativo(self, nome_app):
        """Abre um aplicativo no sistema pelo nome."""
        try:
            apps = {
                "bloco de notas": "notepad.exe",
                "calculadora": "calc.exe",
                "paint": "mspaint.exe",
                "cmd": "cmd.exe",
                "navegador": "start msedge",
                "word": "start winword",
                "excel": "start excel",
                "powerpoint": "start powerpnt",
                "notion": os.getenv("NOTION_URL", "https://www.notion.so"),
                "explorador de arquivos": "explorer.exe",
                "configuracoes": "start ms-settings:"
            }
            comando = apps.get(nome_app.lower())
            if comando:
                if comando.startswith("start "):
                    executavel = comando.replace("start ", "", 1).strip()
                    try:
                        _abrir_caminho(executavel)
                    except OSError:
                        subprocess.Popen(['cmd', '/c', 'start', '', executavel], shell=True)
                elif "://" in comando or comando.startswith("ms-"):
                    _abrir_caminho(comando)
                else:
                    subprocess.Popen(comando, shell=False)
                return f"Abrindo {nome_app}."
            else:
                try:
                    _abrir_caminho(nome_app)
                except OSError:
                    subprocess.Popen(['cmd', '/c', 'start', '', nome_app], shell=True)
                return f"Tentando abrir {nome_app}."
        except Exception as e:
            return f"Erro ao abrir aplicativo: {str(e)}"

    def atalhos_navegacao(self, site):
        try:
            url = self.shortcuts.get(site.lower())
            if url:
                _abrir_caminho(url)
                return f"Abrindo {site}."
            return "Site não cadastrado."
        except Exception as e:
            return f"Erro ao abrir site: {str(e)}"

    def pesquisar_no_google(self, termo):
        try:
            import urllib.parse
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(termo)}"
            _abrir_caminho(url)
            return f"Pesquisando por {termo}."
        except Exception as e:
            return f"Erro ao pesquisar: {str(e)}"

    def energia_pc(self, acao):
        try:
            if acao == "desligar":
                os.system("shutdown /s /t 1")
                return "Desligando o computador."
            elif acao == "reiniciar":
                os.system("shutdown /r /t 1")
                return "Reiniciando o computador."
            elif acao == "bloquear":
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
                return "Computador bloqueado."
            return "Ação inválida."
        except Exception as e:
            return f"Erro: {str(e)}"

    def abrir_arquivo(self, caminho):
        """Abre um arquivo pelo caminho completo."""
        try:
            path_abs = self._resolver_caminho(caminho)
            if os.path.exists(path_abs):
                _abrir_caminho(path_abs)
                return f"Abrindo arquivo {path_abs}."
            return f"Arquivo não encontrado: {path_abs}"
        except Exception as e:
            return f"Erro ao abrir arquivo: {str(e)}"

if __name__ == "__main__":
    # Teste rápido de caminhos dinâmicos
    user_home = os.path.expanduser('~')
    print(f"Home do usuário detectada: {user_home}")
    jarvis = JarvisControl()
    # jarvis.atalhos_navegacao("github")
