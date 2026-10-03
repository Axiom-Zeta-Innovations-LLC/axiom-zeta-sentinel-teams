from typing import Literal

RiskLevel = Literal["green", "yellow", "red"]
ActionType = Literal["pass", "clamp", "retry", "fallback-model", "human-review"]


def classify_risk(drift_score: float) -> RiskLevel:
    if drift_score < 0.20:
        return "green"
    if drift_score < 0.45:
        return "yellow"
    return "red"


def actions_for_risk(risk: RiskLevel) -> list[ActionType]:
    if risk == "green":
        return ["pass"]
    if risk == "yellow":
        return ["clamp", "retry"]
    return ["fallback-model", "human-review"]


def enforce_circuit_breaker(actions: list[ActionType], breaker_open: bool) -> list[ActionType]:
    if not breaker_open:
        return actions

    escalated: list[ActionType] = list(actions)
    if "fallback-model" not in escalated:
        escalated.append("fallback-model")
    if "human-review" not in escalated:
        escalated.append("human-review")
    return escalated
