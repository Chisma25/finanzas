# Mis Finanzas (local, visual y serio)

Aplicación de finanzas personales para uso local con dos interfaces:

- **GUI avanzada (Tkinter):** panel visual, movimientos por mes/año, cuentas e inversiones.
- **CLI:** para automatizar o cargar datos rápido por terminal.

Base de datos local: `~/.mis_finanzas.db` (SQLite).

## 1) Interfaz gráfica (recomendada)

```bash
python3 finanzas_gui.py
```

### Funcionalidades de la GUI

- **Resumen visual** con métricas clave:
  - Balance mensual
  - Ingresos y gastos del periodo
  - Tasa de ahorro
  - Saldo total en cuentas
  - Capital invertido
- **Filtro por mes y año** para revisar movimientos por periodos.
- **Gráfico de evolución** de ingresos/gastos de los últimos 6 meses.
- **Gestión de movimientos**:
  - Alta con tipo, cuenta, categoría, fecha y descripción.
  - Tabla filtrada por periodo.
  - Eliminación individual.
  - Exportación CSV mensual.
- **Gestión de cuentas bancarias**:
  - Alta de cuentas (nombre, banco, tipo, moneda, saldo).
  - Tabla con saldo total agregado.
- **Gestión de inversiones**:
  - Alta de activos (tipo, broker, capital invertido, valor actual, riesgo).
  - Resumen de rentabilidad total.
  - Gráfico de composición de cartera por tipo.

## 2) CLI (opcional)

```bash
python3 finanzas.py agregar --tipo ingreso --monto 1500 --categoria salario --descripcion "Nómina"
python3 finanzas.py agregar --tipo gasto --monto 52.3 --categoria supermercado --descripcion "Compra semanal"
python3 finanzas.py listar
python3 finanzas.py resumen
```

Comandos:

- `agregar --tipo {ingreso,gasto} --monto N --categoria TXT --descripcion TXT [--fecha YYYY-MM-DD]`
- `listar [--limite N]`
- `eliminar ID`
- `resumen`
- `reset --si`

## Requisitos

- Python 3.10+
- Tkinter (normalmente incluido con Python en Windows/macOS; en Linux puede requerir paquete adicional)
