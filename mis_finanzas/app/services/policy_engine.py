from __future__ import annotations

import json
import sqlite3

from mis_finanzas.domain.enums import PolicyStatus
from mis_finanzas.domain.models import PolicyResult


def evaluate_policies(conn: sqlite3.Connection, *, liquidez: float, margen_libre: float) -> list[PolicyResult]:
    rows = conn.execute(
        "SELECT id, nombre, tipo_politica, severidad, config_json FROM policies WHERE activa=1 ORDER BY prioridad, id"
    ).fetchall()
    results: list[PolicyResult] = []
    for row in rows:
        config = json.loads(row["config_json"] or "{}")
        ptype = row["tipo_politica"]
        status = PolicyStatus.OK
        msg = "Cumple"

        if ptype == "min_liquidity":
            minimo = float(config.get("min", 0))
            if liquidez < minimo:
                status = PolicyStatus.FAIL
                msg = f"Liquidez {liquidez:.2f} por debajo del mínimo {minimo:.2f}"
        elif ptype == "max_free_spend":
            maximo = float(config.get("max", 0))
            if margen_libre > maximo and maximo > 0:
                status = PolicyStatus.WARNING
                msg = f"Margen libre superior al objetivo de gasto libre ({maximo:.2f})"
        elif ptype == "non_negative_margin":
            if margen_libre <= 0:
                status = PolicyStatus.FAIL
                msg = "Margen libre real agotado"

        results.append(
            PolicyResult(
                policy_id=row["id"],
                nombre=row["nombre"],
                status=status,
                severidad=row["severidad"],
                mensaje=msg,
                soporte={"tipo": ptype, "config": config},
            )
        )
    return results
