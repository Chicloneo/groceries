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

`uv.lock` fija las versiones resueltas; `requirements.txt` es la exportación
para herramientas de instalación basadas en pip.

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
visibles para poder leerlo sin arrancar Jupyter.

Para abrirlo:

```bash
uv run --group notebooks jupyter lab
```

## Estructura

```text
Proyecto-2/
  pyproject.toml
  uv.lock
  requirements.txt
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
