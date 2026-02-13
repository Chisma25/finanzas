#!/usr/bin/env python3
"""CLI para gestionar finanzas personales en local usando SQLite."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path.home() / ".mis_finanzas.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('ingreso', 'gasto')),
            categoria TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            monto REAL NOT NULL CHECK(monto >= 0)
        )
        """
    )
    conn.commit()


def parse_fecha(value: str | None) -> str:
    if not value:
        return date.today().isoformat()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("La fecha debe tener formato YYYY-MM-DD") from exc


def formato_eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "_").replace(".", ",").replace("_", ".")


def add_transaction(args: argparse.Namespace) -> None:
    conn = get_connection()
    init_db(conn)
    conn.execute(
        """
        INSERT INTO transacciones (fecha, tipo, categoria, descripcion, monto)
        VALUES (?, ?, ?, ?, ?)
        """,
        (args.fecha, args.tipo, args.categoria.strip(), args.descripcion.strip(), args.monto),
    )
    conn.commit()
    conn.close()
    print("✅ Transacción guardada.")


def list_transactions(args: argparse.Namespace) -> None:
    conn = get_connection()
    init_db(conn)
    rows = conn.execute(
        """
        SELECT id, fecha, tipo, categoria, descripcion, monto
        FROM transacciones
        ORDER BY fecha DESC, id DESC
        LIMIT ?
        """,
        (args.limite,),
    ).fetchall()
    conn.close()

    if not rows:
        print("No hay transacciones registradas.")
        return

    print("\nID | Fecha       | Tipo    | Categoría       | Monto      | Descripción")
    print("-" * 78)
    for row in rows:
        print(
            f"{row['id']:>2} | {row['fecha']} | {row['tipo']:<7} | "
            f"{row['categoria'][:14]:<14} | {formato_eur(row['monto']):>10} | {row['descripcion']}"
        )


def delete_transaction(args: argparse.Namespace) -> None:
    conn = get_connection()
    init_db(conn)
    result = conn.execute("DELETE FROM transacciones WHERE id = ?", (args.id,))
    conn.commit()
    conn.close()
    if result.rowcount:
        print(f"✅ Transacción {args.id} eliminada.")
    else:
        print(f"⚠️ No existe la transacción {args.id}.")


def summary(_: argparse.Namespace) -> None:
    conn = get_connection()
    init_db(conn)
    total_ingresos = conn.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo='ingreso'"
    ).fetchone()[0]
    total_gastos = conn.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo='gasto'"
    ).fetchone()[0]
    conn.close()

    balance = total_ingresos - total_gastos
    print("\nResumen financiero")
    print("-" * 24)
    print(f"Ingresos: {formato_eur(total_ingresos)}")
    print(f"Gastos:   {formato_eur(total_gastos)}")
    print(f"Balance:  {formato_eur(balance)}")


def reset_data(args: argparse.Namespace) -> None:
    if not args.si:
        print("Para borrar todo usa también: --si")
        return
    conn = get_connection()
    init_db(conn)
    conn.execute("DELETE FROM transacciones")
    conn.commit()
    conn.close()
    print("✅ Datos eliminados.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gestor local de finanzas personales")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_cmd = subparsers.add_parser("agregar", help="Registrar una transacción")
    add_cmd.add_argument("--tipo", choices=["ingreso", "gasto"], required=True)
    add_cmd.add_argument("--monto", type=float, required=True)
    add_cmd.add_argument("--categoria", required=True)
    add_cmd.add_argument("--descripcion", required=True)
    add_cmd.add_argument("--fecha", type=parse_fecha, default=date.today().isoformat())
    add_cmd.set_defaults(func=add_transaction)

    list_cmd = subparsers.add_parser("listar", help="Listar transacciones")
    list_cmd.add_argument("--limite", type=int, default=20)
    list_cmd.set_defaults(func=list_transactions)

    del_cmd = subparsers.add_parser("eliminar", help="Eliminar por ID")
    del_cmd.add_argument("id", type=int)
    del_cmd.set_defaults(func=delete_transaction)

    summary_cmd = subparsers.add_parser("resumen", help="Mostrar resumen")
    summary_cmd.set_defaults(func=summary)

    reset_cmd = subparsers.add_parser("reset", help="Borrar todas las transacciones")
    reset_cmd.add_argument("--si", action="store_true", help="Confirmar borrado")
    reset_cmd.set_defaults(func=reset_data)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
