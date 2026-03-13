from __future__ import annotations

from enum import Enum


class PolicyStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    FAIL = "fail"


class FinancialRisk(str, Enum):
    STABLE = "estable"
    TIGHT = "ajustado"
    STRESSED = "tensionado"
    BREACH = "incumplimiento"
