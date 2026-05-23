# Jarvis Sistema

Este diretorio concentra o Jarvis principal, separado por responsabilidade.

## Estrutura

- `cerebro_ia`: cerebro do agente, LiveKit/Gemini/Mem0, ferramentas e servicos autonomos.
- `cerebro_ia/core`: configuracao, memoria de sessao, presenca, perfil social e modo proativo.
- `cerebro_ia/automation`: mouse, teclado, midia, apps e controle do PC.
- `cerebro_ia/vision`: analise de tela, OCR e captura contextual.
- `cerebro_ia/modules`: memoria de caminhos, busca, documentos, WhatsApp resolver e escrita inteligente.
- `cerebro_ia/providers`: roteador multi-IA para provedores externos.
- `cerebro_ia/services`: sandbox, Git proativo, boletim, ata, UI explorer e limpeza WhatsApp.
- `cerebro_ia/tools`: wrappers expostos ao agente LiveKit.
- `cerebro_ia/whatsapp_service`: microservico Node.js para WhatsApp Web.
- `interface_web`: frontend Next.js do Jarvis com LiveKit e `CentralOrb`.
- `automacao_pc`, `memoria_pensamento`, `integracoes`: areas auxiliares preservadas da reorganizacao.

## Ambiente

Use `GEMINI_API_KEY` como chave canonica. Se `GOOGLE_API_KEY` e `GEMINI_API_KEY` estiverem definidas ao mesmo tempo, o Jarvis remove `GOOGLE_API_KEY` do processo para evitar o warning do Gemini.

Variaveis novas ou esperadas:

- `JARVIS_VIDEO_ENABLED=true`
- `JARVIS_VIDEO_MAX_FPS=1`
- `JARVIS_VIDEO_SILENT_FPS=0.2`
- `JARVIS_VIDEO_MAX_WIDTH=960`
- `JARVIS_VIDEO_JPEG_QUALITY=65`
- `JARVIS_VIDEO_QUEUE_SIZE=2`
- `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY`, `JINA_API_KEY`
- `COHERE_API_KEY`, `CARTESIA_API_KEY`, `OCRSPACE_API_KEY`, `SEARXNG_URL`
- `WHATSAPP_SERVICE_URL=http://127.0.0.1:3333`
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback`
- `SPOTIFY_AUTH_FLOW=pkce`, `SPOTIFY_MARKET=BR`

Ferramentas que dependem de API externa retornam erro claro quando a chave correspondente nao existir.

## Spotify

1. Crie um app no Spotify Developer Dashboard.
2. Cadastre exatamente este Redirect URI no app: `http://127.0.0.1:8888/callback`.
3. Copie o Client ID para `SPOTIFY_CLIENT_ID` no `cerebro_ia/.env`.
4. Inicie o Jarvis e diga `autenticar Spotify`.
5. Depois do login, use comandos como `tocar Daft Punk no Spotify`, `pausar Spotify`, `proxima musica`, `volume do Spotify 40`, `modo aleatorio ligado` ou `o que esta tocando`.

O token OAuth fica salvo em `cerebro_ia/cache/spotify_token_cache.json`, que ja e uma pasta ignorada pelo Git. Para controle de playback, mantenha o Spotify aberto em algum dispositivo e use uma conta Premium quando a API exigir controle por Spotify Connect.

## Rodar

Backend:

```powershell
cd .\cerebro_ia
python -m pip install -r requirements.txt
python agent.py dev
```

Frontend:

```powershell
cd .\interface_web
pnpm install
pnpm dev --hostname 127.0.0.1 --port 3000
```

WhatsApp:

```powershell
cd .\cerebro_ia\whatsapp_service
npm install
npm start
```

Na primeira execucao do WhatsApp, leia o QR code no terminal.

## Validacao

```powershell
cd .\cerebro_ia
python -m py_compile agent.py prompts.py core\*.py automation\*.py modules\*.py providers\*.py routers\*.py services\*.py tools\*.py vision\*.py
python -m unittest discover -s tests

cd ..\interface_web
pnpm build
```

Arquivos gerados como `venv`, `node_modules`, `.next`, `.runtime`, caches, logs e `__pycache__` ficam fora da estrutura versionada e podem ser recriados pelos scripts de inicializacao.
