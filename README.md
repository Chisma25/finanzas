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

- **Diseño renovado (más moderno):**
  - Tipografía y espaciados más limpios
  - Botones primarios/secundarios/peligro bien diferenciados
  - Pestañas y tablas con estilo visual más actual
  - Toggle de tema claro/oscuro para adaptar la interfaz a tu preferencia
  - La preferencia de tema queda guardada al cerrar y se restaura al abrir
  - En Windows compatible, la barra de título nativa también se oscurece al activar modo oscuro y se reaplica al arrancar para respetar la preferencia guardada

- **Resumen visual** con:
  - Balance, ingresos y gastos del periodo
  - Tasa de ahorro
  - Saldo total de cuentas
  - Valor total de cartera
  - Gráfico de evolución de los últimos 6 meses
- **Filtro por mes y año** para consultar movimientos por periodos.
  - Selector de años disponible desde el año actual hasta 2040.
- **Control de liquidez (sin crédito):**
  - Gastos e inversiones quedan limitados por dinero disponible.
  - Si tienes cuentas registradas, el disponible se calcula desde el saldo total de cuentas (incluyendo saldos iniciales manuales).
- **Movimientos:**
  - Alta de ingresos/gastos con cuenta asociada
  - Exportación CSV del mes
  - Ingreso o gasto recurrente mensual opcional (ej. salario)
- **Cuentas bancarias:**
  - Alta, edición y eliminación
  - Saldo agregado y actualización de datos
- **Inversiones:**
  - Alta de aportes
  - El valor actual inicial se asume igual al aporte invertido
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
  - El botón "Aplicar recurrencias ahora" aplica reglas hasta el mes/año actualmente seleccionado
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

## Empaquetado profesional (app ejecutable)

Si quieres compartir la app como una aplicación "normal" sin ejecutar `.py`:

1. Instala PyInstaller:

```bash
pip install pyinstaller
```

2. Genera ejecutable:

- **Windows:** ejecutar `packaging/build_windows.bat`
  - Resultado: `dist/MisFinanzas.exe` (un único `.exe`)
- **Linux/macOS:** ejecutar `packaging/build_unix.sh`
  - Resultado: `dist/MisFinanzas` (binario único)

3. Puedes compartir directamente ese binario generado.


### Si el `.bat` se cierra solo

- Ejecuta `build_windows.bat` haciendo doble clic o desde `cmd`.
- El script ahora hace `pause` al final y también cuando hay error para que puedas leer el mensaje.
- Si falla al inicio, instala PyInstaller con:

```bash
pip install pyinstaller
```

## V2 (base incremental orientada a decisión)

Se añadió una base v2 manteniendo compatibilidad con la app actual:

- Migraciones no destructivas para nuevas tablas de planificación/escenarios/recomendaciones.
- Motor de políticas personales (reglas activas con evaluación estructurada).
- Cálculo centralizado de métricas v2 (liquidez operativa, dinero protegido, compromisos, margen libre real y riesgo).
- Motor de simulación de compra sin mutar el ledger real.
- Recomendador mensual explicable basado en reglas.

### Nuevos comandos CLI v2

- `python3 finanzas.py buckets listar`
- `python3 finanzas.py buckets crear --nombre Emergencia --objetivo 5000 --reservado 600 --protegido`
- `python3 finanzas.py simular-compra --nombre Portatil --monto 1200 --tipo-necesidad mejora --urgencia media`
- `python3 finanzas.py recomendaciones-mes --anio 2026 --mes 7`

### Documentación técnica adicional

- `ARCHITECTURE.md`
- `MIGRATIONS.md`
- `CHANGELOG.md`


## UI v2: decisión de capa visual

Tras evaluar límites prácticos de Tkinter/ttk para acabado “comercializable”, la v2 introduce una **capa visual moderna en PySide6** reutilizando el core ya refactorizado (`mis_finanzas/*`).

- GUI clásica legacy: `python3 finanzas_gui.py`
- GUI v2 (Qt): `python3 finanzas_gui_qt.py`

> Nota: la GUI Qt usa los mismos servicios y la misma base SQLite local; no reescribe el core ni rompe compatibilidad de datos.
