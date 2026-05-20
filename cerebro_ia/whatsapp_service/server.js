const express = require('express');
const qrcode = require('qrcode-terminal');
const { Client, LocalAuth } = require('whatsapp-web.js');

const PORT = Number(process.env.WHATSAPP_SERVICE_PORT || 3333);
const app = express();
app.use(express.json({ limit: '2mb' }));

let ready = false;
let lastQr = '';

const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'jarvis' }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  }
});

client.on('qr', (qr) => {
  ready = false;
  lastQr = qr;
  qrcode.generate(qr, { small: true });
  console.log('[Jarvis WhatsApp] Escaneie o QR Code acima.');
});

client.on('ready', () => {
  ready = true;
  console.log('[Jarvis WhatsApp] Cliente pronto.');
});

client.on('disconnected', (reason) => {
  ready = false;
  console.log('[Jarvis WhatsApp] Desconectado:', reason);
});

function normalizeTarget(to) {
  const raw = String(to || '').trim();
  if (!raw) return raw;
  if (raw.includes('@')) return raw;
  const digits = raw.replace(/\D/g, '');
  if (!digits) return raw;
  return `${digits}@c.us`;
}

function requireReady(res) {
  if (!ready) {
    res.status(503).json({ ok: false, error: 'WhatsApp ainda nao esta pronto. Escaneie o QR Code.' });
    return false;
  }
  return true;
}

app.get('/status', (_req, res) => {
  res.json({ ok: true, ready, hasQr: Boolean(lastQr) });
});

app.get('/contatos', async (_req, res) => {
  if (!requireReady(res)) return;
  try {
    const contacts = await client.getContacts();
    res.json({
      ok: true,
      contatos: contacts.map((c) => ({
        id: c.id?._serialized,
        number: c.number,
        name: c.name,
        pushname: c.pushname,
        isGroup: c.isGroup
      }))
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: String(error) });
  }
});

app.get('/mensagens', async (req, res) => {
  if (!requireReady(res)) return;
  try {
    const limit = Number(req.query.limit || 20);
    const chats = await client.getChats();
    const mensagens = [];
    for (const chat of chats.slice(0, Math.max(1, limit))) {
      const msgs = await chat.fetchMessages({ limit: 5 });
      mensagens.push({
        id: chat.id?._serialized,
        name: chat.name,
        unreadCount: chat.unreadCount,
        messages: msgs.map((m) => ({
          from: m.from,
          to: m.to,
          body: m.body,
          timestamp: m.timestamp
        }))
      });
    }
    res.json({ ok: true, mensagens });
  } catch (error) {
    res.status(500).json({ ok: false, error: String(error) });
  }
});

app.get('/nao_lidas', async (_req, res) => {
  if (!requireReady(res)) return;
  try {
    const chats = await client.getChats();
    const naoLidas = chats
      .filter((chat) => chat.unreadCount > 0)
      .map((chat) => ({
        id: chat.id?._serialized,
        name: chat.name,
        unreadCount: chat.unreadCount
      }));
    res.json({ ok: true, nao_lidas: naoLidas });
  } catch (error) {
    res.status(500).json({ ok: false, error: String(error) });
  }
});

app.post('/enviar', async (req, res) => {
  if (!requireReady(res)) return;
  try {
    const target = normalizeTarget(req.body.to || req.body.numero || req.body.jid);
    const message = String(req.body.message || req.body.mensagem || '');
    if (!target || !message) {
      res.status(400).json({ ok: false, error: 'Campos obrigatorios: to/message.' });
      return;
    }
    const response = await client.sendMessage(target, message);
    res.json({ ok: true, id: response.id?._serialized, to: target });
  } catch (error) {
    res.status(500).json({ ok: false, error: String(error) });
  }
});

client.initialize();

app.listen(PORT, () => {
  console.log(`[Jarvis WhatsApp] Servico em http://127.0.0.1:${PORT}`);
});

