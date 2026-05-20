from __future__ import annotations


class AutonomousPlanner:
    def plan(self, goal: str) -> list[str]:
        goal = goal.strip()
        if not goal:
            return []
        return [
            "entender objetivo",
            "validar ferramentas necessarias",
            "executar acao reversivel primeiro",
            "pedir confirmacao para acao sensivel",
            f"entregar resultado: {goal}",
        ]

