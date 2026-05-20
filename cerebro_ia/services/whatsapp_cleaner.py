from __future__ import annotations

from services.whatsapp_client import WhatsAppClient


class SmartWhatsAppCleaner:
    def __init__(self):
        self.client = WhatsAppClient()

    def clean(self, confirmar: bool = False) -> str:
        if not confirmar:
            return "Confirmacao necessaria para faxinar WhatsApp. Chame com confirmar=True."
        data = self.client.pendentes()
        return f"Analise de limpeza concluida. Conversas preservadas; dados recebidos: {data[:1000]}"

