#!/usr/bin/env python3
"""Interfaz gráfica local para finanzas personales con paneles avanzados."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

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


def formato_eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "_").replace(".", ",").replace("_", ".")


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
            tipo TEXT NOT NULL,
            broker TEXT,
            monto_invertido REAL NOT NULL CHECK(monto_invertido >= 0),
            valor_actual REAL NOT NULL CHECK(valor_actual >= 0),
            riesgo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            notas TEXT
        )
        """
    )

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(transacciones)").fetchall()}
    if "cuenta_id" not in columns:
        conn.execute("ALTER TABLE transacciones ADD COLUMN cuenta_id INTEGER")

    conn.commit()


class FinanzasApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Mis Finanzas Personales")
        self.geometry("1280x780")
        self.minsize(1180, 700)
        self.configure(bg="#F2F5FA")

        self.conn = get_connection()
        init_db(self.conn)

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
        style.configure("MetricTitle.TLabel", background="#FFFFFF", foreground="#607089", font=("Segoe UI", 9))
        style.configure("MetricValue.TLabel", background="#FFFFFF", foreground="#1D2A3A", font=("Segoe UI", 18, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Panel financiero personal", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="Seguimiento mensual de movimientos, cuentas bancarias e inversiones.",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        filters = ttk.Frame(root, style="Root.TFrame")
        filters.pack(fill="x", pady=(0, 10))

        ttk.Label(filters, text="Año", style="SubHeader.TLabel").pack(side="left")
        self.year_var = tk.StringVar(value=str(date.today().year))
        self.year_combo = ttk.Combobox(filters, textvariable=self.year_var, state="readonly", width=8)
        self.year_combo.pack(side="left", padx=(6, 12))

        ttk.Label(filters, text="Mes", style="SubHeader.TLabel").pack(side="left")
        self.month_var = tk.StringVar(value=f"{date.today().month:02d}")
        self.month_combo = ttk.Combobox(
            filters,
            textvariable=self.month_var,
            state="readonly",
            width=13,
            values=[f"{m:02d} - {MONTH_NAMES[m]}" for m in range(1, 13)],
        )
        self.month_combo.pack(side="left", padx=(6, 12))

        ttk.Button(filters, text="Aplicar periodo", command=self.refresh_all, style="Accent.TButton").pack(side="left")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.dashboard_tab = ttk.Frame(self.notebook, padding=10)
        self.mov_tab = ttk.Frame(self.notebook, padding=10)
        self.accounts_tab = ttk.Frame(self.notebook, padding=10)
        self.investments_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.dashboard_tab, text="Resumen")
        self.notebook.add(self.mov_tab, text="Movimientos")
        self.notebook.add(self.accounts_tab, text="Cuentas")
        self.notebook.add(self.investments_tab, text="Inversiones")

        self._build_dashboard_tab()
        self._build_movimientos_tab()
        self._build_accounts_tab()
        self._build_investments_tab()

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
            ("Balance del periodo", self.metric_balance),
            ("Ingresos del periodo", self.metric_income),
            ("Gastos del periodo", self.metric_expenses),
            ("Tasa de ahorro", self.metric_saving_rate),
            ("Saldo total cuentas", self.metric_accounts),
            ("Capital invertido", self.metric_invested),
        ]

        for idx, (title, var) in enumerate(card_data):
            frame = ttk.LabelFrame(cards, text=f" {title} ", style="Card.TLabelframe")
            frame.grid(row=0, column=idx, padx=4, sticky="nsew")
            ttk.Label(frame, textvariable=var, style="MetricValue.TLabel").pack(padx=10, pady=12)
            cards.columnconfigure(idx, weight=1)

        graph_frame = ttk.LabelFrame(self.dashboard_tab, text=" Evolución últimos 6 meses ", style="Card.TLabelframe")
        graph_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.chart_canvas = tk.Canvas(graph_frame, bg="#FFFFFF", height=280, highlightthickness=0)
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

        ttk.Label(top, text="Tipo").grid(row=0, column=0, sticky="w")
        ttk.Combobox(top, textvariable=self.mov_tipo, values=["ingreso", "gasto"], state="readonly", width=12).grid(
            row=1, column=0, sticky="w", padx=(0, 10)
        )

        ttk.Label(top, text="Monto").grid(row=0, column=1, sticky="w")
        ttk.Entry(top, textvariable=self.mov_monto, width=12).grid(row=1, column=1, sticky="w", padx=(0, 10))

        ttk.Label(top, text="Categoría").grid(row=0, column=2, sticky="w")
        ttk.Entry(top, textvariable=self.mov_categoria, width=18).grid(row=1, column=2, sticky="w", padx=(0, 10))

        ttk.Label(top, text="Cuenta").grid(row=0, column=3, sticky="w")
        self.mov_account_combo = ttk.Combobox(top, textvariable=self.mov_cuenta, state="readonly", width=20)
        self.mov_account_combo.grid(row=1, column=3, sticky="w", padx=(0, 10))

        ttk.Label(top, text="Fecha (YYYY-MM-DD)").grid(row=0, column=4, sticky="w")
        ttk.Entry(top, textvariable=self.mov_fecha, width=14).grid(row=1, column=4, sticky="w", padx=(0, 10))

        ttk.Label(top, text="Descripción").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(top, textvariable=self.mov_descripcion, width=72).grid(row=3, column=0, columnspan=4, sticky="we")

        ttk.Button(top, text="Guardar movimiento", command=self.add_movimiento, style="Accent.TButton").grid(
            row=3, column=4, sticky="e"
        )

        table_frame = ttk.LabelFrame(self.mov_tab, text=" Movimientos del periodo ", style="Card.TLabelframe", padding=8)
        table_frame.pack(fill="both", expand=True, pady=(12, 0))

        columns = ("id", "fecha", "tipo", "categoria", "cuenta", "monto", "descripcion")
        self.mov_tree = ttk.Treeview(table_frame, columns=columns, show="headings")

        headers = {
            "id": "ID",
            "fecha": "Fecha",
            "tipo": "Tipo",
            "categoria": "Categoría",
            "cuenta": "Cuenta",
            "monto": "Monto",
            "descripcion": "Descripción",
        }
        widths = {"id": 50, "fecha": 100, "tipo": 80, "categoria": 120, "cuenta": 160, "monto": 110, "descripcion": 340}

        for col in columns:
            anchor = "e" if col == "monto" else "w"
            self.mov_tree.heading(col, text=headers[col])
            self.mov_tree.column(col, width=widths[col], anchor=anchor)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.mov_tree.yview)
        self.mov_tree.configure(yscrollcommand=scroll.set)
        self.mov_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        actions = ttk.Frame(self.mov_tab)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Eliminar seleccionada", command=self.delete_movimiento).pack(side="left")
        ttk.Button(actions, text="Exportar CSV del periodo", command=self.export_movimientos_csv).pack(side="left", padx=(8, 0))

    def _build_accounts_tab(self) -> None:
        form = ttk.LabelFrame(self.accounts_tab, text=" Nueva cuenta bancaria ", style="Card.TLabelframe", padding=10)
        form.pack(fill="x")

        self.acc_nombre = tk.StringVar()
        self.acc_banco = tk.StringVar()
        self.acc_tipo = tk.StringVar(value="Corriente")
        self.acc_moneda = tk.StringVar(value="EUR")
        self.acc_saldo = tk.StringVar(value="0")

        ttk.Label(form, text="Nombre").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.acc_nombre, width=20).grid(row=1, column=0, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Banco").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.acc_banco, width=20).grid(row=1, column=1, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Tipo").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.acc_tipo,
            values=["Corriente", "Ahorro", "Nómina", "Broker", "Otra"],
            state="readonly",
            width=14,
        ).grid(row=1, column=2, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Moneda").grid(row=0, column=3, sticky="w")
        ttk.Combobox(form, textvariable=self.acc_moneda, values=["EUR", "USD", "GBP"], state="readonly", width=8).grid(
            row=1, column=3, padx=(0, 10), sticky="w"
        )

        ttk.Label(form, text="Saldo actual").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.acc_saldo, width=12).grid(row=1, column=4, padx=(0, 10), sticky="w")

        ttk.Button(form, text="Guardar cuenta", command=self.add_account, style="Accent.TButton").grid(row=1, column=5, sticky="e")

        self.accounts_total_var = tk.StringVar(value="Saldo agregado: 0,00 €")
        ttk.Label(self.accounts_tab, textvariable=self.accounts_total_var, style="Header.TLabel").pack(anchor="w", pady=(10, 6))

        table_frame = ttk.LabelFrame(self.accounts_tab, text=" Cuentas registradas ", style="Card.TLabelframe", padding=8)
        table_frame.pack(fill="both", expand=True)

        cols = ("id", "nombre", "banco", "tipo", "moneda", "saldo")
        self.accounts_tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col, title, width in [
            ("id", "ID", 50),
            ("nombre", "Nombre", 180),
            ("banco", "Banco", 180),
            ("tipo", "Tipo", 120),
            ("moneda", "Moneda", 90),
            ("saldo", "Saldo", 130),
        ]:
            self.accounts_tree.heading(col, text=title)
            anchor = "e" if col == "saldo" else "w"
            self.accounts_tree.column(col, width=width, anchor=anchor)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.accounts_tree.yview)
        self.accounts_tree.configure(yscrollcommand=scroll.set)
        self.accounts_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Button(self.accounts_tab, text="Eliminar cuenta seleccionada", command=self.delete_account).pack(anchor="w", pady=(8, 0))

    def _build_investments_tab(self) -> None:
        form = ttk.LabelFrame(self.investments_tab, text=" Nueva inversión ", style="Card.TLabelframe", padding=10)
        form.pack(fill="x")

        self.inv_nombre = tk.StringVar()
        self.inv_tipo = tk.StringVar(value="ETF")
        self.inv_broker = tk.StringVar()
        self.inv_invertido = tk.StringVar()
        self.inv_actual = tk.StringVar()
        self.inv_riesgo = tk.StringVar(value="Medio")
        self.inv_fecha = tk.StringVar(value=date.today().isoformat())

        ttk.Label(form, text="Activo").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.inv_nombre, width=20).grid(row=1, column=0, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Tipo").grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.inv_tipo,
            values=["ETF", "Acción", "Fondo", "Cripto", "Renta fija", "Otro"],
            state="readonly",
            width=14,
        ).grid(row=1, column=1, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Broker/Plataforma").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.inv_broker, width=20).grid(row=1, column=2, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Capital invertido").grid(row=0, column=3, sticky="w")
        ttk.Entry(form, textvariable=self.inv_invertido, width=14).grid(row=1, column=3, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Valor actual").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.inv_actual, width=14).grid(row=1, column=4, padx=(0, 10), sticky="w")

        ttk.Label(form, text="Riesgo").grid(row=0, column=5, sticky="w")
        ttk.Combobox(form, textvariable=self.inv_riesgo, values=["Bajo", "Medio", "Alto"], state="readonly", width=10).grid(
            row=1, column=5, padx=(0, 10), sticky="w"
        )

        ttk.Label(form, text="Fecha").grid(row=0, column=6, sticky="w")
        ttk.Entry(form, textvariable=self.inv_fecha, width=12).grid(row=1, column=6, padx=(0, 10), sticky="w")

        ttk.Button(form, text="Guardar inversión", command=self.add_investment, style="Accent.TButton").grid(row=1, column=7, sticky="e")

        self.inv_summary_var = tk.StringVar(value="Invertido: 0,00 € | Valor actual: 0,00 € | Rentabilidad: 0,00 €")
        ttk.Label(self.investments_tab, textvariable=self.inv_summary_var, style="Header.TLabel").pack(anchor="w", pady=(10, 6))

        chart_box = ttk.LabelFrame(self.investments_tab, text=" Distribución por tipo ", style="Card.TLabelframe", padding=8)
        chart_box.pack(fill="x")
        self.invest_chart = tk.Canvas(chart_box, bg="#FFFFFF", height=150, highlightthickness=0)
        self.invest_chart.pack(fill="x")

        table_frame = ttk.LabelFrame(self.investments_tab, text=" Cartera ", style="Card.TLabelframe", padding=8)
        table_frame.pack(fill="both", expand=True, pady=(10, 0))

        cols = ("id", "nombre", "tipo", "broker", "invertido", "actual", "riesgo", "rent")
        self.inv_tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col, title, width in [
            ("id", "ID", 50),
            ("nombre", "Activo", 140),
            ("tipo", "Tipo", 90),
            ("broker", "Broker", 120),
            ("invertido", "Invertido", 110),
            ("actual", "Actual", 110),
            ("riesgo", "Riesgo", 90),
            ("rent", "P/L", 110),
        ]:
            self.inv_tree.heading(col, text=title)
            anchor = "e" if col in {"invertido", "actual", "rent"} else "w"
            self.inv_tree.column(col, width=width, anchor=anchor)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.inv_tree.yview)
        self.inv_tree.configure(yscrollcommand=scroll.set)
        self.inv_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Button(self.investments_tab, text="Eliminar inversión seleccionada", command=self.delete_investment).pack(
            anchor="w", pady=(8, 0)
        )

    def selected_year_month(self) -> tuple[int, int]:
        try:
            year = int(self.year_var.get().strip())
        except ValueError:
            year = date.today().year
        month_text = self.month_var.get().strip()
        month = int(month_text[:2]) if month_text and month_text[:2].isdigit() else date.today().month
        return year, month

    def refresh_period_options(self) -> None:
        years = {date.today().year}
        rows = self.conn.execute("SELECT fecha FROM transacciones").fetchall()
        for row in rows:
            try:
                years.add(datetime.strptime(row["fecha"], "%Y-%m-%d").year)
            except ValueError:
                continue

        values = [str(y) for y in sorted(years)]
        self.year_combo["values"] = values
        if self.year_var.get() not in values:
            self.year_var.set(str(max(years)))

    def get_filtered_movimientos(self) -> list[sqlite3.Row]:
        year, month = self.selected_year_month()
        start = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month + 1:02d}-01"

        query = """
            SELECT t.id, t.fecha, t.tipo, t.categoria, t.descripcion, t.monto, c.nombre AS cuenta_nombre
            FROM transacciones t
            LEFT JOIN cuentas c ON c.id = t.cuenta_id
            WHERE t.fecha >= ? AND t.fecha < ?
            ORDER BY t.fecha DESC, t.id DESC
        """
        return self.conn.execute(query, (start, end)).fetchall()

    def refresh_movimientos(self) -> None:
        for item in self.mov_tree.get_children():
            self.mov_tree.delete(item)

        rows = self.get_filtered_movimientos()
        for row in rows:
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

    def refresh_accounts_combo(self) -> None:
        rows = self.conn.execute("SELECT id, nombre, banco FROM cuentas ORDER BY nombre").fetchall()
        self.account_map = {"Sin cuenta": None}
        options = ["Sin cuenta"]
        for row in rows:
            label = f"{row['nombre']} ({row['banco']})"
            self.account_map[label] = row["id"]
            options.append(label)

        self.mov_account_combo["values"] = options
        if self.mov_cuenta.get() not in options:
            self.mov_cuenta.set("Sin cuenta")

    def refresh_dashboard(self) -> None:
        rows = self.get_filtered_movimientos()
        ingresos = sum(r["monto"] for r in rows if r["tipo"] == "ingreso")
        gastos = sum(r["monto"] for r in rows if r["tipo"] == "gasto")
        balance = ingresos - gastos
        saving_rate = (balance / ingresos * 100) if ingresos else 0.0

        cuentas_total = self.conn.execute("SELECT COALESCE(SUM(saldo), 0) FROM cuentas").fetchone()[0]
        invested_total = self.conn.execute("SELECT COALESCE(SUM(valor_actual), 0) FROM inversiones").fetchone()[0]

        self.metric_balance.set(formato_eur(balance))
        self.metric_income.set(formato_eur(ingresos))
        self.metric_expenses.set(formato_eur(gastos))
        self.metric_saving_rate.set(f"{saving_rate:.1f} %")
        self.metric_accounts.set(formato_eur(cuentas_total))
        self.metric_invested.set(formato_eur(invested_total))

        self.draw_monthly_chart()

    def draw_monthly_chart(self) -> None:
        self.chart_canvas.delete("all")
        width = max(640, self.chart_canvas.winfo_width())
        height = max(220, self.chart_canvas.winfo_height())
        pad = 40

        today = date.today()
        months = []
        year, month = today.year, today.month
        for _ in range(6):
            months.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        months.reverse()

        series = []
        max_value = 1.0
        for y, m in months:
            start = f"{y:04d}-{m:02d}-01"
            if m == 12:
                end = f"{y + 1:04d}-01-01"
            else:
                end = f"{y:04d}-{m + 1:02d}-01"

            income = self.conn.execute(
                "SELECT COALESCE(SUM(monto),0) FROM transacciones WHERE tipo='ingreso' AND fecha>=? AND fecha<?",
                (start, end),
            ).fetchone()[0]
            expenses = self.conn.execute(
                "SELECT COALESCE(SUM(monto),0) FROM transacciones WHERE tipo='gasto' AND fecha>=? AND fecha<?",
                (start, end),
            ).fetchone()[0]
            series.append((y, m, income, expenses))
            max_value = max(max_value, income, expenses)

        chart_w = width - (pad * 2)
        bar_group = chart_w / max(1, len(series))
        bar_w = bar_group * 0.34
        max_h = height - 70

        self.chart_canvas.create_text(pad, 16, text="Ingresos y gastos últimos 6 meses", anchor="w", fill="#3A4A63", font=("Segoe UI", 11, "bold"))
        self.chart_canvas.create_rectangle(pad + 4, 28, pad + 16, 40, fill="#1E9E68", outline="")
        self.chart_canvas.create_text(pad + 22, 34, text="Ingresos", anchor="w", fill="#46566F")
        self.chart_canvas.create_rectangle(pad + 100, 28, pad + 112, 40, fill="#D14A5B", outline="")
        self.chart_canvas.create_text(pad + 118, 34, text="Gastos", anchor="w", fill="#46566F")

        base_y = height - 24
        self.chart_canvas.create_line(pad, base_y, width - pad, base_y, fill="#D8DFEA")

        for idx, (_, m, income, expenses) in enumerate(series):
            center = pad + (idx + 0.5) * bar_group
            income_h = (income / max_value) * max_h
            expenses_h = (expenses / max_value) * max_h

            self.chart_canvas.create_rectangle(
                center - bar_w - 2,
                base_y - income_h,
                center - 2,
                base_y,
                fill="#1E9E68",
                outline="",
            )
            self.chart_canvas.create_rectangle(
                center + 2,
                base_y - expenses_h,
                center + bar_w + 2,
                base_y,
                fill="#D14A5B",
                outline="",
            )
            self.chart_canvas.create_text(center, base_y + 12, text=MONTH_NAMES[m][:3], fill="#5A6980")

    def refresh_accounts(self) -> None:
        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)

        rows = self.conn.execute("SELECT id, nombre, banco, tipo, moneda, saldo FROM cuentas ORDER BY banco, nombre").fetchall()
        total = 0.0
        for row in rows:
            total += row["saldo"]
            self.accounts_tree.insert(
                "",
                "end",
                values=(row["id"], row["nombre"], row["banco"], row["tipo"], row["moneda"], formato_eur(row["saldo"])),
            )

        self.accounts_total_var.set(f"Saldo agregado: {formato_eur(total)}")

    def refresh_investments(self) -> None:
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)

        rows = self.conn.execute(
            "SELECT id, nombre, tipo, broker, monto_invertido, valor_actual, riesgo FROM inversiones ORDER BY fecha DESC, id DESC"
        ).fetchall()
        invested = 0.0
        current = 0.0
        by_type: dict[str, float] = {}

        for row in rows:
            pnl = row["valor_actual"] - row["monto_invertido"]
            invested += row["monto_invertido"]
            current += row["valor_actual"]
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

        pnl_total = current - invested
        self.inv_summary_var.set(
            f"Invertido: {formato_eur(invested)} | Valor actual: {formato_eur(current)} | Rentabilidad: {formato_eur(pnl_total)}"
        )
        self.draw_investments_chart(by_type)

    def draw_investments_chart(self, by_type: dict[str, float]) -> None:
        self.invest_chart.delete("all")
        w = max(640, self.invest_chart.winfo_width())
        h = max(130, self.invest_chart.winfo_height())
        pad = 16
        total = sum(by_type.values())

        if total <= 0:
            self.invest_chart.create_text(w / 2, h / 2, text="Sin datos de inversiones", fill="#6D7B90")
            return

        colors = ["#2C7BE5", "#00A5A8", "#F29E4C", "#A66CFF", "#E05263", "#48BB78"]
        x = pad
        usable = w - (pad * 2)
        for idx, (name, value) in enumerate(sorted(by_type.items(), key=lambda x: x[1], reverse=True)):
            segment = usable * (value / total)
            color = colors[idx % len(colors)]
            self.invest_chart.create_rectangle(x, 28, x + segment, 70, fill=color, outline="")
            self.invest_chart.create_text(x + 4, 80, text=f"{name} ({value / total * 100:.0f}%)", anchor="nw", fill="#425268")
            x += segment

        self.invest_chart.create_text(pad, 14, text="Composición de cartera por tipo", anchor="w", fill="#3A4A63", font=("Segoe UI", 10, "bold"))

    def refresh_all(self) -> None:
        self.refresh_period_options()
        self.refresh_accounts_combo()
        self.refresh_movimientos()
        self.refresh_accounts()
        self.refresh_investments()
        self.refresh_dashboard()

    def add_movimiento(self) -> None:
        tipo = self.mov_tipo.get().strip()
        categoria = self.mov_categoria.get().strip()
        descripcion = self.mov_descripcion.get().strip()
        fecha_text = self.mov_fecha.get().strip()
        cuenta_id = self.account_map.get(self.mov_cuenta.get()) if hasattr(self, "account_map") else None

        try:
            monto = float(self.mov_monto.get().strip())
        except ValueError:
            messagebox.showerror("Monto inválido", "Introduce un monto numérico.")
            return

        if monto < 0:
            messagebox.showerror("Monto inválido", "El monto no puede ser negativo.")
            return
        if tipo not in {"ingreso", "gasto"}:
            messagebox.showerror("Tipo inválido", "Selecciona ingreso o gasto.")
            return
        if not categoria or not descripcion:
            messagebox.showerror("Campos incompletos", "Categoría y descripción son obligatorias.")
            return

        try:
            datetime.strptime(fecha_text, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha inválida", "Usa formato YYYY-MM-DD.")
            return

        self.conn.execute(
            """
            INSERT INTO transacciones (fecha, tipo, categoria, descripcion, monto, cuenta_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (fecha_text, tipo, categoria, descripcion, monto, cuenta_id),
        )
        self.conn.commit()

        self.mov_monto.set("")
        self.mov_categoria.set("")
        self.mov_descripcion.set("")
        self.mov_fecha.set(date.today().isoformat())

        self.refresh_all()

    def delete_movimiento(self) -> None:
        selected = self.mov_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona un movimiento.")
            return

        item = self.mov_tree.item(selected[0], "values")
        mov_id = int(item[0])
        if not messagebox.askyesno("Confirmación", f"¿Eliminar movimiento {mov_id}?"):
            return

        self.conn.execute("DELETE FROM transacciones WHERE id = ?", (mov_id,))
        self.conn.commit()
        self.refresh_all()

    def export_movimientos_csv(self) -> None:
        import csv

        year, month = self.selected_year_month()
        filename = Path.cwd() / f"movimientos_{year}_{month:02d}.csv"
        rows = self.get_filtered_movimientos()

        with filename.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "fecha", "tipo", "categoria", "cuenta", "monto", "descripcion"])
            for row in rows:
                writer.writerow(
                    [
                        row["id"],
                        row["fecha"],
                        row["tipo"],
                        row["categoria"],
                        row["cuenta_nombre"] or "",
                        row["monto"],
                        row["descripcion"],
                    ]
                )

        messagebox.showinfo("Exportación completada", f"CSV guardado en:\n{filename}")

    def add_account(self) -> None:
        nombre = self.acc_nombre.get().strip()
        banco = self.acc_banco.get().strip()
        tipo = self.acc_tipo.get().strip()
        moneda = self.acc_moneda.get().strip()

        try:
            saldo = float(self.acc_saldo.get().strip())
        except ValueError:
            messagebox.showerror("Saldo inválido", "Introduce un saldo numérico.")
            return

        if not nombre or not banco:
            messagebox.showerror("Campos incompletos", "Nombre y banco son obligatorios.")
            return

        self.conn.execute(
            """
            INSERT INTO cuentas (nombre, banco, tipo, moneda, saldo, notas, creado_en)
            VALUES (?, ?, ?, ?, ?, '', ?)
            """,
            (nombre, banco, tipo, moneda, saldo, date.today().isoformat()),
        )
        self.conn.commit()

        self.acc_nombre.set("")
        self.acc_banco.set("")
        self.acc_tipo.set("Corriente")
        self.acc_moneda.set("EUR")
        self.acc_saldo.set("0")
        self.refresh_all()

    def delete_account(self) -> None:
        selected = self.accounts_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una cuenta.")
            return

        account_id = int(self.accounts_tree.item(selected[0], "values")[0])
        if not messagebox.askyesno(
            "Confirmación",
            "Eliminar cuenta desvinculará movimientos asociados (sin borrarlos). ¿Continuar?",
        ):
            return

        self.conn.execute("UPDATE transacciones SET cuenta_id = NULL WHERE cuenta_id = ?", (account_id,))
        self.conn.execute("DELETE FROM cuentas WHERE id = ?", (account_id,))
        self.conn.commit()
        self.refresh_all()

    def add_investment(self) -> None:
        nombre = self.inv_nombre.get().strip()
        tipo = self.inv_tipo.get().strip()
        broker = self.inv_broker.get().strip()
        riesgo = self.inv_riesgo.get().strip()
        fecha_text = self.inv_fecha.get().strip()

        try:
            invertido = float(self.inv_invertido.get().strip())
            actual = float(self.inv_actual.get().strip())
        except ValueError:
            messagebox.showerror("Valor inválido", "Capital invertido y valor actual deben ser numéricos.")
            return

        if not nombre:
            messagebox.showerror("Campo obligatorio", "El nombre del activo es obligatorio.")
            return

        try:
            datetime.strptime(fecha_text, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha inválida", "Usa formato YYYY-MM-DD.")
            return

        self.conn.execute(
            """
            INSERT INTO inversiones (nombre, tipo, broker, monto_invertido, valor_actual, riesgo, fecha, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, '')
            """,
            (nombre, tipo, broker, invertido, actual, riesgo, fecha_text),
        )
        self.conn.commit()

        self.inv_nombre.set("")
        self.inv_broker.set("")
        self.inv_invertido.set("")
        self.inv_actual.set("")
        self.inv_riesgo.set("Medio")
        self.inv_fecha.set(date.today().isoformat())
        self.refresh_all()

    def delete_investment(self) -> None:
        selected = self.inv_tree.selection()
        if not selected:
            messagebox.showinfo("Sin selección", "Selecciona una inversión.")
            return

        inv_id = int(self.inv_tree.item(selected[0], "values")[0])
        if not messagebox.askyesno("Confirmación", f"¿Eliminar inversión {inv_id}?"):
            return

        self.conn.execute("DELETE FROM inversiones WHERE id = ?", (inv_id,))
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
