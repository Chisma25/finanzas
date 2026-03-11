from __future__ import annotations

import sqlite3

from mis_finanzas.app.services.metrics import compute_financial_snapshot


def build_monthly_recommendations(conn: sqlite3.Connection, *, year: int, month: int) -> list[dict]:
    snap = compute_financial_snapshot(conn, year=year, month=month)
    recs: list[dict] = []
    if snap.margen_libre_real == 0:
        recs.append(
            {
                "tipo": "alerta",
                "severidad": "alta",
                "titulo": "Margen libre agotado",
                "mensaje": "Reduce gasto variable y pausa compras no esenciales.",
            }
        )
    if snap.dinero_protegido < 300:
        recs.append(
            {
                "tipo": "objetivo",
                "severidad": "media",
                "titulo": "Refuerza tu colchón",
                "mensaje": "Aumenta aportaciones a bucket de emergencia.",
            }
        )
    if not recs:
        recs.append(
            {
                "tipo": "seguimiento",
                "severidad": "baja",
                "titulo": "Mes estable",
                "mensaje": "Mantén el plan actual y revisa objetivos de inversión.",
            }
        )
    return recs
