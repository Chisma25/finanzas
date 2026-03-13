# Migraciones v2

Migraciones implementadas de forma idempotente en `mis_finanzas/infrastructure/db.py`.

## Nuevas tablas
- `schema_migrations`
- `buckets`
- `goals`
- `policies`
- `monthly_plans`
- `planned_purchases`
- `scenarios`
- `scenario_changes`
- `recommendations`

## Nuevas columnas en `cuentas`
- `is_liquid` (default 1)
- `is_credit` (default 0)
- `include_in_available_cash` (default 1)
- `is_primary_operating_account` (default 0)

## Compatibilidad
- No borra datos existentes.
- Mantiene tablas legacy (`transacciones`, `cuentas`, `inversiones`, `recurrencias`, `app_config`).
- Diseñado para ejecutarse varias veces sin duplicar ni romper schema.
