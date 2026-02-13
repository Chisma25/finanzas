#!/usr/bin/env python3
"""Interfaz gráfica local para gestionar finanzas personales."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

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


def formato_eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "_").replace(".", ",").replace("_", ".")


class FinanzasApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Mis Finanzas Personales")
        self.geometry("900x560")
        self.minsize(840, 500)

        self.conn = get_connection()
        init_db(self.conn)

        self._build_ui()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        summary = ttk.LabelFrame(container, text="Resumen", padding=12)
        summary.pack(fill="x")

        self.balance_var = tk.StringVar(value="Balance: 0,00 €")
        self.ingresos_var = tk.StringVar(value="Ingresos: 0,00 €")
        self.gastos_var = tk.StringVar(value="Gastos: 0,00 €")

        ttk.Label(summary, textvariable=self.balance_var).grid(row=0, column=0, sticky="w", padx=8)
        ttk.Label(summary, textvariable=self.ingresos_var).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(summary, textvariable=self.gastos_var).grid(row=0, column=2, sticky="w", padx=8)

        form = ttk.LabelFrame(container, text="Nueva transacción", padding=12)
        form.pack(fill="x", pady=10)

        self.tipo_var = tk.StringVar(value="gasto")
        self.monto_var = tk.StringVar()
        self.categoria_var = tk.StringVar()
        self.descripcion_var = tk.StringVar()
        self.fecha_var = tk.StringVar(value=date.today().isoformat())

        ttk.Label(form, text="Tipo").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.tipo_var,
            values=["ingreso", "gasto"],
            state="readonly",
            width=12,
        ).grid(row=1, column=0, padx=(0, 10), pady=(0, 8), sticky="w")

        ttk.Label(form, text="Monto").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.monto_var, width=14).grid(
            row=1, column=1, padx=(0, 10), pady=(0, 8), sticky="w"
        )

        ttk.Label(form, text="Categoría").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.categoria_var, width=18).grid(
            row=1, column=2, padx=(0, 10), pady=(0, 8), sticky="w"
        )

        ttk.Label(form, text="Fecha (YYYY-MM-DD)").grid(row=0, column=3, sticky="w")
        ttk.Entry(form, textvariable=self.fecha_var, width=14).grid(
            row=1, column=3, padx=(0, 10), pady=(0, 8), sticky="w"
        )

        ttk.Label(form, text="Descripción").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.descripcion_var, width=52).grid(
            row=3, column=0, columnspan=3, sticky="we", pady=(0, 8)
        )

        ttk.Button(form, text="Guardar", command=self.on_add).grid(row=3, column=3, sticky="e")

        table_frame = ttk.LabelFrame(container, text="Movimientos", padding=12)
        table_frame.pack(fill="both", expand=True)

        columns = ("id", "fecha", "tipo", "categoria", "monto", "descripcion")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

        headers = {
            "id": "ID",
            "fecha": "Fecha",
            "tipo": "Tipo",
            "categoria": "Categoría",
            "monto": "Monto",
            "descripcion": "Descripción",
        }
        widths = {"id": 50, "fecha": 100, "tipo": 90, "categoria": 140, "monto": 100, "descripcion": 340}

        for col in columns:
            self.tree.heading(col, text=headers[col])
            anchor = "e" if col == "monto" else "w"
            self.tree.column(col, width=widths[col], anchor=anchor)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Eliminar seleccionada", command=self.on_delete_selected).pack(side="left")
        ttk.Button(actions, text="Borrar todo", command=self.on_reset_all).pack(side="right")

    def refresh_summary(self) -> None:
        total_ingresos = self.conn.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo='ingreso'"
        ).fetchone()[0]
        total_gastos = self.conn.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo='gasto'"
        ).fetchone()[0]
        balance = total_ingresos - total_gastos

        self.balance_var.set(f"Balance: {formato_eur(balance)}")
        self.ingresos_var.set(f"Ingresos: {formato_eur(total_ingresos)}")
        self.gastos_var.set(f"Gastos: {formato_eur(total_gastos)}")

    def refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = self.conn.execute(
            """
            SELECT id, fecha, tipo, categoria, descripcion, monto
            FROM transacciones
            ORDER BY fecha DESC, id DESC
            """
        ).fetchall()

        for row in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    row["id"],
                    row["fecha"],
                    row["tipo"],
                    row["categoria"],
                    formato_eur(row["monto"]),
                    row["descripcion"],
                ),
            )

    def refresh_all(self) -> None:
        self.refresh_summary()
        self.refresh_table()

    def on_add(self) -> None:
        tipo = self.tipo_var.get().strip()
        categoria = self.categoria_var.get().strip()
        descripcion = self.descripcion_var.get().strip()
        fecha_valor = self.fecha_var.get().strip()

        try:
            monto = float(self.monto_var.get().strip())
        except ValueError:
            messagebox.showerror("Monto inválido", "El monto debe ser un número.")
            return

        if monto < 0:
            messagebox.showerror("Monto inválido", "El monto no puede ser negativo.")
            return

        if tipo not in {"ingreso", "gasto"}:
            messagebox.showerror("Tipo inválido", "Selecciona ingreso o gasto.")
            return

        if not categoria or not descripcion:
            messagebox.showerror("Campos obligatorios", "Categoría y descripción son obligatorias.")
            return

        try:
            datetime.strptime(fecha_valor, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha inválida", "La fecha debe estar en formato YYYY-MM-DD.")
            return

        self.conn.execute(
            """
            INSERT INTO transacciones (fecha, tipo, categoria, descripcion, monto)
            VALUES (?, ?, ?, ?, ?)
            """,
            (fecha_valor, tipo, categoria, descripcion, monto),
        )
        self.conn.commit()

        self.monto_var.set("")
        self.categoria_var.set("")
        self.descripcion_var.set("")
        self.fecha_var.set(date.today().isoformat())
        self.tipo_var.set("gasto")

        self.refresh_all()

    def on_delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una transacción primero.")
            return

        item_values = self.tree.item(selected[0], "values")
        trans_id = int(item_values[0])

        if not messagebox.askyesno("Confirmar", f"¿Eliminar la transacción {trans_id}?"):
            return

        self.conn.execute("DELETE FROM transacciones WHERE id = ?", (trans_id,))
        self.conn.commit()
        self.refresh_all()

    def on_reset_all(self) -> None:
        if not messagebox.askyesno("Confirmar", "¿Seguro que quieres borrar todas las transacciones?"):
            return

        self.conn.execute("DELETE FROM transacciones")
        self.conn.commit()
        self.refresh_all()

    def on_close(self) -> None:
        self.conn.close()
        self.destroy()


def main() -> None:
    app = FinanzasApp()
    app.mainloop()


if __name__ == "__main__":
    main()
