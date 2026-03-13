from __future__ import annotations

from dataclasses import dataclass

from .enums import FinancialRisk, PolicyStatus


@dataclass
class FinancialSnapshot:
    saldo_total_cuentas: float
    liquidez_disponible_operativa: float
    dinero_protegido: float
    compromisos_cercanos: float
    margen_libre_real: float
    riesgo_financiero_actual: FinancialRisk


@dataclass
class PolicyResult:
    policy_id: int | None
    nombre: str
    status: PolicyStatus
    severidad: str
    mensaje: str
    soporte: dict


@dataclass
class PurchaseSimulationResult:
    veredicto: str
    impacto_liquidez: float
    margen_restante: float
    politicas: list[PolicyResult]
    objetivos_afectados: list[dict]
    alternativas: list[str]
