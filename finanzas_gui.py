#!/usr/bin/env python3
"""Interfaz gráfica local para finanzas personales con paneles avanzados."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

DB_PATH = Path.home() / ".mis_finanzas.db"
MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


@dataclass
class RecurrenceResult:
    created: int = 0
    skipped: int = 0


def formato_eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "_").replace(".", ",").replace("_", ".")


def normalize_asset(name: str) -> str:
    return " ".join(name.strip().lower().split())


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


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
    ensure_column(conn, "transacciones", "cuenta_id", "cuenta_id INTEGER")
    ensure_column(conn, "transacciones", "origen_regla_id", "origen_regla_id INTEGER")

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
            creado_en TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inversiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            clave TEXT NOT NULL UNIQUE,
            tipo TEXT NOT NULL,
            broker TEXT,
            monto_invertido REAL NOT NULL CHECK(monto_invertido >= 0),
            valor_actual REAL NOT NULL CHECK(valor_actual >= 0),
            riesgo TEXT NOT NULL,
            fecha_actualizacion TEXT NOT NULL,
            notas TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recurrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL CHECK(tipo IN ('gasto', 'inversion')),
            nombre TEXT NOT NULL,
            categoria_tipo TEXT NOT NULL,
            descripcion TEXT,
            monto REAL NOT NULL,
            valor_actual REAL,
            riesgo TEXT,
            broker TEXT,
            cuenta_id INTEGER,
            activa INTEGER NOT NULL DEFAULT 1,
            inicio_year INTEGER NOT NULL,
            inicio_month INTEGER NOT NULL,
            ultimo_year INTEGER,
            ultimo_month INTEGER,
            creado_en TEXT NOT NULL
        )
        """
    )
    conn.commit()


def parse_iso_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def month_add(year: int, month: int, delta: int) -> tuple[int, int]:
    total = (year * 12 + month - 1) + delta
    return total // 12, total % 12 + 1


def month_lte(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[0] or (a[0] == b[0] and a[1] <= b[1])


def get_available_cash(conn: sqlite3.Connection) -> float:
    ingresos = conn.execute("SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo='ingreso'").fetchone()[0]
    gastos = conn.execute("SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo='gasto'").fetchone()[0]
    invertido = conn.execute("SELECT COALESCE(SUM(monto_invertido), 0) FROM inversiones").fetchone()[0]
    return ingresos - gastos - invertido


def upsert_investment(
    conn: sqlite3.Connection,
    *,
    nombre: str,
    tipo: str,
    broker: str,
    invertido_delta: float,
    valor_actual_delta: float,
    riesgo: str,
    fecha_text: str,
) -> None:
    clave = normalize_asset(nombre)
    current = conn.execute("SELECT * FROM inversiones WHERE clave = ?", (clave,)).fetchone()

    if current is None:
        conn.execute(
            """
            INSERT INTO inversiones (nombre, clave, tipo, broker, monto_invertido, valor_actual, riesgo, fecha_actualizacion, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (nombre.strip(), clave, tipo, broker.strip(), invertido_delta, valor_actual_delta, riesgo, fecha_text),
        )
    else:
        conn.execute(
            """
            UPDATE inversiones
            SET monto_invertido = monto_invertido + ?,
                valor_actual = valor_actual + ?,
                broker = ?,
                tipo = ?,
                riesgo = ?,
                fecha_actualizacion = ?
            WHERE id = ?
            """,
            (
                invertido_delta,
                valor_actual_delta,
                broker.strip() or current["broker"],
                tipo or current["tipo"],
                riesgo or current["riesgo"],
                fecha_text,
                current["id"],
            ),
        )


def apply_recurring_entries(conn: sqlite3.Connection, today: date | None = None) -> RecurrenceResult:
    now = today or date.today()
    current = (now.year, now.month)
    result = RecurrenceResult()

    rules = conn.execute("SELECT * FROM recurrencias WHERE activa = 1 ORDER BY id").fetchall()
    for rule in rules:
        if rule["ultimo_year"] is None or rule["ultimo_month"] is None:
            next_month = (rule["inicio_year"], rule["inicio_month"])
        else:
            next_month = month_add(rule["ultimo_year"], rule["ultimo_month"], 1)

        while month_lte(next_month, current):
            y, m = next_month
            fecha = f"{y:04d}-{m:02d}-01"

            if rule["tipo"] == "gasto":
                disponible = get_available_cash(conn)
                if rule["monto"] > disponible:
                    result.skipped += 1
                    break

                conn.execute(
                    """
                    INSERT INTO transacciones (fecha, tipo, categoria, descripcion, monto, cuenta_id, origen_regla_id)
                    VALUES (?, 'gasto', ?, ?, ?, ?, ?)
                    """,
                    (
                        fecha,
                        rule["categoria_tipo"],
                        f"{rule['descripcion'] or rule['nombre']} (recurrente)",
                        rule["monto"],
                        rule["cuenta_id"],
                        rule["id"],
                    ),
                )
                if rule["cuenta_id"]:
                    conn.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (rule["monto"], rule["cuenta_id"]))

            if rule["tipo"] == "inversion":
                disponible = get_available_cash(conn)
                if rule["monto"] > disponible:
                    result.skipped += 1
                    break

                upsert_investment(
                    conn,
                    nombre=rule["nombre"],
                    tipo=rule["categoria_tipo"],
                    broker=rule["broker"] or "",
                    invertido_delta=rule["monto"],
                    valor_actual_delta=rule["valor_actual"] if rule["valor_actual"] is not None else rule["monto"],
                    riesgo=rule["riesgo"] or "Medio",
                    fecha_text=fecha,
                )
                if rule["cuenta_id"]:
                    conn.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (rule["monto"], rule["cuenta_id"]))

            conn.execute(
                "UPDATE recurrencias SET ultimo_year = ?, ultimo_month = ? WHERE id = ?",
                (y, m, rule["id"]),
            )
            result.created += 1
            next_month = month_add(y, m, 1)

    conn.commit()
    return result


class EditAccountDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, data: sqlite3.Row):
        super().__init__(parent)
        self.title("Editar cuenta")
        self.resizable(False, False)
        self.result = None

        self.nombre = tk.StringVar(value=data["nombre"])
        self.banco = tk.StringVar(value=data["banco"])
        self.tipo = tk.StringVar(value=data["tipo"])
        self.moneda = tk.StringVar(value=data["moneda"])
        self.saldo = tk.StringVar(value=str(data["saldo"]))

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        for i, (label, var) in enumerate(
            [
                ("Nombre", self.nombre),
                ("Banco", self.banco),
                ("Tipo", self.tipo),
                ("Moneda", self.moneda),
                ("Saldo", self.saldo),
            ]
        ):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w")
            ttk.Entry(frm, textvariable=var, width=28).grid(row=i, column=1, pady=2, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Guardar", command=self.on_save).pack(side="right")

        self.grab_set()
        self.wait_visibility()

    def on_save(self) -> None:
        try:
            saldo = float(self.saldo.get().strip())
        except ValueError:
            messagebox.showerror("Saldo inválido", "Saldo no numérico", parent=self)
            return

        if not self.nombre.get().strip() or not self.banco.get().strip():
            messagebox.showerror("Campos", "Nombre y banco son obligatorios", parent=self)
            return

        self.result = {
            "nombre": self.nombre.get().strip(),
            "banco": self.banco.get().strip(),
            "tipo": self.tipo.get().strip() or "Corriente",
            "moneda": self.moneda.get().strip() or "EUR",
            "saldo": saldo,
        }
        self.destroy()


class EditInvestmentDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, data: sqlite3.Row):
        super().__init__(parent)
        self.title("Editar posición de inversión")
        self.resizable(False, False)
        self.result = None

        self.nombre = tk.StringVar(value=data["nombre"])
        self.tipo = tk.StringVar(value=data["tipo"])
        self.broker = tk.StringVar(value=data["broker"] or "")
        self.invertido = tk.StringVar(value=str(data["monto_invertido"]))
        self.actual = tk.StringVar(value=str(data["valor_actual"]))
        self.riesgo = tk.StringVar(value=data["riesgo"])

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        fields = [
            ("Activo", self.nombre),
            ("Tipo", self.tipo),
            ("Broker", self.broker),
            ("Total invertido", self.invertido),
            ("Valor actual", self.actual),
            ("Riesgo", self.riesgo),
        ]
        for i, (label, var) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w")
            ttk.Entry(frm, textvariable=var, width=30).grid(row=i, column=1, pady=2, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Guardar", command=self.on_save).pack(side="right")

        self.grab_set()
        self.wait_visibility()

    def on_save(self) -> None:
        try:
            invertido = float(self.invertido.get().strip())
            actual = float(self.actual.get().strip())
        except ValueError:
            messagebox.showerror("Valores", "Invertido y actual deben ser numéricos", parent=self)
            return

        if not self.nombre.get().strip():
            messagebox.showerror("Campos", "Activo obligatorio", parent=self)
            return

        self.result = {
            "nombre": self.nombre.get().strip(),
            "tipo": self.tipo.get().strip() or "ETF",
            "broker": self.broker.get().strip(),
            "monto_invertido": max(invertido, 0),
            "valor_actual": max(actual, 0),
            "riesgo": self.riesgo.get().strip() or "Medio",
        }
        self.destroy()


class FinanzasApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Mis Finanzas Personales")
        self.geometry("1320x810")
        self.minsize(1200, 740)
        self.configure(bg="#F2F5FA")

        self.conn = get_connection()
        init_db(self.conn)
        apply_recurring_entries(self.conn)

        self._set_style()
        self._build_ui()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _set_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Root.TFrame", background="#F2F5FA")
        style.configure("Card.TLabelframe", background="#FFFFFF")
        style.configure("Card.TLabelframe.Label", background="#FFFFFF", foreground="#1D2A3A", font=("Segoe UI", 10, "bold"))
        style.configure("Header.TLabel", background="#F2F5FA", foreground="#1D2A3A", font=("Segoe UI", 18, "bold"))
        style.configure("SubHeader.TLabel", background="#F2F5FA", foreground="#607089", font=("Segoe UI", 10))
        style.configure("MetricValue.TLabel", background="#FFFFFF", foreground="#1D2A3A", font=("Segoe UI", 16, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Panel financiero personal", style="Header.TLabel").pack(anchor="w")
        self.available_var = tk.StringVar(value="Disponible: 0,00 €")
        ttk.Label(root, textvariable=self.available_var, style="SubHeader.TLabel").pack(anchor="w", pady=(0, 8))

        filters = ttk.Frame(root, style="Root.TFrame")
        filters.pack(fill="x", pady=(0, 8))

        ttk.Label(filters, text="Año", style="SubHeader.TLabel").pack(side="left")
        self.year_var = tk.StringVar(value=str(date.today().year))
        self.year_combo = ttk.Combobox(filters, textvariable=self.year_var, state="readonly", width=8)
        self.year_combo.pack(side="left", padx=(6, 12))

        ttk.Label(filters, text="Mes", style="SubHeader.TLabel").pack(side="left")
        self.month_var = tk.StringVar(value=f"{date.today().month:02d} - {MONTH_NAMES[date.today().month]}")
        self.month_combo = ttk.Combobox(
            filters,
            textvariable=self.month_var,
            state="readonly",
            width=13,
            values=[f"{m:02d} - {MONTH_NAMES[m]}" for m in range(1, 13)],
        )
        self.month_combo.pack(side="left", padx=(6, 12))

        ttk.Button(filters, text="Aplicar periodo", command=self.refresh_all, style="Accent.TButton").pack(side="left")
        ttk.Button(filters, text="Aplicar recurrencias ahora", command=self.apply_recurrences_now).pack(side="left", padx=(8, 0))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.dashboard_tab = ttk.Frame(self.notebook, padding=10)
        self.mov_tab = ttk.Frame(self.notebook, padding=10)
        self.accounts_tab = ttk.Frame(self.notebook, padding=10)
        self.investments_tab = ttk.Frame(self.notebook, padding=10)
        self.recurrences_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.dashboard_tab, text="Resumen")
        self.notebook.add(self.mov_tab, text="Movimientos")
        self.notebook.add(self.accounts_tab, text="Cuentas")
        self.notebook.add(self.investments_tab, text="Inversiones")
        self.notebook.add(self.recurrences_tab, text="Recurrencias")

        self._build_dashboard_tab()
        self._build_movimientos_tab()
        self._build_accounts_tab()
        self._build_investments_tab()
        self._build_recurrences_tab()

    def _build_dashboard_tab(self) -> None:
        cards = ttk.Frame(self.dashboard_tab)
        cards.pack(fill="x")

        self.metric_balance = tk.StringVar(value="0,00 €")
        self.metric_income = tk.StringVar(value="0,00 €")
        self.metric_expenses = tk.StringVar(value="0,00 €")
        self.metric_saving_rate = tk.StringVar(value="0 %")
        self.metric_accounts = tk.StringVar(value="0,00 €")
        self.metric_invested = tk.StringVar(value="0,00 €")

        card_data = [
            ("Balance periodo", self.metric_balance),
            ("Ingresos", self.metric_income),
            ("Gastos", self.metric_expenses),
            ("Tasa ahorro", self.metric_saving_rate),
            ("Saldo cuentas", self.metric_accounts),
            ("Valor cartera", self.metric_invested),
        ]

        for idx, (title, var) in enumerate(card_data):
            frame = ttk.LabelFrame(cards, text=f" {title} ", style="Card.TLabelframe")
            frame.grid(row=0, column=idx, padx=4, sticky="nsew")
            ttk.Label(frame, textvariable=var, style="MetricValue.TLabel").pack(padx=10, pady=12)
            cards.columnconfigure(idx, weight=1)

        graph_frame = ttk.LabelFrame(self.dashboard_tab, text=" Evolución 6 meses ", style="Card.TLabelframe")
        graph_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.chart_canvas = tk.Canvas(graph_frame, bg="#FFFFFF", height=260, highlightthickness=0)
        self.chart_canvas.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_movimientos_tab(self) -> None:
        top = ttk.LabelFrame(self.mov_tab, text=" Nuevo movimiento ", style="Card.TLabelframe", padding=10)
        top.pack(fill="x")

        self.mov_tipo = tk.StringVar(value="gasto")
        self.mov_monto = tk.StringVar()
        self.mov_categoria = tk.StringVar()
        self.mov_descripcion = tk.StringVar()
        self.mov_fecha = tk.StringVar(value=date.today().isoformat())
        self.mov_cuenta = tk.StringVar(value="Sin cuenta")
        self.mov_recurrente = tk.BooleanVar(value=False)

        ttk.Label(top, text="Tipo").grid(row=0, column=0, sticky="w")
        ttk.Combobox(top, textvariable=self.mov_tipo, values=["ingreso", "gasto"], state="readonly", width=12).grid(row=1, column=0)

        ttk.Label(top, text="Monto").grid(row=0, column=1, sticky="w")
        ttk.Entry(top, textvariable=self.mov_monto, width=12).grid(row=1, column=1)

        ttk.Label(top, text="Categoría").grid(row=0, column=2, sticky="w")
        ttk.Entry(top, textvariable=self.mov_categoria, width=16).grid(row=1, column=2)

        ttk.Label(top, text="Cuenta").grid(row=0, column=3, sticky="w")
        self.mov_account_combo = ttk.Combobox(top, textvariable=self.mov_cuenta, state="readonly", width=22)
        self.mov_account_combo.grid(row=1, column=3)

        ttk.Label(top, text="Fecha").grid(row=0, column=4, sticky="w")
        ttk.Entry(top, textvariable=self.mov_fecha, width=12).grid(row=1, column=4)

        ttk.Label(top, text="Descripción").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.mov_descripcion, width=60).grid(row=3, column=0, columnspan=4, sticky="we")
        ttk.Checkbutton(top, text="Recurrente mensual (solo gastos)", variable=self.mov_recurrente).grid(row=3, column=4, sticky="w")
        ttk.Button(top, text="Guardar movimiento", command=self.add_movimiento, style="Accent.TButton").grid(row=3, column=5, padx=(8, 0))

        table_frame = ttk.LabelFrame(self.mov_tab, text=" Movimientos del periodo ", style="Card.TLabelframe", padding=8)
        table_frame.pack(fill="both", expand=True, pady=(10, 0))

        cols = ("id", "fecha", "tipo", "categoria", "cuenta", "monto", "descripcion")
        self.mov_tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "fecha": 100, "tipo": 80, "categoria": 120, "cuenta": 170, "monto": 110, "descripcion": 360}
        headers = {
            "id": "ID",
            "fecha": "Fecha",
            "tipo": "Tipo",
            "categoria": "Categoría",
            "cuenta": "Cuenta",
            "monto": "Monto",
            "descripcion": "Descripción",
        }

        for col in cols:
            self.mov_tree.heading(col, text=headers[col])
            self.mov_tree.column(col, width=widths[col], anchor="e" if col == "monto" else "w")

        scr = ttk.Scrollbar(table_frame, orient="vertical", command=self.mov_tree.yview)
        self.mov_tree.configure(yscrollcommand=scr.set)
        self.mov_tree.pack(side="left", fill="both", expand=True)
        scr.pack(side="right", fill="y")

        actions = ttk.Frame(self.mov_tab)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Eliminar seleccionada", command=self.delete_movimiento).pack(side="left")
        ttk.Button(actions, text="Exportar CSV", command=self.export_movimientos_csv).pack(side="left", padx=(8, 0))

    def _build_accounts_tab(self) -> None:
        form = ttk.LabelFrame(self.accounts_tab, text=" Nueva cuenta bancaria ", style="Card.TLabelframe", padding=10)
        form.pack(fill="x")

        self.acc_nombre = tk.StringVar()
        self.acc_banco = tk.StringVar()
        self.acc_tipo = tk.StringVar(value="Corriente")
        self.acc_moneda = tk.StringVar(value="EUR")
        self.acc_saldo = tk.StringVar(value="0")

        ttk.Label(form, text="Nombre").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.acc_nombre, width=20).grid(row=1, column=0)
        ttk.Label(form, text="Banco").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.acc_banco, width=20).grid(row=1, column=1)
        ttk.Label(form, text="Tipo").grid(row=0, column=2, sticky="w")
        ttk.Combobox(form, textvariable=self.acc_tipo, values=["Corriente", "Ahorro", "Nómina", "Broker", "Otra"], state="readonly", width=14).grid(row=1, column=2)
        ttk.Label(form, text="Moneda").grid(row=0, column=3, sticky="w")
        ttk.Combobox(form, textvariable=self.acc_moneda, values=["EUR", "USD", "GBP"], state="readonly", width=8).grid(row=1, column=3)
        ttk.Label(form, text="Saldo").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.acc_saldo, width=12).grid(row=1, column=4)
        ttk.Button(form, text="Guardar cuenta", command=self.add_account, style="Accent.TButton").grid(row=1, column=5, padx=(8, 0))

        self.accounts_total_var = tk.StringVar(value="Saldo agregado: 0,00 €")
        ttk.Label(self.accounts_tab, textvariable=self.accounts_total_var, style="Header.TLabel").pack(anchor="w", pady=(8, 6))

        table = ttk.LabelFrame(self.accounts_tab, text=" Cuentas registradas ", style="Card.TLabelframe", padding=8)
        table.pack(fill="both", expand=True)

        cols = ("id", "nombre", "banco", "tipo", "moneda", "saldo")
        self.accounts_tree = ttk.Treeview(table, columns=cols, show="headings")
        for c, t, w in [("id", "ID", 50), ("nombre", "Nombre", 190), ("banco", "Banco", 170), ("tipo", "Tipo", 120), ("moneda", "Moneda", 90), ("saldo", "Saldo", 130)]:
            self.accounts_tree.heading(c, text=t)
            self.accounts_tree.column(c, width=w, anchor="e" if c == "saldo" else "w")

        scr = ttk.Scrollbar(table, orient="vertical", command=self.accounts_tree.yview)
        self.accounts_tree.configure(yscrollcommand=scr.set)
        self.accounts_tree.pack(side="left", fill="both", expand=True)
        scr.pack(side="right", fill="y")

        actions = ttk.Frame(self.accounts_tab)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Editar cuenta", command=self.edit_account).pack(side="left")
        ttk.Button(actions, text="Eliminar cuenta", command=self.delete_account).pack(side="left", padx=(8, 0))

    def _build_investments_tab(self) -> None:
        form = ttk.LabelFrame(self.investments_tab, text=" Nueva inversión / aporte ", style="Card.TLabelframe", padding=10)
        form.pack(fill="x")

        self.inv_nombre = tk.StringVar()
        self.inv_tipo = tk.StringVar(value="Acción")
        self.inv_broker = tk.StringVar()
        self.inv_invertido = tk.StringVar()
        self.inv_actual = tk.StringVar()
        self.inv_riesgo = tk.StringVar(value="Medio")
        self.inv_fecha = tk.StringVar(value=date.today().isoformat())
        self.inv_cuenta = tk.StringVar(value="Sin cuenta")
        self.inv_recurrente = tk.BooleanVar(value=False)

        ttk.Label(form, text="Activo").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.inv_nombre, width=18).grid(row=1, column=0)
        ttk.Label(form, text="Tipo").grid(row=0, column=1, sticky="w")
        ttk.Combobox(form, textvariable=self.inv_tipo, values=["Acción", "ETF", "Fondo", "Cripto", "Renta fija", "Otro"], state="readonly", width=12).grid(row=1, column=1)
        ttk.Label(form, text="Broker").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.inv_broker, width=16).grid(row=1, column=2)
        ttk.Label(form, text="Aporte invertido").grid(row=0, column=3, sticky="w")
        ttk.Entry(form, textvariable=self.inv_invertido, width=12).grid(row=1, column=3)
        ttk.Label(form, text="Valor actual del aporte").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.inv_actual, width=14).grid(row=1, column=4)
        ttk.Label(form, text="Cuenta origen").grid(row=0, column=5, sticky="w")
        self.inv_account_combo = ttk.Combobox(form, textvariable=self.inv_cuenta, state="readonly", width=18)
        self.inv_account_combo.grid(row=1, column=5)
        ttk.Label(form, text="Riesgo").grid(row=0, column=6, sticky="w")
        ttk.Combobox(form, textvariable=self.inv_riesgo, values=["Bajo", "Medio", "Alto"], state="readonly", width=10).grid(row=1, column=6)
        ttk.Checkbutton(form, text="Recurrente mensual", variable=self.inv_recurrente).grid(row=1, column=7, padx=(8, 0), sticky="w")
        ttk.Button(form, text="Guardar inversión", command=self.add_investment, style="Accent.TButton").grid(row=1, column=8, padx=(8, 0))

        self.inv_summary_var = tk.StringVar(value="Invertido: 0,00 € | Valor actual: 0,00 € | Rentabilidad: 0,00 €")
        ttk.Label(self.investments_tab, textvariable=self.inv_summary_var, style="Header.TLabel").pack(anchor="w", pady=(8, 6))

        chart_box = ttk.LabelFrame(self.investments_tab, text=" Composición de cartera ", style="Card.TLabelframe", padding=8)
        chart_box.pack(fill="x")
        self.invest_chart = tk.Canvas(chart_box, bg="#FFFFFF", height=150, highlightthickness=0)
        self.invest_chart.pack(fill="x")

        table = ttk.LabelFrame(self.investments_tab, text=" Posiciones agregadas ", style="Card.TLabelframe", padding=8)
        table.pack(fill="both", expand=True, pady=(10, 0))

        cols = ("id", "nombre", "tipo", "broker", "invertido", "actual", "riesgo", "rent")
        self.inv_tree = ttk.Treeview(table, columns=cols, show="headings")
        for c, t, w in [
            ("id", "ID", 50),
            ("nombre", "Activo", 170),
            ("tipo", "Tipo", 90),
            ("broker", "Broker", 110),
            ("invertido", "Invertido", 120),
            ("actual", "Actual", 120),
            ("riesgo", "Riesgo", 90),
            ("rent", "P/L", 110),
        ]:
            self.inv_tree.heading(c, text=t)
            self.inv_tree.column(c, width=w, anchor="e" if c in {"invertido", "actual", "rent"} else "w")

        scr = ttk.Scrollbar(table, orient="vertical", command=self.inv_tree.yview)
        self.inv_tree.configure(yscrollcommand=scr.set)
        self.inv_tree.pack(side="left", fill="both", expand=True)
        scr.pack(side="right", fill="y")

        actions = ttk.Frame(self.investments_tab)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Editar posición", command=self.edit_investment).pack(side="left")
        ttk.Button(actions, text="Actualizar valor actual", command=self.quick_update_investment_value).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Eliminar posición", command=self.delete_investment).pack(side="left", padx=(8, 0))

    def _build_recurrences_tab(self) -> None:
        info = ttk.Label(self.recurrences_tab, text="Puedes activar/desactivar reglas recurrentes mensuales de gastos e inversiones.")
        info.pack(anchor="w", pady=(0, 8))

        table = ttk.LabelFrame(self.recurrences_tab, text=" Reglas recurrentes ", style="Card.TLabelframe", padding=8)
        table.pack(fill="both", expand=True)

        cols = ("id", "tipo", "nombre", "categoria", "monto", "cuenta", "estado", "ultimo")
        self.rec_tree = ttk.Treeview(table, columns=cols, show="headings")
        for c, t, w in [
            ("id", "ID", 50),
            ("tipo", "Tipo", 90),
            ("nombre", "Nombre", 190),
            ("categoria", "Categoría/Tipo", 140),
            ("monto", "Monto", 110),
            ("cuenta", "Cuenta", 180),
            ("estado", "Estado", 80),
            ("ultimo", "Último mes", 110),
        ]:
            self.rec_tree.heading(c, text=t)
            self.rec_tree.column(c, width=w, anchor="e" if c == "monto" else "w")

        scr = ttk.Scrollbar(table, orient="vertical", command=self.rec_tree.yview)
        self.rec_tree.configure(yscrollcommand=scr.set)
        self.rec_tree.pack(side="left", fill="both", expand=True)
        scr.pack(side="right", fill="y")

        actions = ttk.Frame(self.recurrences_tab)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Activar/Desactivar", command=self.toggle_recurrence).pack(side="left")
        ttk.Button(actions, text="Eliminar regla", command=self.delete_recurrence).pack(side="left", padx=(8, 0))

    def selected_year_month(self) -> tuple[int, int]:
        try:
            year = int(self.year_var.get().strip())
        except ValueError:
            year = date.today().year

        month_txt = self.month_var.get().strip()
        month = int(month_txt[:2]) if len(month_txt) >= 2 and month_txt[:2].isdigit() else date.today().month
        return year, month

    def refresh_period_options(self) -> None:
        years = {date.today().year}
        rows = self.conn.execute("SELECT fecha FROM transacciones").fetchall()
        for row in rows:
            try:
                years.add(parse_iso_date(row["fecha"]).year)
            except ValueError:
                continue

        values = [str(y) for y in sorted(years)]
        self.year_combo["values"] = values
        if self.year_var.get() not in values:
            self.year_var.set(values[-1])

    def refresh_accounts_combo(self) -> None:
        rows = self.conn.execute("SELECT id, nombre, banco FROM cuentas ORDER BY nombre").fetchall()
        self.account_map = {"Sin cuenta": None}
        opts = ["Sin cuenta"]
        for row in rows:
            label = f"{row['nombre']} ({row['banco']})"
            self.account_map[label] = row["id"]
            opts.append(label)
        self.mov_account_combo["values"] = opts
        self.inv_account_combo["values"] = opts
        if self.mov_cuenta.get() not in opts:
            self.mov_cuenta.set("Sin cuenta")
        if self.inv_cuenta.get() not in opts:
            self.inv_cuenta.set("Sin cuenta")

    def get_filtered_movimientos(self) -> list[sqlite3.Row]:
        year, month = self.selected_year_month()
        start = f"{year:04d}-{month:02d}-01"
        end_y, end_m = month_add(year, month, 1)
        end = f"{end_y:04d}-{end_m:02d}-01"

        return self.conn.execute(
            """
            SELECT t.id, t.fecha, t.tipo, t.categoria, t.descripcion, t.monto, c.nombre AS cuenta_nombre
            FROM transacciones t
            LEFT JOIN cuentas c ON c.id = t.cuenta_id
            WHERE t.fecha >= ? AND t.fecha < ?
            ORDER BY t.fecha DESC, t.id DESC
            """,
            (start, end),
        ).fetchall()

    def refresh_movimientos(self) -> None:
        for item in self.mov_tree.get_children():
            self.mov_tree.delete(item)

        for row in self.get_filtered_movimientos():
            self.mov_tree.insert(
                "",
                "end",
                values=(
                    row["id"],
                    row["fecha"],
                    row["tipo"],
                    row["categoria"],
                    row["cuenta_nombre"] or "-",
                    formato_eur(row["monto"]),
                    row["descripcion"],
                ),
            )

    def refresh_dashboard(self) -> None:
        rows = self.get_filtered_movimientos()
        ingresos = sum(r["monto"] for r in rows if r["tipo"] == "ingreso")
        gastos = sum(r["monto"] for r in rows if r["tipo"] == "gasto")
        balance = ingresos - gastos
        tasa = (balance / ingresos * 100) if ingresos else 0

        cuentas_total = self.conn.execute("SELECT COALESCE(SUM(saldo), 0) FROM cuentas").fetchone()[0]
        cartera = self.conn.execute("SELECT COALESCE(SUM(valor_actual), 0) FROM inversiones").fetchone()[0]

        self.metric_balance.set(formato_eur(balance))
        self.metric_income.set(formato_eur(ingresos))
        self.metric_expenses.set(formato_eur(gastos))
        self.metric_saving_rate.set(f"{tasa:.1f}%")
        self.metric_accounts.set(formato_eur(cuentas_total))
        self.metric_invested.set(formato_eur(cartera))
        self.available_var.set(f"Disponible (sin crédito): {formato_eur(get_available_cash(self.conn))}")

        self.draw_monthly_chart()

    def draw_monthly_chart(self) -> None:
        self.chart_canvas.delete("all")
        width = max(640, self.chart_canvas.winfo_width())
        height = max(220, self.chart_canvas.winfo_height())
        pad = 40

        today = date.today()
        months = []
        y, m = today.year, today.month
        for _ in range(6):
            months.append((y, m))
            y, m = month_add(y, m, -1)
        months.reverse()

        max_value = 1.0
        series = []
        for y, m in months:
            start = f"{y:04d}-{m:02d}-01"
            ey, em = month_add(y, m, 1)
            end = f"{ey:04d}-{em:02d}-01"
            inc = self.conn.execute(
                "SELECT COALESCE(SUM(monto),0) FROM transacciones WHERE tipo='ingreso' AND fecha>=? AND fecha<?",
                (start, end),
            ).fetchone()[0]
            exp = self.conn.execute(
                "SELECT COALESCE(SUM(monto),0) FROM transacciones WHERE tipo='gasto' AND fecha>=? AND fecha<?",
                (start, end),
            ).fetchone()[0]
            series.append((m, inc, exp))
            max_value = max(max_value, inc, exp)

        base_y = height - 24
        chart_w = width - (pad * 2)
        group_w = chart_w / len(series)
        bar_w = group_w * 0.32
        max_h = height - 70

        self.chart_canvas.create_line(pad, base_y, width - pad, base_y, fill="#D8DFEA")
        self.chart_canvas.create_text(pad, 14, text="Ingresos vs gastos (6 meses)", anchor="w", fill="#3A4A63", font=("Segoe UI", 11, "bold"))

        for idx, (m, inc, exp) in enumerate(series):
            center = pad + (idx + 0.5) * group_w
            h_inc = (inc / max_value) * max_h
            h_exp = (exp / max_value) * max_h
            self.chart_canvas.create_rectangle(center - bar_w - 2, base_y - h_inc, center - 2, base_y, fill="#1E9E68", outline="")
            self.chart_canvas.create_rectangle(center + 2, base_y - h_exp, center + bar_w + 2, base_y, fill="#D14A5B", outline="")
            self.chart_canvas.create_text(center, base_y + 12, text=MONTH_NAMES[m][:3], fill="#5A6980")

    def refresh_accounts(self) -> None:
        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)

        total = 0.0
        rows = self.conn.execute("SELECT id, nombre, banco, tipo, moneda, saldo FROM cuentas ORDER BY banco, nombre").fetchall()
        for row in rows:
            total += row["saldo"]
            self.accounts_tree.insert("", "end", values=(row["id"], row["nombre"], row["banco"], row["tipo"], row["moneda"], formato_eur(row["saldo"])))
        self.accounts_total_var.set(f"Saldo agregado: {formato_eur(total)}")

    def refresh_investments(self) -> None:
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)

        rows = self.conn.execute(
            "SELECT id, nombre, tipo, broker, monto_invertido, valor_actual, riesgo FROM inversiones ORDER BY nombre"
        ).fetchall()
        total_inv = 0.0
        total_current = 0.0
        by_type: dict[str, float] = {}

        for row in rows:
            pnl = row["valor_actual"] - row["monto_invertido"]
            total_inv += row["monto_invertido"]
            total_current += row["valor_actual"]
            by_type[row["tipo"]] = by_type.get(row["tipo"], 0.0) + row["valor_actual"]
            self.inv_tree.insert(
                "",
                "end",
                values=(
                    row["id"],
                    row["nombre"],
                    row["tipo"],
                    row["broker"] or "-",
                    formato_eur(row["monto_invertido"]),
                    formato_eur(row["valor_actual"]),
                    row["riesgo"],
                    formato_eur(pnl),
                ),
            )

        self.inv_summary_var.set(
            f"Invertido: {formato_eur(total_inv)} | Valor actual: {formato_eur(total_current)} | Rentabilidad: {formato_eur(total_current - total_inv)}"
        )
        self.draw_investments_chart(by_type)

    def draw_investments_chart(self, by_type: dict[str, float]) -> None:
        self.invest_chart.delete("all")
        w = max(600, self.invest_chart.winfo_width())
        total = sum(by_type.values())
        if total <= 0:
            self.invest_chart.create_text(w / 2, 70, text="Sin datos de inversiones", fill="#6D7B90")
            return

        colors = ["#2C7BE5", "#00A5A8", "#F29E4C", "#A66CFF", "#E05263", "#48BB78"]
        x = 16
        usable = w - 32
        for idx, (name, value) in enumerate(sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)):
            seg = usable * (value / total)
            color = colors[idx % len(colors)]
            self.invest_chart.create_rectangle(x, 28, x + seg, 68, fill=color, outline="")
            self.invest_chart.create_text(x + 4, 76, text=f"{name} ({value / total * 100:.0f}%)", anchor="nw", fill="#425268")
            x += seg

    def refresh_recurrences(self) -> None:
        for item in self.rec_tree.get_children():
            self.rec_tree.delete(item)

        rows = self.conn.execute(
            """
            SELECT r.*, c.nombre AS cuenta_nombre
            FROM recurrencias r
            LEFT JOIN cuentas c ON c.id = r.cuenta_id
            ORDER BY r.id DESC
            """
        ).fetchall()

        for row in rows:
            ultimo = "-"
            if row["ultimo_year"] and row["ultimo_month"]:
                ultimo = f"{row['ultimo_year']}-{row['ultimo_month']:02d}"
            self.rec_tree.insert(
                "",
                "end",
                values=(
                    row["id"],
                    row["tipo"],
                    row["nombre"],
                    row["categoria_tipo"],
                    formato_eur(row["monto"]),
                    row["cuenta_nombre"] or "-",
                    "Activa" if row["activa"] else "Pausada",
                    ultimo,
                ),
            )

    def refresh_all(self) -> None:
        self.refresh_period_options()
        self.refresh_accounts_combo()
        self.refresh_movimientos()
        self.refresh_accounts()
        self.refresh_investments()
        self.refresh_recurrences()
        self.refresh_dashboard()

    def add_movimiento(self) -> None:
        tipo = self.mov_tipo.get().strip()
        categoria = self.mov_categoria.get().strip()
        descripcion = self.mov_descripcion.get().strip()
        fecha_text = self.mov_fecha.get().strip()
        cuenta_id = self.account_map.get(self.mov_cuenta.get())

        try:
            monto = float(self.mov_monto.get().strip())
        except ValueError:
            messagebox.showerror("Monto inválido", "Introduce un monto numérico")
            return

        if monto < 0:
            messagebox.showerror("Monto inválido", "El monto no puede ser negativo")
            return
        if tipo not in {"ingreso", "gasto"}:
            messagebox.showerror("Tipo inválido", "Selecciona ingreso o gasto")
            return
        if not categoria or not descripcion:
            messagebox.showerror("Campos", "Categoría y descripción son obligatorias")
            return

        try:
            parse_iso_date(fecha_text)
        except ValueError:
            messagebox.showerror("Fecha", "Usa formato YYYY-MM-DD")
            return

        if tipo == "gasto" and monto > get_available_cash(self.conn):
            messagebox.showerror("Fondos insuficientes", "No hay dinero disponible para este gasto (sin crédito)")
            return

        self.conn.execute(
            """
            INSERT INTO transacciones (fecha, tipo, categoria, descripcion, monto, cuenta_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (fecha_text, tipo, categoria, descripcion, monto, cuenta_id),
        )

        if cuenta_id:
            delta = monto if tipo == "ingreso" else -monto
            self.conn.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (delta, cuenta_id))

        if self.mov_recurrente.get() and tipo == "gasto":
            d = parse_iso_date(fecha_text)
            self.conn.execute(
                """
                INSERT INTO recurrencias
                (tipo, nombre, categoria_tipo, descripcion, monto, cuenta_id, inicio_year, inicio_month, ultimo_year, ultimo_month, creado_en)
                VALUES ('gasto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    categoria,
                    categoria,
                    descripcion,
                    monto,
                    cuenta_id,
                    d.year,
                    d.month,
                    d.year,
                    d.month,
                    date.today().isoformat(),
                ),
            )

        self.conn.commit()
        self.mov_monto.set("")
        self.mov_categoria.set("")
        self.mov_descripcion.set("")
        self.mov_recurrente.set(False)
        self.refresh_all()

    def delete_movimiento(self) -> None:
        selected = self.mov_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona un movimiento")
            return

        mov_id = int(self.mov_tree.item(selected[0], "values")[0])
        row = self.conn.execute("SELECT tipo, monto, cuenta_id FROM transacciones WHERE id=?", (mov_id,)).fetchone()
        if row is None:
            return

        if not messagebox.askyesno("Confirmación", f"¿Eliminar movimiento {mov_id}?"):
            return

        if row["cuenta_id"]:
            revert = -row["monto"] if row["tipo"] == "ingreso" else row["monto"]
            self.conn.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (revert, row["cuenta_id"]))

        self.conn.execute("DELETE FROM transacciones WHERE id = ?", (mov_id,))
        self.conn.commit()
        self.refresh_all()

    def export_movimientos_csv(self) -> None:
        import csv

        year, month = self.selected_year_month()
        out = Path.cwd() / f"movimientos_{year}_{month:02d}.csv"
        rows = self.get_filtered_movimientos()

        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "fecha", "tipo", "categoria", "cuenta", "monto", "descripcion"])
            for row in rows:
                writer.writerow([row["id"], row["fecha"], row["tipo"], row["categoria"], row["cuenta_nombre"] or "", row["monto"], row["descripcion"]])

        messagebox.showinfo("Exportado", f"CSV guardado en:\n{out}")

    def add_account(self) -> None:
        nombre = self.acc_nombre.get().strip()
        banco = self.acc_banco.get().strip()
        tipo = self.acc_tipo.get().strip() or "Corriente"
        moneda = self.acc_moneda.get().strip() or "EUR"

        try:
            saldo = float(self.acc_saldo.get().strip())
        except ValueError:
            messagebox.showerror("Saldo inválido", "Saldo no numérico")
            return

        if not nombre or not banco:
            messagebox.showerror("Campos", "Nombre y banco son obligatorios")
            return

        self.conn.execute(
            "INSERT INTO cuentas (nombre,banco,tipo,moneda,saldo,notas,creado_en) VALUES (?,?,?,?,?,'',?)",
            (nombre, banco, tipo, moneda, saldo, date.today().isoformat()),
        )
        self.conn.commit()

        self.acc_nombre.set("")
        self.acc_banco.set("")
        self.acc_tipo.set("Corriente")
        self.acc_moneda.set("EUR")
        self.acc_saldo.set("0")
        self.refresh_all()

    def edit_account(self) -> None:
        selected = self.accounts_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una cuenta")
            return

        account_id = int(self.accounts_tree.item(selected[0], "values")[0])
        row = self.conn.execute("SELECT * FROM cuentas WHERE id=?", (account_id,)).fetchone()
        if row is None:
            return

        dlg = EditAccountDialog(self, row)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        self.conn.execute(
            "UPDATE cuentas SET nombre=?, banco=?, tipo=?, moneda=?, saldo=? WHERE id=?",
            (
                dlg.result["nombre"],
                dlg.result["banco"],
                dlg.result["tipo"],
                dlg.result["moneda"],
                dlg.result["saldo"],
                account_id,
            ),
        )
        self.conn.commit()
        self.refresh_all()

    def delete_account(self) -> None:
        selected = self.accounts_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una cuenta")
            return

        account_id = int(self.accounts_tree.item(selected[0], "values")[0])
        if not messagebox.askyesno("Confirmación", "Eliminar cuenta desvinculará movimientos y recurrencias. ¿Continuar?"):
            return

        self.conn.execute("UPDATE transacciones SET cuenta_id = NULL WHERE cuenta_id = ?", (account_id,))
        self.conn.execute("UPDATE recurrencias SET cuenta_id = NULL WHERE cuenta_id = ?", (account_id,))
        self.conn.execute("DELETE FROM cuentas WHERE id = ?", (account_id,))
        self.conn.commit()
        self.refresh_all()

    def add_investment(self) -> None:
        nombre = self.inv_nombre.get().strip()
        tipo = self.inv_tipo.get().strip() or "Acción"
        broker = self.inv_broker.get().strip()
        riesgo = self.inv_riesgo.get().strip() or "Medio"
        cuenta_id = self.account_map.get(self.inv_cuenta.get())

        try:
            invertido = float(self.inv_invertido.get().strip())
            actual = float(self.inv_actual.get().strip()) if self.inv_actual.get().strip() else invertido
        except ValueError:
            messagebox.showerror("Valores", "Invertido/actual deben ser numéricos")
            return

        if not nombre or invertido <= 0 or actual < 0:
            messagebox.showerror("Valores", "Revisa activo, invertido y valor actual")
            return

        fecha_text = date.today().isoformat()
        if invertido > get_available_cash(self.conn):
            messagebox.showerror("Fondos insuficientes", "No hay dinero disponible para esta inversión (sin crédito)")
            return

        upsert_investment(
            self.conn,
            nombre=nombre,
            tipo=tipo,
            broker=broker,
            invertido_delta=invertido,
            valor_actual_delta=actual,
            riesgo=riesgo,
            fecha_text=fecha_text,
        )

        if cuenta_id:
            self.conn.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (invertido, cuenta_id))

        if self.inv_recurrente.get():
            d = date.today()
            self.conn.execute(
                """
                INSERT INTO recurrencias
                (tipo, nombre, categoria_tipo, descripcion, monto, valor_actual, riesgo, broker, cuenta_id, inicio_year, inicio_month, ultimo_year, ultimo_month, creado_en)
                VALUES ('inversion', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nombre,
                    tipo,
                    f"Aporte recurrente {nombre}",
                    invertido,
                    actual,
                    riesgo,
                    broker,
                    cuenta_id,
                    d.year,
                    d.month,
                    d.year,
                    d.month,
                    d.isoformat(),
                ),
            )

        self.conn.commit()

        self.inv_nombre.set("")
        self.inv_broker.set("")
        self.inv_invertido.set("")
        self.inv_actual.set("")
        self.inv_riesgo.set("Medio")
        self.inv_recurrente.set(False)
        self.refresh_all()

    def edit_investment(self) -> None:
        selected = self.inv_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una posición")
            return

        inv_id = int(self.inv_tree.item(selected[0], "values")[0])
        row = self.conn.execute("SELECT * FROM inversiones WHERE id=?", (inv_id,)).fetchone()
        if row is None:
            return

        dlg = EditInvestmentDialog(self, row)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        clave = normalize_asset(dlg.result["nombre"])
        exists = self.conn.execute("SELECT id FROM inversiones WHERE clave=? AND id != ?", (clave, inv_id)).fetchone()
        if exists is not None:
            messagebox.showerror("Duplicado", "Ya existe una posición para ese activo. Usa nuevos aportes para acumular.")
            return

        self.conn.execute(
            """
            UPDATE inversiones
            SET nombre=?, clave=?, tipo=?, broker=?, monto_invertido=?, valor_actual=?, riesgo=?, fecha_actualizacion=?
            WHERE id=?
            """,
            (
                dlg.result["nombre"],
                clave,
                dlg.result["tipo"],
                dlg.result["broker"],
                dlg.result["monto_invertido"],
                dlg.result["valor_actual"],
                dlg.result["riesgo"],
                date.today().isoformat(),
                inv_id,
            ),
        )
        self.conn.commit()
        self.refresh_all()

    def quick_update_investment_value(self) -> None:
        selected = self.inv_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una posición")
            return

        inv_id = int(self.inv_tree.item(selected[0], "values")[0])
        row = self.conn.execute("SELECT nombre, valor_actual FROM inversiones WHERE id=?", (inv_id,)).fetchone()
        if row is None:
            return

        new_val = simpledialog.askstring("Actualizar cotización", f"Nuevo valor actual de {row['nombre']}:", initialvalue=str(row["valor_actual"]))
        if new_val is None:
            return
        try:
            value = float(new_val)
        except ValueError:
            messagebox.showerror("Valor inválido", "Introduce un número")
            return

        self.conn.execute("UPDATE inversiones SET valor_actual=?, fecha_actualizacion=? WHERE id=?", (max(value, 0), date.today().isoformat(), inv_id))
        self.conn.commit()
        self.refresh_all()

    def delete_investment(self) -> None:
        selected = self.inv_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una inversión")
            return

        inv_id = int(self.inv_tree.item(selected[0], "values")[0])
        if not messagebox.askyesno("Confirmación", "¿Eliminar posición de inversión?"):
            return

        self.conn.execute("DELETE FROM inversiones WHERE id = ?", (inv_id,))
        self.conn.commit()
        self.refresh_all()

    def toggle_recurrence(self) -> None:
        selected = self.rec_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una recurrencia")
            return

        rec_id = int(self.rec_tree.item(selected[0], "values")[0])
        row = self.conn.execute("SELECT activa FROM recurrencias WHERE id=?", (rec_id,)).fetchone()
        if row is None:
            return

        new_val = 0 if row["activa"] else 1
        self.conn.execute("UPDATE recurrencias SET activa=? WHERE id=?", (new_val, rec_id))
        self.conn.commit()
        self.refresh_all()

    def delete_recurrence(self) -> None:
        selected = self.rec_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una recurrencia")
            return

        rec_id = int(self.rec_tree.item(selected[0], "values")[0])
        if not messagebox.askyesno("Confirmación", "¿Eliminar regla recurrente?"):
            return

        self.conn.execute("DELETE FROM recurrencias WHERE id=?", (rec_id,))
        self.conn.commit()
        self.refresh_all()

    def apply_recurrences_now(self) -> None:
        result = apply_recurring_entries(self.conn)
        self.refresh_all()
        messagebox.showinfo("Recurrencias", f"Generadas: {result.created}\nSaltadas por fondos insuficientes: {result.skipped}")

    def on_close(self) -> None:
        self.conn.close()
        self.destroy()


def main() -> None:
    app = FinanzasApp()
    app.mainloop()


if __name__ == "__main__":
    main()
