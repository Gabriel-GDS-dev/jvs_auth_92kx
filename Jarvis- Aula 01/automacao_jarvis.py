import os
import shutil
import webbrowser
import zipfile
import subprocess
import base64
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import screen_brightness_control as sbc

class JarvisControl:
    def __init__(self):
        self.shortcuts = {
            "youtube": "https://www.youtube.com",
            "github": "https://www.github.com",
            "chatgpt": "https://chatgpt.com/",
            "gemini": "https://gemini.google.com/app",
            "google": "https://www.google.com",
            "instagram": "https://www.instagram.com",
            "portal periodicos": "https://www.periodicos.capes.gov.br/",
            "ava": "https://ava.unesc.net/login/index.php"
        }
        self.home = os.path.expanduser('~')
        self.desktop = os.path.join(self.home, 'Desktop')
        self.documents = os.path.join(self.home, 'Documents')
        self.downloads = os.path.join(self.home, 'Downloads')
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
                os.startfile(caminho_direto)
                return f"Abrindo {nome_pasta}."

            # Busca recursiva nos locais base
            for base_name, base_path in self.base_folders.items():
                if base_name in ["area de trabalho", "documentos", "downloads"]:
                    for dirpath, dirnames, _ in self._walk_seguro(base_path):
                        for d in dirnames:
                            if d.lower() == nome_pasta.lower():
                                full_path = os.path.join(dirpath, d)
                                os.startfile(full_path)
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
                            os.startfile(full_path)
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

        Modos suportados para texto: w, a, x, r+, w+, a+, x+
        Modos suportados para binário: wb, ab, xb, rb+, r+b, wb+, ab+, xb+
        Para arquivos binários, envie o conteúdo em base64.
        """
        path_abs = self._resolver_caminho(caminho)
        try:
            modo = modo.strip().lower()

            modos_validos = {
                'w', 'a', 'x', 'r+', 'w+', 'a+', 'x+',
                'wb', 'ab', 'xb', 'rb+', 'r+b', 'wb+', 'ab+', 'xb+'
            }

            if modo not in modos_validos:
                return (
                    "Modo de arquivo inválido. Use um destes: "
                    + ", ".join(sorted(modos_validos))
                )

            existe_antes = os.path.exists(path_abs)
            diretorio_pai = os.path.dirname(path_abs)
            if diretorio_pai and any(flag in modo for flag in ('w', 'a', 'x')):
                os.makedirs(diretorio_pai, exist_ok=True)

            arquivo_binario = 'b' in modo

            if arquivo_binario:
                dados_binarios = None
                if conteudo_base64 is not None:
                    try:
                        dados_binarios = base64.b64decode(conteudo_base64)
                    except Exception as e:
                        return f"Erro ao decodificar conteúdo base64: {str(e)}"

                with open(path_abs, modo) as arquivo:
                    if dados_binarios is not None:
                        if '+' in modo and 'a' not in modo:
                            arquivo.seek(0)
                        arquivo.write(dados_binarios)
                        if 'r+' in modo or 'rb+' in modo or 'r+b' in modo:
                            arquivo.truncate()

                acao = 'criado' if not existe_antes and os.path.exists(path_abs) else 'atualizado'
                tamanho = os.path.getsize(path_abs) if os.path.exists(path_abs) else 0
                return f"Arquivo binário {acao} com sucesso: {path_abs} ({tamanho} bytes)."

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
            return f"Arquivo não encontrado para edição: {path_abs}"
        except Exception as e:
            return f"Erro ao criar/editar arquivo: {str(e)}"

    # --- Controle de Sistema ---

    def controle_volume(self, nivel):
        """Define o volume entre 0 e 100"""
        try:
            nivel = max(0, min(100, int(nivel)))
            import comtypes
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume # type: ignore
            volume.SetMasterVolumeLevelScalar(nivel / 100, None)
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
                "explorador de arquivos": "explorer.exe",
                "configuracoes": "start ms-settings:"
            }
            comando = apps.get(nome_app.lower())
            if comando:
                if comando.startswith("start "):
                    executavel = comando.replace("start ", "", 1).strip()
                    try: os.startfile(executavel)
                    except: subprocess.Popen(['cmd', '/c', 'start', '', executavel], shell=True)
                else:
                    subprocess.Popen(comando, shell=False)
                return f"Abrindo {nome_app}."
            else:
                try: os.startfile(nome_app)
                except: subprocess.Popen(['cmd', '/c', 'start', '', nome_app], shell=True)
                return f"Tentando abrir {nome_app}."
        except Exception as e:
            return f"Erro ao abrir aplicativo: {str(e)}"

    def atalhos_navegacao(self, site):
        try:
            url = self.shortcuts.get(site.lower())
            if url:
                os.startfile(url)
                return f"Abrindo {site}."
            return "Site não cadastrado."
        except Exception as e:
            return f"Erro ao abrir site: {str(e)}"

    def pesquisar_no_google(self, termo):
        try:
            import urllib.parse
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(termo)}"
            brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
            if os.path.exists(brave_path):
                subprocess.Popen([brave_path, url])
            else:
                os.startfile(url)
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
                os.startfile(path_abs)
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
