#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import date

from mis_finanzas.app.services.dashboard_service import get_dashboard_payload
from mis_finanzas.app.services.recommendation_engine import build_monthly_recommendations
from mis_finanzas.app.services.simulation_engine import simulate_purchase
from mis_finanzas.infrastructure.db import get_connection, migrate_schema_v2

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QStackedWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except Exception as exc:  # pragma: no cover
    print("PySide6 no está instalado. Instálalo con: pip install pyside6")
    raise SystemExit(1) from exc


LIGHT_QSS = """
QMainWindow { background: #F4F6FA; }
QWidget { color: #1E293B; font-size: 13px; }
#Header { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; }
#Card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 8px; }
#Sidebar { background: #0F172A; border-radius: 10px; }
QListWidget#Nav { background: transparent; border: none; color: #CBD5E1; }
QListWidget#Nav::item { padding: 10px; border-radius: 8px; }
QListWidget#Nav::item:selected { background: #1E293B; color: #F8FAFC; }
QPushButton { background: #2563EB; color: white; border: none; border-radius: 8px; padding: 8px 12px; }
QPushButton:hover { background: #1D4ED8; }
QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px; }
"""

DARK_QSS = """
QMainWindow { background: #0B1220; }
QWidget { color: #E2E8F0; font-size: 13px; }
#Header { background: #111827; border: 1px solid #334155; border-radius: 10px; }
#Card { background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 8px; }
#Sidebar { background: #020617; border-radius: 10px; }
QListWidget#Nav { background: transparent; border: none; color: #94A3B8; }
QListWidget#Nav::item { padding: 10px; border-radius: 8px; }
QListWidget#Nav::item:selected { background: #1E293B; color: #F8FAFC; }
QPushButton { background: #334155; color: #E2E8F0; border: 1px solid #475569; border-radius: 8px; padding: 8px 12px; }
QPushButton:hover { background: #3F4D63; }
QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #0F172A; border: 1px solid #334155; border-radius: 8px; padding: 6px; color: #E2E8F0; }
"""


def eur(v: float) -> str:
    return f"{v:,.2f} €".replace(",", "_").replace(".", ",").replace("_", ".")


class Card(QFrame):
    def __init__(self, title: str, value: str):
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        t = QLabel(title)
        t.setStyleSheet("font-size:12px;color:#94A3B8;")
        v = QLabel(value)
        v.setStyleSheet("font-size:26px;font-weight:700;")
        layout.addWidget(t)
        layout.addWidget(v)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.conn = get_connection()
        migrate_schema_v2(self.conn)
        self.theme = "dark"
        self.setWindowTitle("Mis Finanzas v2")
        self.resize(1380, 860)
        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        side_l = QVBoxLayout(sidebar)
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        for n in ["Dashboard", "Simulación", "Recomendaciones"]:
            QListWidgetItem(n, self.nav)
        self.nav.setCurrentRow(0)
        side_l.addWidget(QLabel("  Mis Finanzas v2"))
        side_l.addWidget(self.nav)

        content = QVBoxLayout()
        header = QFrame()
        header.setObjectName("Header")
        h = QHBoxLayout(header)
        self.year = QSpinBox(); self.year.setRange(2020, 2045); self.year.setValue(date.today().year)
        self.month = QComboBox(); self.month.addItems([f"{m:02d}" for m in range(1,13)]); self.month.setCurrentIndex(date.today().month-1)
        btn_refresh = QPushButton("Actualizar")
        btn_refresh.clicked.connect(self.refresh_dashboard)
        self.btn_theme = QPushButton("Cambiar tema")
        self.btn_theme.clicked.connect(self.toggle_theme)
        h.addWidget(QLabel("Año")); h.addWidget(self.year)
        h.addWidget(QLabel("Mes")); h.addWidget(self.month)
        h.addStretch(1)
        h.addWidget(btn_refresh)
        h.addWidget(self.btn_theme)

        self.stack = QStackedWidget()
        self.dashboard_page = QWidget(); self.sim_page = QWidget(); self.rec_page = QWidget()
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.sim_page)
        self.stack.addWidget(self.rec_page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        self._build_dashboard()
        self._build_simulation()
        self._build_recommendations()

        content.addWidget(header)
        content.addWidget(self.stack)

        main.addWidget(sidebar, 1)
        main.addLayout(content, 4)

        self.apply_theme()
        self.refresh_dashboard()
        self.refresh_recommendations()

    def _build_dashboard(self):
        self.dashboard_layout = QVBoxLayout(self.dashboard_page)
        self.cards_grid = QGridLayout()
        self.dashboard_layout.addLayout(self.cards_grid)

    def _build_simulation(self):
        lay = QVBoxLayout(self.sim_page)
        box = QFrame(); box.setObjectName("Card")
        f = QFormLayout(box)
        self.sim_name = QLineEdit("Compra")
        self.sim_amount = QLineEdit("100")
        self.sim_type = QComboBox(); self.sim_type.addItems(["necesidad","mejora","capricho","inversion_personal"])
        self.sim_urg = QComboBox(); self.sim_urg.addItems(["baja","media","alta"])
        btn = QPushButton("Simular")
        btn.clicked.connect(self.run_simulation)
        self.sim_out = QTextEdit(); self.sim_out.setReadOnly(True)
        f.addRow("Nombre", self.sim_name)
        f.addRow("Monto", self.sim_amount)
        f.addRow("Tipo", self.sim_type)
        f.addRow("Urgencia", self.sim_urg)
        f.addRow(btn)
        lay.addWidget(box)
        lay.addWidget(self.sim_out)

    def _build_recommendations(self):
        lay = QVBoxLayout(self.rec_page)
        self.rec_box = QTextEdit(); self.rec_box.setReadOnly(True); self.rec_box.setObjectName("Card")
        lay.addWidget(self.rec_box)

    def refresh_dashboard(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        payload = get_dashboard_payload(self.conn, year=self.year.value(), month=int(self.month.currentText()))
        items = [
            ("Balance", eur(payload["balance"])),
            ("Ingresos", eur(payload["ingresos"])),
            ("Gastos", eur(payload["gastos"])),
            ("Liquidez operativa", eur(payload["liquidez"])),
            ("Dinero protegido", eur(payload["protegido"])),
            ("Margen libre real", eur(payload["margen"])),
            ("Riesgo", payload["riesgo"].title()),
        ]
        for i, (t, v) in enumerate(items):
            self.cards_grid.addWidget(Card(t, v), i // 3, i % 3)

    def refresh_recommendations(self):
        recs = build_monthly_recommendations(self.conn, year=self.year.value(), month=int(self.month.currentText()))
        txt = []
        for r in recs:
            txt.append(f"• [{r['severidad'].upper()}] {r['titulo']}\n  {r['mensaje']}")
        self.rec_box.setText("\n\n".join(txt))

    def run_simulation(self):
        try:
            amount = float(self.sim_amount.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Simulación", "Monto inválido")
            return
        result = simulate_purchase(
            self.conn,
            nombre=self.sim_name.text().strip() or "Compra",
            monto=amount,
            tipo_necesidad=self.sim_type.currentText(),
            urgencia=self.sim_urg.currentText(),
        )
        lines = [
            f"Veredicto: {result.veredicto}",
            f"Impacto liquidez: {eur(result.impacto_liquidez)}",
            f"Margen restante: {eur(result.margen_restante)}",
            "",
            "Políticas:",
        ]
        for p in result.politicas:
            lines.append(f"- {p.nombre}: {p.status.value} · {p.mensaje}")
        lines.append("\nAlternativas:")
        for alt in result.alternativas:
            lines.append(f"- {alt}")
        self.sim_out.setText("\n".join(lines))

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(DARK_QSS if self.theme == "dark" else LIGHT_QSS)

    def closeEvent(self, event):
        self.conn.close()
        return super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
