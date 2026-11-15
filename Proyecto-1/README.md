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

## Preprocesado de los datos raw

El preprocesado del catálogo de Madrid Centro se realiza en dos etapas:
`src/proyecto_1/preprocess.py` prepara las columnas generales y después llama a
`src/proyecto_1/preprocess_formato.py`, que añade los datos calculados a partir
del formato. La entrada es `Data/Raw/catalogo_madrid_centro.csv`; se generan
`Data/Clean/preprocesado_0_madrid_centro.csv` y
`Data/Clean/preprocesado_1_madrid_centro.csv`, respectivamente. Este proceso es
distinto de la carga del CLI descrita arriba.

### Primera etapa: columnas generales

El CSV raw contiene estas columnas:

| Columna raw | Significado |
| --- | --- |
| `cp` | Código postal de la tienda. |
| `categoria` | Categoría del producto. |
| `subcategoria` | Subcategoría dentro de la categoría. |
| `nombre` | Nombre del producto. |
| `formato_y_precio_por_kilo` | Texto combinado con el formato y el precio de referencia, separados por `\|`. |
| `precio_unidad` | Precio total de compra de esa presentación. |

`preprocess.py` conserva `cp`, `categoria`, `subcategoria` y `nombre`. De las
otras dos columnas deriva:

- `precio`: precio total, sin el símbolo `€` y con punto decimal.
- `formato`: parte anterior a `|`, con los espacios exteriores eliminados.
- `precio_por_`: valor numérico de la parte posterior a `|`, sin `€` y con
  punto decimal.
- `unidades`: unidad que aparece después de la última `/` del precio de
  referencia. Los códigos `dz` y `dc` se escriben como `docena`, y `lv` como
  `lavado`.

Las columnas de origen `precio_unidad` y `formato_y_precio_por_kilo` se
sustituyen por esos campos derivados. Por ejemplo:

```text
Raw:
formato_y_precio_por_kilo = "Garrafa 5 L | 3,35 €/L"
precio_unidad = "16,75 €"
```
```
Preprocesado general:
formato = "Garrafa 5 L"
precio_por_ = "3.35"
unidades = "L"
precio = "16.75"
```

### Segunda etapa: campos derivados del formato

`preprocess_formato.py` conserva las columnas recibidas y añade:

| Columna añadida | Significado |
| --- | --- |
| `es_pack` | `True` si el primer recuento explícito de unidades en `formato` es mayor que uno; en otro caso, `False`. |
| `numero_unidades_pack` | Ese primer recuento, solo cuando `es_pack` es `True`; si no, queda vacío. |
| `numero_subunidades_pack_por_unidad` | Se establece en `1` para los packs; si no, queda vacío. |
| `cantidad producto` | Cantidad física extraída del formato, ajustada al pack cuando corresponde. Puede quedar vacía si no se encuentra una cantidad física. |
| `medida_producto` | Unidad de `cantidad producto`: la masa se convierte a `g`, el volumen a `ml` y la longitud se mantiene en `m`. |

Criterios para interpretar `formato`:

- Se toma el primer recuento explícito reconocido (por ejemplo, `3` en
  `3 briks x 400 g`) como número de unidades del pack. Un recuento superior a
  uno indica un pack.
- Si aparece una cantidad escurrida, se usa antes que la cantidad neta; en un
  pack se multiplica por el número de unidades.
- En expresiones como `3 briks x 400 g`, la cantidad que sigue a `x` es por
  unidad, por lo que se multiplica por tres.
- Una cantidad entre paréntesis se interpreta como cantidad por unidad en un
  pack, salvo que el precio total y el precio por medida indiquen que ya es la
  cantidad total. Para esta comprobación se admite una diferencia de hasta el
  12 %, por el redondeo del precio.
- Se elimina `aprox.` para extraer la cantidad y se trata como si fuera exacta.
- Si no hay cantidad física reconocible, `cantidad producto` y
  `medida_producto` quedan vacías; el formato textual original se conserva.

Ejemplos reales:

```text
formato = "3 briks x 400 g"
es_pack = True
numero_unidades_pack = 3
cantidad producto = 1200
medida_producto = "g"
```

```text
formato = "3 botes x 350 g (150 g escurrido)"
es_pack = True
numero_unidades_pack = 3
cantidad producto = 450
medida_producto = "g"
```

```text
formato = "Paquete 4 sobres (0,4 g)"
precio = 1.90
precio_por_ = 475.00
unidades = "100 g"
es_pack = True
numero_unidades_pack = 4
cantidad producto = 0.4
medida_producto = "g"
```

En el último caso, `0,4 g` ya corresponde al total: el precio da
`1,90 / 475 × 100 = 0,4 g`. Por eso no se multiplica por los cuatro sobres.

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

Workflow compartido por los dos proyectos:
[`../.github/workflows/ci.yml`](../.github/workflows/ci.yml). CI ejecuta los
tests de Proyecto 1 y Proyecto 2; este job mantiene la cobertura mínima del 60 %.

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
