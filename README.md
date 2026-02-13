# Mis Finanzas (local, visual y serio)

Aplicación de finanzas personales para uso local con dos interfaces:

- **GUI avanzada (Tkinter):** panel visual, movimientos por mes/año, cuentas, inversiones y recurrencias.
- **CLI:** para automatizar o cargar datos rápido por terminal.

Base de datos local: `~/.mis_finanzas.db` (SQLite).

## 1) Interfaz gráfica (recomendada)

```bash
python3 finanzas_gui.py
```

### Funcionalidades clave

- **Resumen visual** con:
  - Balance, ingresos y gastos del periodo
  - Tasa de ahorro
  - Saldo total de cuentas
  - Valor total de cartera
  - Gráfico de evolución de los últimos 6 meses
- **Filtro por mes y año** para consultar movimientos por periodos.
- **Control de liquidez (sin crédito):**
  - Gastos e inversiones quedan limitados por dinero disponible.
- **Movimientos:**
  - Alta de ingresos/gastos con cuenta asociada
  - Exportación CSV del mes
  - Gasto recurrente mensual opcional
- **Cuentas bancarias:**
  - Alta, edición y eliminación
  - Saldo agregado y actualización de datos
- **Inversiones:**
  - Alta de aportes
  - Acumulación automática por activo (ej. NVIDIA)
  - Edición de posición y actualización de valor actual (cotización)
  - Doble clic sobre una posición para actualizar rápido su valor actual
  - Rentabilidad agregada y composición por tipo
  - Inversión recurrente mensual opcional
- **Recurrencias:**
  - Listado de reglas
  - Activar/desactivar
  - Eliminar
  - Aplicación mensual automática y manual
- **Reset global de datos:**
  - Botón "Resetear base de datos" con doble confirmación (`RESET`) para limpiar valores de prueba.

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
