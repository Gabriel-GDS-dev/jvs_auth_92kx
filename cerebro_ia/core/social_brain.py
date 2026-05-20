from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SocialDecision:
    mode: str
    should_interrupt: bool
    reason: str


class SocialBrain:
    def decide(self, *, in_call: bool = False, fullscreen: bool = False, coding_minutes: int = 0) -> SocialDecision:
        if in_call:
            return SocialDecision("passivo", False, "reuniao detectada")
        if fullscreen:
            return SocialDecision("passivo", False, "fullscreen ativo")
        if coding_minutes >= 120:
            return SocialDecision("companheiro", True, "2h+ de foco continuo")
        if coding_minutes >= 45:
            return SocialDecision("proativo", False, "usuario em foco")
        return SocialDecision("normal", True, "ambiente livre")

