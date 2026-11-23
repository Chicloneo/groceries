# Proyecto 2 — Clasificación de productos

Ampliación de Proyecto 1: se reutiliza el catálogo Mercadona de
`../Proyecto-1/Data/productos_madrid_centro.csv` para entrenar un modelo que
sugiera la **categoría** y la **subcategoría** de un producto nuevo a partir de
su nombre. El catálogo no se copia a este directorio.

## Resultados

Con `random_state=42`, se reservan inicialmente el 20 % de los productos. Para
que todas las subcategorías estén representadas en entrenamiento y prueba, se
mueven algunos productos reales entre conjuntos cuando hace falta: en esta
partición quedan 2.851 productos para entrenar y 720 para probar (20,16 %).

| Tarea | Exactitud | F1 macro |
| --- | ---: | ---: |
| Categoría (24 clases) | 92,4 % | 91,2 % |
| Subcategoría (134 clases) | 85,4 % | 81,1 % |

El catálogo tiene 36.766 filas pero solo 3.571 nombres únicos: cada producto se
repite por código postal y se deduplica antes de entrenar. La partición reserva
nombres distintos, sin repetir un producto entre entrenamiento y prueba.

## Cómo funciona

1. **Limpieza.** Se eliminan filas vacías y se deja un producto por nombre. Si
   un nombre aparece con etiquetas distintas, se conserva la combinación
   (categoría, subcategoría) más frecuente.
2. **Representación.** TF-IDF de palabras (n-gramas 1-2) combinado con TF-IDF
   de caracteres (n-gramas 3-5). El segundo ayuda con marcas, palabras
   compuestas y pequeñas variaciones ortográficas.
3. **Modelo.** Una regresión logística multinomial por tarea, con
   `class_weight="balanced"` para compensar las clases con menos ejemplos.
4. **Predicción.** Se devuelve la categoría, la subcategoría, la probabilidad de
   cada una y las alternativas del top-3 de subcategoría.

## Entorno

Este directorio es un proyecto `uv` independiente. Desde `Proyecto-2/`:

```bash
uv sync                      # entorno de la librería y los tests
uv sync --group notebooks    # añade Jupyter, matplotlib y nbclient
uv run pytest -q
```

`pyproject.toml` declara las dependencias y `uv.lock` fija las versiones
resueltas; no hay `requirements.txt`.

## Probar el intérprete de listas con Groq

Desde `Proyecto-2/`, configura `GROQ_API_KEY` en tu `.env` y usa opcionalmente
`GROQ_MODEL` (por defecto `llama-3.3-70b-versatile`). Instala las dependencias
y prueba la extracción estructurada:

```bash
uv sync
uv run --env-file .env python -m proyecto_2.llm \
  "Necesito comprar 6 L de leche semidesnatada y carne picada"
```

La salida debe ser un JSON con dos productos. La leche tendrá cantidad solicitada
`6` y unidad `L`; la carne picada no tendrá cantidad solicitada. El CP será `null`
si no lo incluiste en el mensaje. En el uso real, la aplicación debe pedirlo antes
de llamar a la búsqueda si tampoco lo tiene guardado en la sesión. Python pasa el
`original_text` de cada producto por separado al clasificador guardado en
`models/clasificador_productos.joblib` y añade las predicciones de categoría y
subcategoría a ese producto. Por tanto, esa frase produce una predicción para
`6 L de leche semidesnatada` y otra para `carne picada`. El archivo del modelo
debe existir; este flujo no lo reentrena.

## Buscar opciones en el catálogo

`proyecto_2.catalog_search.search()` recibe el `ShoppingRequest` y busca cada
producto en `../Data/Clean/preprocesado_1_madrid_centro.csv`, restringiendo por
CP, categoría y subcategoría, y comparando el nombre con `pseudo_name` y
`search_terms`. Los atributos de `features` también deben aparecer en el nombre
o el formato. Las palabras relevantes de cada término se intersectan, así que
una diferencia como «carne picada de vacuno» frente a «Preparado de carne picada
vacuno» no depende de que coincida la frase completa. Si no encuentra filas con
los `features`, muestra todas las coincidencias de la descripción base con un
aviso de qué detalles no están disponibles. La cantidad solicitada queda en el
producto de entrada y no filtra formatos.

```python
from proyecto_2.catalog_search import search
from proyecto_2.llm import parse_request

peticion = parse_request(
    "Necesito comprar 6 L de leche semidesnatada y carne picada",
    cp="28012",
)
resultados = search(peticion)
for resultado in resultados:
    print(resultado["status"], resultado["clarification_question"])
    for opcion in resultado["options"]:
        print(opcion["option_id"], opcion["product"]["nombre"])
```

Cada producto ofrece todas las coincidencias si hay cinco o menos. Si hay más,
el resultado usa `status: "needs_clarification"`, incluye el número de
coincidencias y pregunta por más detalle sin escoger cinco arbitrariamente. Si
el fallback elimina detalles de `features` que no aparecen en el catálogo,
devuelve la lista base completa con un aviso. Las opciones incluyen `option_id`
y `product`, listas para `parse_selection()`. Si falta el CP, la función pide
ese dato antes de buscar.

## Flujo completo de selección

`proyecto_2.shopping_flow.start_shopping()` conecta la extracción y la búsqueda.
La persona puede elegir opciones de un producto con
`select_for_product(session, product_index, texto)`. Se puede llamar de nuevo
para acumular elecciones. Python multiplica las unidades comerciales elegidas
por `cantidad producto` del catálogo y compara el contenido acumulado con la
cantidad pedida cuando ambas unidades son compatibles (`g`/`kg` o `ml`/`L`).
También calcula el importe de cada opción elegida como `precio × sale_quantity`
y actualiza el total de la cesta en Python. No determina qué combinación debe
elegir la persona.

```python
from proyecto_2.shopping_flow import select_for_product, start_shopping

sesion = start_shopping(
    "Necesito comprar 8 L de leche semidesnatada",
    cp="28012",
)
opciones = sesion.searches[0]["options"]
print(opciones)

seleccion = select_for_product(sesion, 0, "un pack y dos briks")
print(seleccion["selected_quantity"], seleccion["remaining_quantity"])
print(seleccion["selected_total_price"], seleccion["basket_total_price"])
```

Si la cantidad seleccionada aún no alcanza el objetivo, otra llamada acumula
una elección adicional y devuelve la cantidad restante.

## Probar el flujo por CLI

Con la clave de Groq configurada en `.env`, desde `Proyecto-2/` puedes iniciar
el flujo interactivo:

```bash
uv run --env-file .env python -m proyecto_2.shopping_cli \
  "Necesito comprar 8 L de leche semidesnatada" --cp 28012
```

Si ejecutas el CLI sin una petición, imprime instrucciones para escribir cada
producto en una línea numerada, con su cantidad y detalles:

```bash
uv run --env-file .env python -m proyecto_2.shopping_cli
```

El CLI muestra las opciones, acepta selecciones en lenguaje natural y vuelve a
preguntar si la cantidad elegida aún no llega a la solicitada. Si no indicas
`--cp` y la petición no contiene uno, lo pregunta por consola. También está
disponible el comando instalado `uv run --env-file .env proyecto-2-compra`.
Al terminar imprime un ticket con el precio unitario de cada opción, el subtotal
de cada producto y el total de la cesta.

Si hay más de cinco coincidencias o ninguna, el CLI espera una precisión, vuelve
a interpretar ese detalle para el producto actual y repite la búsqueda. Escribe
`saltar` para omitir ese producto.

`parse_selection()` se prueba después de que Python haya encontrado y presentado
opciones. Para probar solo ese parser, puedes pasarle una fila real como opción;
la primera fila del CSV se usa aquí únicamente como dato de prueba, no como
resultado de búsqueda:

```bash
uv run --env-file .env python - <<'PY'
import pandas as pd

from proyecto_2.llm import CatalogProduct, ProductOption, parse_selection

catalogo = pd.read_csv(
    "../Data/Clean/preprocesado_1_madrid_centro.csv",
    sep=";",
    dtype={"cp": "string"},
    encoding="utf-8-sig",
)
fila = CatalogProduct.model_validate(catalogo.iloc[0].to_dict())
opcion = ProductOption(option_id="opcion-1", product=fila)

print(f"Opción 1: {fila.nombre} — {fila.precio} €")
seleccion = parse_selection("dame dos de la opción 1", [opcion])
print(seleccion.model_dump_json(indent=2))
PY
```

La selección esperada es el identificador `opcion-1` con `sale_quantity: 2`.
El parser de selecciones no busca ni suma precios. La orquestación valida los
identificadores contra las opciones ofrecidas y calcula los importes desde los
precios de esas filas del CSV.

## Script de consola

```bash
# Lista de productos de ejemplo (no están en el catálogo de entrenamiento)
uv run python scripts/classify_products.py

# Uno o varios productos nuevos
uv run python scripts/classify_products.py \
    --name "Leche de avena sin azúcar 1 L" \
    --name "Pintalabios mate rojo 24 h"

# Clasificar un CSV y guardar las predicciones
uv run python scripts/classify_products.py \
    --input-csv productos_nuevos.csv \
    --output-csv predicciones.csv

# Reentrenar con otros datos o hiperparámetros
uv run python scripts/classify_products.py --retrain --test-size 0.25 --C 10
```

La primera ejecución entrena el modelo (unos segundos) y lo guarda en
`models/clasificador_productos.joblib` (ignorado por Git). Las siguientes lo
cargan automáticamente; usa `--retrain` para volver a entrenarlo.

También está disponible como *entry point*:

```bash
uv run proyecto-2 --name "Cerveza sin alcohol 0,0 33 cl"
```

## Notebook

`Notebooks/clasificacion_productos.ipynb` explica el proceso paso a paso:
exploración de datos, deduplicación, split estratificado, TF-IDF, entrenamiento,
evaluación con matriz de confusión, interpretación de coeficientes,
clasificación de productos nuevos y limitaciones. Está ejecutado con las salidas
visibles para poder leerlo sin arrancar Jupyter. Sus salidas de evaluación aún
corresponden al split anterior (129 de 134 subcategorías en test); los resultados
actualizados están en la tabla de este README.

Para abrirlo:

```bash
uv run --group notebooks jupyter lab
```

## Estructura

```text
Proyecto-2/
  pyproject.toml
  uv.lock
  scripts/
    classify_products.py       # envoltorio de consola
  src/proyecto_2/
    classifier.py              # datos, pipelines, entrenamiento y predicción
    cli.py                     # argumentos e impresión de resultados
    mock_products.py           # productos nuevos de ejemplo
  Notebooks/
    clasificacion_productos.ipynb
  tests/
    test_classifier.py
  models/                      # generado, no se versiona
```

La lógica reutilizable está en `proyecto_2.classifier`:

```python
from proyecto_2.classifier import train_classifier

modelo = train_classifier()
print(modelo.predict(["Leche de avena sin azúcar 1 L"]))
modelo.save()  # models/clasificador_productos.joblib
```

## Limitaciones

- Solo se usa el nombre del producto; no el formato, el precio ni el código
  postal.
- Algunas subcategorías tienen muy pocos ejemplos (el mínimo es 2), por lo que
  su F1 es bajo.
- El catálogo no cubre todos los productos posibles. Un producto de un tipo
  ausente puede recibir una etiqueta con poca confianza; en producción conviene
  revisar los casos por debajo de un umbral.
- Categoría y subcategoría se entrenan por separado. En torno al 4 % de las
  predicciones de prueba no son coherentes entre sí; una mejora futura es un
  modelo jerárquico que restrinja las subcategorías a la categoría predicha.

## Tests

```bash
uv run pytest -q
```

Los tests usan un catálogo sintético, así que no dependen de que exista el CSV
del Proyecto 1.

## CI

El workflow compartido está en [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml)
y ejecuta las pruebas de Proyecto 1 y Proyecto 2 en cada `push` a `main` y en
cada `pull request`. Proyecto 1 conserva el umbral de cobertura del 60 %;
Proyecto 2 ejecuta su suite con `pytest -q`.
