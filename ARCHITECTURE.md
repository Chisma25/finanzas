# Arquitectura v2 (incremental sobre base existente)

## Diagnóstico inicial
La base actual tenía buena cobertura funcional pero mucha lógica acoplada en `finanzas_gui.py`.

## Estrategia aplicada
- Mantener Tkinter + SQLite + CLI.
- Extraer lógica de cálculo/evaluación a servicios reutilizables.
- Añadir migraciones v2 no destructivas.

## Capas
- `mis_finanzas/infrastructure/db.py`: conexión y migraciones de schema v2.
- `mis_finanzas/domain/*`: tipos/enums/modelos de salida.
- `mis_finanzas/app/services/*`:
  - `metrics.py`: snapshot financiero y margen libre real.
  - `policy_engine.py`: evaluación de políticas activas.
  - `simulation_engine.py`: simulación de compra (sin mutar ledger real).
  - `recommendation_engine.py`: recomendaciones mensuales explicables.

## Integración
- GUI y CLI siguen operativas.
- CLI ahora incluye comandos v2 base (`buckets`, `simular-compra`, `recomendaciones-mes`).
- GUI inicializa también migraciones v2 para compatibilidad de datos.

## Principio clave
La simulación se realiza en memoria (sobre snapshot derivado), sin escritura en transacciones reales.


## Capa de presentación v2
- Se mantiene Tkinter como fallback funcional.
- Se añade `finanzas_gui_qt.py` (PySide6) como shell moderna principal.
- Ambas UIs comparten core de servicios y SQLite.
