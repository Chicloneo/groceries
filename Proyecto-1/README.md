# Proyecto 1 — Catálogo de productos de Mercadona

Pipeline de carga, validación y análisis para el catálogo de productos.

## Ejecutar

Desde `Proyecto-1/`:

```bash
uv sync --inexact --group dev
uv run --no-sync python -m proyecto_1.cli --input Data/aux.csv
```

El programa imprime un informe JSON con el número de filas válidas e inválidas
y las métricas. Si hay filas inválidas, también incluye sus números de fila y
los errores de validación.

## Reglas y métricas

- Se exige un código postal de cinco dígitos, campos descriptivos no vacíos y
  un precio de producto numérico y mayor que cero.
- Los conteos de productos usan nombres únicos dentro de cada categoría o
  subcategoría; distintos formatos con el mismo nombre cuentan como un
  producto.
- El precio medio se calcula sobre `precio_unidad`, determinando las categorías más baratas y más caras
- El ranking de envases excluye `Revisar nombre`; los empates se muestran
  completos.

## Estructura

```text
src/proyecto_1/
  contracts.py
  loader.py
  validator.py
  metrics.py
  cli.py
tests/
  test_loader.py
  test_validator.py
  test_metrics.py
  test_cli.py
  test_integration.py
```

Los demás CSV existentes se mantienen en sus ubicaciones actuales. `Data/aux.csv`
es la entrada de referencia para Cabo de Palos, Murcia (CP `30370`).

## Tests

```bash
uv run --no-sync pytest -q
uv run --no-sync pytest -q -m "not integration"
uv run --no-sync pytest -q -m integration
```

## CI

Workflow: [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml)

![Estado de CI](https://github.com/Chicloneo/groceries/actions/workflows/ci.yml/badge.svg)

[Ver ejecuciones de GitHub Actions](https://github.com/Chicloneo/groceries/actions/workflows/ci.yml).

```bash
pytest -q \
  --cov=proyecto_1.cli \
  --cov=proyecto_1.contracts \
  --cov=proyecto_1.loader \
  --cov=proyecto_1.metrics \
  --cov=proyecto_1.validator \
  --cov-report=term-missing \
  --cov-fail-under=60
```
