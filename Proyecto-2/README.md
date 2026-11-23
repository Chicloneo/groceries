# Proyecto 2

Proyecto Python para convertir una petición de compra en lenguaje natural,
buscar productos reales en el catálogo de Mercadona y calcular el importe.

Groq interpreta el texto. Python clasifica, busca, valida y suma precios.

## Configuración

Desde `Proyecto-2/`:

```bash
uv sync
cp .env.example .env
```

Edita `.env` y añade tu clave:

```dotenv
GROQ_API_KEY=tu_clave
GROQ_MODEL=llama-3.3-70b-versatile
LLM_MAX_ATTEMPTS=3
```

## Ejecutar el grafo

```bash
uv run --env-file .env proyecto-2-grafo \
  "Leche semidesnatada Hacendado 1 litro"
```

El grafo tiene tres pasos:

1. Extraer productos con `request_parser.py`.
2. Buscar coincidencias reales con `catalog_search.py`.
3. Presentar las opciones con una plantilla en `grafo/graph.py`.

## Ejecutar el flujo interactivo completo

```bash
uv run --env-file .env proyecto-2-compra \
  "Necesito 8 L de leche semidesnatada" --cp 28012
```

Este CLI conserva productos seleccionados, permite acumular cantidades y muestra
el ticket final.

## Clasificador

```bash
uv run proyecto-2 --name "Leche de avena sin azúcar 1 L"
```

El modelo se guarda automáticamente en `models/clasificador_productos.joblib`.
Para entrenarlo de nuevo:

```bash
uv run proyecto-2 --retrain --test-size 0.2 --C 10
```

## Código principal

```text
src/proyecto_2/
  contracts.py       Modelos Pydantic
  llm_client.py      Conexión con Groq
  prompts.py         Instrucciones para el modelo
  request_parser.py  Interpretación de la petición
  catalog_search.py  Búsqueda determinista en el CSV
  selection_parser.py Interpretación de opciones elegidas
  shopping_flow.py   Sesión, cantidades y totales
  shopping_cli.py    CLI interactivo
  grafo/             Grafo LangGraph de tres nodos
  classifier.py      Clasificador de categoría y subcategoría
  cli.py             CLI del clasificador
```

## Tests

```bash
uv run pytest -q
```
