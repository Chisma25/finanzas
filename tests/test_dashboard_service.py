from __future__ import annotations

from pathlib import Path

from mis_finanzas.app.services.dashboard_service import get_dashboard_payload
from mis_finanzas.infrastructure.db import get_connection, migrate_schema_v2


def test_dashboard_payload(tmp_path: Path):
    conn = get_connection(tmp_path / 'dash.db')
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            monto REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,banco TEXT,tipo TEXT,moneda TEXT,saldo REAL,notas TEXT,creado_en TEXT
        )
        """
    )
    migrate_schema_v2(conn)
    conn.execute("INSERT INTO cuentas (nombre,banco,tipo,moneda,saldo,notas,creado_en,is_liquid,is_credit,include_in_available_cash) VALUES ('op','b','c','EUR',700,'','2026-01-01',1,0,1)")
    conn.execute("INSERT INTO transacciones (fecha,tipo,categoria,descripcion,monto) VALUES ('2026-03-01','ingreso','salario','nomina',1000)")
    conn.execute("INSERT INTO transacciones (fecha,tipo,categoria,descripcion,monto) VALUES ('2026-03-05','gasto','hogar','alquiler',350)")
    conn.commit()

    payload = get_dashboard_payload(conn, year=2026, month=3)
    assert payload['ingresos'] == 1000
    assert payload['gastos'] == 350
    assert payload['balance'] == 650
    assert payload['liquidez'] == 700
    conn.close()
