from __future__ import annotations

import sqlite3
from datetime import date

from mis_finanzas.app.services.metrics import compute_financial_snapshot


def get_dashboard_payload(conn: sqlite3.Connection, *, year: int | None = None, month: int | None = None) -> dict:
    if year is None or month is None:
        today = date.today()
        year, month = today.year, today.month

    start = f"{year:04d}-{month:02d}-01"
    end_year = year + 1 if month == 12 else year
    end_month = 1 if month == 12 else month + 1
    end = f"{end_year:04d}-{end_month:02d}-01"

    rows = conn.execute(
        """
        SELECT tipo, COALESCE(SUM(monto), 0) AS total
        FROM transacciones
        WHERE fecha >= ? AND fecha < ?
        GROUP BY tipo
        """,
        (start, end),
    ).fetchall()
    totals = {r["tipo"]: float(r["total"] or 0) for r in rows}
    ingresos = totals.get("ingreso", 0.0)
    gastos = totals.get("gasto", 0.0)

    snap = compute_financial_snapshot(conn, year=year, month=month)
    return {
        "periodo": f"{year:04d}-{month:02d}",
        "ingresos": ingresos,
        "gastos": gastos,
        "balance": ingresos - gastos,
        "saldo_total_cuentas": snap.saldo_total_cuentas,
        "liquidez": snap.liquidez_disponible_operativa,
        "protegido": snap.dinero_protegido,
        "compromisos": snap.compromisos_cercanos,
        "margen": snap.margen_libre_real,
        "riesgo": snap.riesgo_financiero_actual.value,
    }
