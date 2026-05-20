from __future__ import annotations

import os

import requests

from modules.whatsapp_resolver import WhatsAppContactResolver


class WhatsAppClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("WHATSAPP_SERVICE_URL") or "http://127.0.0.1:3333").rstrip("/")
        self.resolver = WhatsAppContactResolver()
        self.pending: dict[str, str] | None = None

    def _get(self, path: str):
        response = requests.get(f"{self.base_url}{path}", timeout=15)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict):
        response = requests.post(f"{self.base_url}{path}", json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    def contatos(self) -> list[dict]:
        data = self._get("/contatos")
        return data.get("contatos", data if isinstance(data, list) else [])

    def enviar(self, contato: str, mensagem: str, confirmar: bool = False) -> str:
        contacts = []
        try:
            contacts = self.contatos()
        except Exception:
            contacts = []
        resolved = self.resolver.resolve(contato, contacts)
        if not resolved.get("found"):
            return f"Contato '{contato}' nao encontrado com confianca suficiente. Ensine com ensinar_contato_whatsapp."
        contact = resolved["contact"] or {}
        target = contact.get("id") or contact.get("jid") or contact.get("number") or contato
        if not confirmar:
            self.pending = {"to": target, "message": mensagem}
            name = contact.get("name") or contact.get("pushname") or contato
            return f"Confirmacao necessaria: deseja enviar '{mensagem}' para {name}?"
        payload = self.pending or {"to": target, "message": mensagem}
        result = self._post("/enviar", payload)
        self.pending = None
        return f"Mensagem enviada: {result}"

    def confirmar_envio(self) -> str:
        if not self.pending:
            return "Nao ha envio pendente para confirmar."
        result = self._post("/enviar", self.pending)
        self.pending = None
        return f"Mensagem enviada: {result}"

    def ensinar(self, alias: str, nome_ou_jid: str) -> str:
        contact = {"name": nome_ou_jid, "id": nome_ou_jid}
        self.resolver.learn(alias, contact)
        return f"Contato aprendido: {alias} -> {nome_ou_jid}"

    def pendentes(self) -> str:
        data = self._get("/nao_lidas")
        return str(data)

