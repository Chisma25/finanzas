from __future__ import annotations

import sqlite3

from mis_finanzas.app.services.metrics import compute_financial_snapshot
from mis_finanzas.app.services.policy_engine import evaluate_policies
from mis_finanzas.domain.enums import PolicyStatus
from mis_finanzas.domain.models import PurchaseSimulationResult


def simulate_purchase(
    conn: sqlite3.Connection,
    *,
    nombre: str,
    monto: float,
    tipo_necesidad: str,
    urgencia: str,
) -> PurchaseSimulationResult:
    base = compute_financial_snapshot(conn)
    margen_restante = max(base.margen_libre_real - monto, 0.0)
    liquidez_post = max(base.liquidez_disponible_operativa - monto, 0.0)
    policies = evaluate_policies(conn, liquidez=liquidez_post, margen_libre=margen_restante)

    objetivos_afectados: list[dict] = []
    if monto > base.margen_libre_real:
        objetivos_afectados.append({"impacto": "alto", "motivo": "La compra supera el margen libre real"})

    score = 0
    if monto <= base.margen_libre_real:
        score += 2
    if tipo_necesidad == "necesidad":
        score += 2
    if urgencia == "alta":
        score += 1
    if any(p.status == PolicyStatus.FAIL for p in policies):
        score -= 4
    elif any(p.status == PolicyStatus.WARNING for p in policies):
        score -= 1

    if score >= 3:
        verdict = "recomendable"
    elif score >= 1:
        verdict = "asumible con ajuste"
    elif score >= -1:
        verdict = "mejor posponer"
    else:
        verdict = "no recomendable"

    alternativas = [
        "Reducir el monto o fraccionar la compra.",
        "Mover gasto variable del mes para liberar margen.",
        "Posponer al siguiente ciclo mensual.",
    ]

    return PurchaseSimulationResult(
        veredicto=verdict,
        impacto_liquidez=monto,
        margen_restante=margen_restante,
        politicas=policies,
        objetivos_afectados=objetivos_afectados,
        alternativas=alternativas,
    )
