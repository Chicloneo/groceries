# Proyecto 2

Aplicación Streamlit para probar la lista de la compra:

1. Escribe una petición en lenguaje natural.
2. El LLM interpreta los productos.
3. Python busca coincidencias reales en el catálogo de Mercadona.
4. Seleccionas las opciones y la aplicación calcula el total de la cesta.

## Configuración

Desde la carpeta `Proyecto-2/`:

```bash
uv sync
cp .env.example .env
```

También se incluye `requirements.txt` para instalaciones con `pip`:

```bash
python -m pip install -r requirements.txt
```

Edita `.env` y añade tu clave:

```dotenv
AI_PROVIDER=groq
GROQ_API_KEY=tu_clave
GROQ_MODEL=openai/gpt-oss-20b
LLM_MAX_ATTEMPTS=3
```

`AI_PROVIDER=groq` conecta Streamlit con Groq en tu equipo. Para ejecutar
pruebas sin llamadas externas, usa `AI_PROVIDER=mock`; GitHub Actions activa
el modo mock automáticamente.

## Ejecutar las pruebas desde Streamlit

```bash
uv run --env-file .env streamlit run frontend/app.py
```

Streamlit abre la aplicación en el navegador. Todas las pruebas funcionales se
hacen desde esta interfaz; no necesitas ejecutar comandos adicionales ni usar
una API externa.

### Flujo de prueba

1. Opcionalmente, elige una categoría y una subcategoría para acotar la búsqueda.
2. Escribe el producto en **Producto concreto** o pulsa un ejemplo de la barra lateral.
3. Pulsa **Buscar**.
4. Revisa las opciones que devuelve el catálogo.
5. Escribe el número de una opción en el chat.
6. También puedes indicar una cantidad o seleccionar varias opciones con lenguaje natural.
7. Comprueba la cesta y el total calculado en la barra lateral.
8. Pulsa **Nueva conversación** para reiniciar la cesta y comenzar otra prueba.

### Ejemplos recomendados

- `Leche semidesnatada Hacendado 1 litro`
- `Aceite de oliva virgen extra Hacendado 1 litro`
- `Huevos frescos 12 unidades`
- `Dos pizzas carbonara`

Si una búsqueda devuelve demasiadas opciones o no encuentra coincidencias,
Streamlit muestra una aclaración o un aviso. Cambia la petición o las
categorías seleccionadas para probar otro caso.

## Continuidad hacia el Proyecto 3

En el Proyecto 3 me gustaría ampliar el catálogo con productos de Carrefour,
además de conservar los productos de Mercadona.

La aplicación podría integrar las APIs de Google Maps y de la AEMET para:

- Sugerir rutas entre la ubicación actual del usuario y las tiendas disponibles.
- Tener en cuenta la distancia, el tráfico y las condiciones meteorológicas.
- Estimar el tiempo de compra en cada establecimiento.
- Comparar supermercados y ayudar a elegir la opción más barata y que reduzca el tiempo
  total del trayecto y la compra.

## Modelo clasificador

La aplicación carga el modelo ya entrenado desde
`models/clasificador_productos.joblib`. El modelo se conserva como artefacto
versionado y no se reentrena durante la ejecución de Streamlit ni en las pruebas.
Los metadatos, métricas, versiones y hash del artefacto están registrados en
`models/clasificador_productos.manifest.json`.

### Métricas de evaluación

El modelo se evaluó sobre `720` ejemplos reservados para prueba:

| Predicción | Accuracy | Macro-F1 |
| --- | ---: | ---: |
| Categoría | 92.36 % | 91.22 % |
| Subcategoría | 85.42 % | 81.13 % |

La clasificación de categoría alcanza una exactitud superior a la de
subcategoría, que contiene `134` clases y presenta un problema más fino.

Si en el futuro se quieren actualizar las categorías a partir de nuevos datos,
el reentrenamiento debe hacerse mediante un proceso externo al proyecto.

El proceso tendría que partir de un DataFrame con `nombre`, `categoria` y
`subcategoria`, entrenar los dos clasificadores por separado y reemplazar
después el artefacto `models/clasificador_productos.joblib`:

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import joblib

def create_pipeline():
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))),
        ("classifier", LogisticRegression(max_iter=1000)),
    ])

category_model = create_pipeline().fit(data["nombre"], data["categoria"])
subcategory_model = create_pipeline().fit(data["nombre"], data["subcategoria"])

joblib.dump({
    "format_version": 1,
    "category_model": category_model,
    "subcategory_model": subcategory_model,
}, "models/clasificador_productos.joblib")
```

## Código principal

```text
src/proyecto_2/
  ai_client.py       Selección del proveedor mock o Groq
  compras/
    contracts.py       Modelos Pydantic
    graph.py           Grafo LangGraph de búsqueda
    interpreter.py     Interpretación de la petición
    catalog_search.py  Búsqueda determinista en el CSV
    selection.py       Interpretación de selecciones y totales
  clasificador/
    classifier.py      Clasificador de categoría y subcategoría
```

## Tests

```bash
uv run pytest -q
```

Las decisiones de uso de IA, proveedor, modelo y partes aceptadas están
documentadas en [AI_USAGE.md](AI_USAGE.md).
