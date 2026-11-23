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

Edita `.env` y añade tu clave:

```dotenv
GROQ_API_KEY=tu_clave
GROQ_MODEL=llama-3.3-70b-versatile
LLM_MAX_ATTEMPTS=3
```

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

## Clasificador

```bash
uv run proyecto-2 clasificar --name "Leche de avena sin azúcar 1 L"
```

El modelo se guarda automáticamente en `models/clasificador_productos.joblib`.

## Código principal

```text
src/proyecto_2/
  compras/
    contracts.py       Modelos Pydantic
    graph.py           Grafo LangGraph de búsqueda
    interpreter.py     Interpretación de la petición
    catalog_search.py  Búsqueda determinista en el CSV
    selection.py       Interpretación de selecciones y totales
  clasificador/
    classifier.py      Clasificador de categoría y subcategoría
    cli.py             CLI del clasificador
```

## Tests

```bash
uv run pytest -q
```
