import os
import shutil
import webbrowser
import zipfile
import subprocess
import base64
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import screen_brightness_control as sbc

class JarvisControl:
    def __init__(self):
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
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
        self.google_calendar_scopes = ["https://www.googleapis.com/auth/calendar"]

    def _resolver_arquivo_projeto(self, caminho):
        caminho = str(caminho).strip().strip('"\'')
        if not caminho:
            return ""

        expandido = os.path.abspath(os.path.expanduser(caminho))
        if os.path.isabs(caminho):
            return expandido

        candidato_projeto = os.path.abspath(os.path.join(self.project_dir, caminho))
        if os.path.exists(candidato_projeto):
            return candidato_projeto

        return self._resolver_caminho(caminho)

    def _calendar_timezone(self):
        return os.getenv("GOOGLE_CALENDAR_TIMEZONE", "America/Sao_Paulo")

    def _calendar_tzinfo(self):
        timezone_name = self._calendar_timezone().strip() or "America/Sao_Paulo"
        try:
            return timezone_name, ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            fallback_offsets = {
                "America/Sao_Paulo": -3,
                "UTC": 0,
                "Etc/UTC": 0,
            }
            if timezone_name in fallback_offsets:
                offset_hours = fallback_offsets[timezone_name]
                return timezone_name, timezone(timedelta(hours=offset_hours), name=timezone_name)

            raise RuntimeError(
                "Nao foi possivel carregar o fuso horario configurado para o Google Calendar. "
                "Defina GOOGLE_CALENDAR_TIMEZONE com um valor valido ou instale o pacote tzdata no ambiente Python."
            )

    def _calendar_id(self, calendar_id=None):
        return calendar_id or os.getenv("GOOGLE_CALENDAR_ID", "primary")

    def _calendar_credentials_file(self):
        configured = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
        if configured:
            return self._resolver_arquivo_projeto(configured)
        return os.path.join(self.project_dir, "google_calendar_credentials.json")

    def _calendar_token_file(self):
        configured = os.getenv("GOOGLE_CALENDAR_TOKEN_FILE")
        if configured:
            return self._resolver_arquivo_projeto(configured)
        return os.path.join(self.project_dir, "google_calendar_token.json")

    def _calendar_service_account_file(self):
        configured = os.getenv("GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE")
        if configured:
            return self._resolver_arquivo_projeto(configured)
        return None

    def _load_google_calendar_oauth_config(self, credentials_file):
        try:
            with open(credentials_file, "r", encoding="utf-8") as credentials_handle:
                credentials_data = json.load(credentials_handle)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"O arquivo de credenciais do Google Calendar esta invalido: {credentials_file}. Gere um novo JSON de OAuth no Google Cloud Console."
            ) from exc

        installed_config = credentials_data.get("installed")
        if installed_config:
            return credentials_data, installed_config

        if credentials_data.get("web"):
            raise RuntimeError(
                "O arquivo google_calendar_credentials.json esta usando um OAuth Client do tipo Web. "
                "Para o Jarvis, gere um novo OAuth Client do tipo Desktop App no Google Cloud Console e substitua esse arquivo. "
                "Se a tela de consentimento estiver em modo de teste, adicione sua conta em Test users antes de autenticar."
            )

        raise RuntimeError(
            "O arquivo google_calendar_credentials.json nao contem uma configuracao OAuth valida. "
            "Use um JSON de OAuth Client do tipo Desktop App."
        )

    def _calendar_oauth_runtime_config(self, installed_config):
        redirect_uris = installed_config.get("redirect_uris") or []
        localhost_uri = next(
            (
                uri for uri in redirect_uris
                if isinstance(uri, str) and uri.startswith("http://localhost")
            ),
            None,
        )

        oauth_host = "localhost"
        oauth_port = 0
        oauth_redirect_trailing_slash = True

        if localhost_uri:
            parsed_uri = urlparse(localhost_uri)
            oauth_host = parsed_uri.hostname or "localhost"
            oauth_port = parsed_uri.port or 0
            oauth_redirect_trailing_slash = localhost_uri.endswith("/")

        return oauth_host, oauth_port, oauth_redirect_trailing_slash

    def _build_google_calendar_oauth_error(self, error):
        message = str(error)
        normalized_message = message.lower()

        if "access_denied" in normalized_message or "error 403" in normalized_message:
            return (
                "O Google bloqueou a autenticacao do Calendar. Confirme estes pontos no Google Cloud Console: "
                "1) use um OAuth Client do tipo Desktop App; "
                "2) a Google Calendar API precisa estar ativada; "
                "3) se a tela de consentimento estiver em Testing, sua conta precisa estar cadastrada em Test users."
            )

        return f"Falha ao autenticar no Google Calendar: {message}"

    def _parse_calendar_datetime(self, valor):
        texto = str(valor).strip()
        _, timezone_info = self._calendar_tzinfo()

        if len(texto) == 10 and texto.count("-") == 2:
            return datetime.fromisoformat(texto).date(), True

        try:
            instante = datetime.fromisoformat(texto)
        except ValueError:
            try:
                from dateutil import parser as date_parser
                instante = date_parser.parse(texto, dayfirst=True)
            except Exception as exc:
                raise ValueError(
                    "Use data no formato YYYY-MM-DD ou data e hora como YYYY-MM-DD HH:MM."
                ) from exc

        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone_info)

        return instante.astimezone(timezone_info), False

    def _format_calendar_event_datetime(self, valor):
        if not isinstance(valor, datetime):
            raise ValueError("Data e hora do evento invalidas para o Google Calendar.")

        _, timezone_info = self._calendar_tzinfo()
        return valor.astimezone(timezone_info).isoformat(timespec="seconds")

    def _get_google_calendar_service(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google.oauth2.service_account import Credentials as ServiceAccountCredentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Dependências do Google Calendar não instaladas. Instale google-api-python-client, google-auth-oauthlib e google-auth-httplib2."
            ) from exc

        service_account_file = self._calendar_service_account_file()
        if service_account_file and os.path.exists(service_account_file):
            creds = ServiceAccountCredentials.from_service_account_file(
                service_account_file,
                scopes=self.google_calendar_scopes,
            )
            return build("calendar", "v3", credentials=creds, cache_discovery=False)

        credentials_file = self._calendar_credentials_file()
        token_file = self._calendar_token_file()

        if not os.path.exists(credentials_file):
            raise RuntimeError(
                f"Arquivo de credenciais do Google Calendar não encontrado em: {credentials_file}. Salve o OAuth client em google_calendar_credentials.json na pasta do projeto ou defina GOOGLE_CALENDAR_CREDENTIALS_FILE com o caminho correto."
            )

        _, installed_config = self._load_google_calendar_oauth_config(credentials_file)
        oauth_host, oauth_port, oauth_redirect_trailing_slash = self._calendar_oauth_runtime_config(installed_config)

        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.google_calendar_scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file,
                    self.google_calendar_scopes,
                )
                try:
                    creds = flow.run_local_server(
                        host=oauth_host,
                        port=oauth_port,
                        redirect_uri_trailing_slash=oauth_redirect_trailing_slash,
                        timeout_seconds=180,
                    )
                except Exception as exc:
                    raise RuntimeError(self._build_google_calendar_oauth_error(exc)) from exc

            with open(token_file, "w", encoding="utf-8") as token_handle:
                token_handle.write(creds.to_json())

        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def autenticar_google_calendar(self):
        try:
            self._get_google_calendar_service()
            return "Google Calendar autenticado com sucesso."
        except Exception as e:
            return f"Erro ao autenticar Google Calendar: {str(e)}"

    def agendar_evento_google_calendar(
        self,
        titulo,
        inicio,
        fim=None,
        descricao="",
        local="",
        dia_inteiro=False,
        lembrete_minutos=30,
        calendar_id=None,
    ):
        try:
            service = self._get_google_calendar_service()
            inicio_parseado, inicio_eh_data = self._parse_calendar_datetime(inicio)
            dia_inteiro = bool(dia_inteiro or inicio_eh_data)

            if fim:
                fim_parseado, _ = self._parse_calendar_datetime(fim)
            elif dia_inteiro:
                fim_parseado = inicio_parseado + timedelta(days=1)
            else:
                fim_parseado = inicio_parseado + timedelta(hours=1)

            evento = {
                "summary": str(titulo).strip(),
                "description": str(descricao).strip(),
                "location": str(local).strip(),
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": max(0, int(lembrete_minutos))}],
                },
            }

            _, timezone_info = self._calendar_tzinfo()
            if dia_inteiro:
                evento["start"] = {"date": inicio_parseado.isoformat()}
                evento["end"] = {"date": fim_parseado.isoformat()}
            else:
                evento["start"] = {
                    "dateTime": self._format_calendar_event_datetime(inicio_parseado),
                }
                evento["end"] = {
                    "dateTime": self._format_calendar_event_datetime(fim_parseado),
                }

            criado = service.events().insert(calendarId=self._calendar_id(calendar_id), body=evento).execute()
            link = criado.get("htmlLink", "")
            return f"Evento criado com sucesso: {criado.get('summary', titulo)} | ID: {criado.get('id')} | Link: {link}"
        except Exception as e:
            return f"Erro ao criar evento no Google Calendar: {str(e)}"

    def listar_eventos_google_calendar(self, inicio=None, fim=None, limite=10, calendar_id=None):
        try:
            service = self._get_google_calendar_service()
            _, timezone_info = self._calendar_tzinfo()
            agora = datetime.now(timezone_info)
            time_min = agora.isoformat()
            time_max = None

            if inicio:
                inicio_parseado, inicio_eh_data = self._parse_calendar_datetime(inicio)
                if inicio_eh_data:
                    inicio_parseado = datetime.combine(inicio_parseado, datetime.min.time(), tzinfo=timezone_info)
                time_min = inicio_parseado.isoformat()

            if fim:
                fim_parseado, fim_eh_data = self._parse_calendar_datetime(fim)
                if fim_eh_data:
                    fim_parseado = datetime.combine(fim_parseado, datetime.max.time(), tzinfo=timezone_info)
                time_max = fim_parseado.isoformat()

            consulta = service.events().list(
                calendarId=self._calendar_id(calendar_id),
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max(1, int(limite)),
                singleEvents=True,
                orderBy="startTime",
            )
            eventos = consulta.execute().get("items", [])

            if not eventos:
                return "Nenhum evento encontrado no intervalo informado."

            linhas = []
            for evento in eventos:
                inicio_evento = evento.get("start", {}).get("dateTime") or evento.get("start", {}).get("date")
                linhas.append(f"- {evento.get('summary', '(sem título)')} | {inicio_evento} | ID: {evento.get('id')}")
            return "\n".join(linhas)
        except Exception as e:
            return f"Erro ao listar eventos do Google Calendar: {str(e)}"

    def remover_evento_google_calendar(self, evento_id, calendar_id=None):
        try:
            service = self._get_google_calendar_service()
            service.events().delete(calendarId=self._calendar_id(calendar_id), eventId=str(evento_id).strip()).execute()
            return f"Evento removido com sucesso: {evento_id}"
        except Exception as e:
            return f"Erro ao remover evento do Google Calendar: {str(e)}"

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
