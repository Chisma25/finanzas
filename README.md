# Mis Finanzas (local, sin Excel)

Ahora tienes **dos formas** de usar la app en local:

1. **Interfaz gráfica (recomendada):** para trastear cómodamente.
2. **CLI:** por si prefieres terminal.

Los datos se guardan en SQLite en `~/.mis_finanzas.db`.

## Interfaz gráfica

```bash
python3 finanzas_gui.py
```

Desde la ventana puedes:
- Añadir transacciones (`ingreso` / `gasto`) con categoría, fecha y descripción.
- Ver resumen de ingresos, gastos y balance.
- Eliminar una transacción seleccionada.
- Borrar todos los movimientos.

## CLI (opcional)

```bash
python3 finanzas.py agregar --tipo ingreso --monto 1500 --categoria salario --descripcion "Nómina"
python3 finanzas.py agregar --tipo gasto --monto 52.3 --categoria supermercado --descripcion "Compra semanal"
python3 finanzas.py listar
python3 finanzas.py resumen
```

Comandos disponibles:
- `agregar --tipo {ingreso,gasto} --monto N --categoria TXT --descripcion TXT [--fecha YYYY-MM-DD]`
- `listar [--limite N]`
- `eliminar ID`
- `resumen`
- `reset --si`

## Requisitos

- Python 3.10+
- Tkinter (suele venir con Python en la mayoría de sistemas)
