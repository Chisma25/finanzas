from __future__ import annotations

import json
from pathlib import Path

from mis_finanzas.app.services.metrics import compute_financial_snapshot
from mis_finanzas.app.services.policy_engine import evaluate_policies
from mis_finanzas.app.services.simulation_engine import simulate_purchase
from mis_finanzas.infrastructure.db import get_connection, migrate_schema_v2


def _db(tmp_path: Path):
    conn = get_connection(tmp_path / "t.db")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,banco TEXT,tipo TEXT,moneda TEXT,saldo REAL,notas TEXT,creado_en TEXT
        )
        """
    )
    migrate_schema_v2(conn)
    return conn


def test_snapshot_margin_and_risk(tmp_path: Path):
    conn = _db(tmp_path)
    conn.execute("INSERT INTO cuentas (nombre,banco,tipo,moneda,saldo,notas,creado_en,is_liquid,is_credit,include_in_available_cash) VALUES ('op','b','c','EUR',1000,'','2026-01-01',1,0,1)")
    conn.execute("INSERT INTO buckets (nombre,saldo_reservado_actual,protegido,activo,objetivo_monto,aportacion_mensual_objetivo,prioridad) VALUES ('emergencia',300,1,1,1000,50,1)")
    conn.execute("INSERT INTO monthly_plans (anio,mes,gasto_fijo_previsto,inversion_prevista) VALUES (2026,3,200,100)")
    conn.commit()

    snap = compute_financial_snapshot(conn, year=2026, month=3)
    assert round(snap.liquidez_disponible_operativa, 2) == 1000
    assert round(snap.dinero_protegido, 2) == 300
    assert round(snap.compromisos_cercanos, 2) == 300
    assert round(snap.margen_libre_real, 2) == 400
    conn.close()


def test_policy_engine(tmp_path: Path):
    conn = _db(tmp_path)
    cfg = json.dumps({"min": 500})
    conn.execute("INSERT INTO policies (nombre,tipo_politica,severidad,config_json,activa) VALUES ('buffer minimo','min_liquidity','alta',?,1)", (cfg,))
    conn.commit()
    results = evaluate_policies(conn, liquidez=200, margen_libre=120)
    assert results and results[0].status.value == "fail"
    conn.close()


def test_simulate_purchase(tmp_path: Path):
    conn = _db(tmp_path)
    conn.execute("INSERT INTO cuentas (nombre,banco,tipo,moneda,saldo,notas,creado_en,is_liquid,is_credit,include_in_available_cash) VALUES ('op','b','c','EUR',500,'','2026-01-01',1,0,1)")
    conn.execute("INSERT INTO buckets (nombre,saldo_reservado_actual,protegido,activo,objetivo_monto,aportacion_mensual_objetivo,prioridad) VALUES ('emergencia',200,1,1,1000,50,1)")
    conn.commit()

    sim = simulate_purchase(conn, nombre="Portatil", monto=250, tipo_necesidad="capricho", urgencia="baja")
    assert sim.veredicto in {"mejor posponer", "no recomendable", "asumible con ajuste", "recomendable"}
    assert sim.impacto_liquidez == 250
    conn.close()
