from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".mis_finanzas.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row['name'] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def migrate_schema_v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Tablas core para compatibilidad si se invoca CLI sin pasar por GUI
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            banco TEXT NOT NULL,
            tipo TEXT NOT NULL,
            moneda TEXT NOT NULL DEFAULT 'EUR',
            saldo REAL NOT NULL DEFAULT 0,
            notas TEXT,
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inversiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            clave TEXT,
            tipo TEXT NOT NULL,
            broker TEXT,
            monto_invertido REAL NOT NULL DEFAULT 0,
            valor_actual REAL NOT NULL DEFAULT 0,
            riesgo TEXT NOT NULL DEFAULT 'Medio',
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            notas TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recurrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            categoria_tipo TEXT NOT NULL,
            descripcion TEXT,
            monto REAL NOT NULL,
            valor_actual REAL,
            riesgo TEXT,
            broker TEXT,
            cuenta_id INTEGER,
            activa INTEGER NOT NULL DEFAULT 1,
            inicio_year INTEGER NOT NULL DEFAULT 2000,
            inicio_month INTEGER NOT NULL DEFAULT 1,
            ultimo_year INTEGER,
            ultimo_month INTEGER,
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS buckets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            objetivo_monto REAL NOT NULL DEFAULT 0,
            saldo_reservado_actual REAL NOT NULL DEFAULT 0,
            aportacion_mensual_objetivo REAL NOT NULL DEFAULT 0,
            prioridad INTEGER NOT NULL DEFAULT 3,
            protegido INTEGER NOT NULL DEFAULT 0,
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            monto_objetivo REAL NOT NULL,
            monto_actual REAL NOT NULL DEFAULT 0,
            fecha_objetivo TEXT,
            prioridad INTEGER NOT NULL DEFAULT 3,
            estado TEXT NOT NULL DEFAULT 'activa',
            bucket_id INTEGER,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo_politica TEXT NOT NULL,
            descripcion TEXT,
            activa INTEGER NOT NULL DEFAULT 1,
            prioridad INTEGER NOT NULL DEFAULT 3,
            severidad TEXT NOT NULL DEFAULT 'media',
            config_json TEXT,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS monthly_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anio INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            ingreso_previsto REAL NOT NULL DEFAULT 0,
            gasto_fijo_previsto REAL NOT NULL DEFAULT 0,
            gasto_variable_presupuestado REAL NOT NULL DEFAULT 0,
            inversion_prevista REAL NOT NULL DEFAULT 0,
            notas TEXT,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(anio, mes)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS planned_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            categoria TEXT,
            monto REAL NOT NULL,
            tipo_necesidad TEXT NOT NULL,
            urgencia TEXT NOT NULL,
            fecha_prevista TEXT,
            recurrente INTEGER NOT NULL DEFAULT 0,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            anio_base INTEGER,
            mes_base INTEGER,
            favorito INTEGER NOT NULL DEFAULT 0,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenario_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id INTEGER NOT NULL,
            tipo_cambio TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            orden INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anio INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            severidad TEXT NOT NULL,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            explicacion_json TEXT,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cuentas'").fetchone():
        ensure_column(conn, "cuentas", "is_liquid", "is_liquid INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "cuentas", "is_credit", "is_credit INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "cuentas", "include_in_available_cash", "include_in_available_cash INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "cuentas", "is_primary_operating_account", "is_primary_operating_account INTEGER NOT NULL DEFAULT 0")

    conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (2)")
    conn.commit()
