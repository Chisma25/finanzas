from __future__ import annotations

import sqlite3

from mis_finanzas.app.services.policy_engine import evaluate_policies
from mis_finanzas.domain.enums import FinancialRisk, PolicyStatus
from mis_finanzas.domain.models import FinancialSnapshot


def compute_financial_snapshot(conn: sqlite3.Connection, year: int | None = None, month: int | None = None) -> FinancialSnapshot:
    saldo_total = float(conn.execute("SELECT COALESCE(SUM(saldo),0) FROM cuentas").fetchone()[0])
    liquidez = float(
        conn.execute(
            """
            SELECT COALESCE(SUM(saldo),0) FROM cuentas
            WHERE COALESCE(is_liquid,1)=1 AND COALESCE(is_credit,0)=0 AND COALESCE(include_in_available_cash,1)=1
            """
        ).fetchone()[0]
    )
    dinero_protegido = float(
        conn.execute("SELECT COALESCE(SUM(saldo_reservado_actual),0) FROM buckets WHERE activo=1 AND protegido=1").fetchone()[0]
    )

    if year is None or month is None:
        plan = conn.execute(
            "SELECT gasto_fijo_previsto, inversion_prevista FROM monthly_plans ORDER BY anio DESC, mes DESC LIMIT 1"
        ).fetchone()
    else:
        plan = conn.execute(
            "SELECT gasto_fijo_previsto, inversion_prevista FROM monthly_plans WHERE anio=? AND mes=?",
            (year, month),
        ).fetchone()

    compromisos = 0.0
    if plan:
        compromisos += float(plan["gasto_fijo_previsto"] or 0) + float(plan["inversion_prevista"] or 0)

    margen = max(liquidez - dinero_protegido - compromisos, 0.0)
    policy_results = evaluate_policies(conn, liquidez=liquidez, margen_libre=margen)

    risk = FinancialRisk.STABLE
    if any(p.status == PolicyStatus.FAIL for p in policy_results):
        risk = FinancialRisk.BREACH
    elif margen <= 0:
        risk = FinancialRisk.STRESSED
    elif margen < max(liquidez * 0.15, 100):
        risk = FinancialRisk.TIGHT

    return FinancialSnapshot(
        saldo_total_cuentas=saldo_total,
        liquidez_disponible_operativa=liquidez,
        dinero_protegido=dinero_protegido,
        compromisos_cercanos=compromisos,
        margen_libre_real=margen,
        riesgo_financiero_actual=risk,
    )
