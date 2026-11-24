# Uso de inteligencia artificial

El proveedor de IA utilizado es **Groq**. El proyecto usa su API compatible
con la interfaz de OpenAI para interpretar peticiones de compra y elecciones
posteriores. Groq no calcula precios ni accede al catálogo: Python conserva
esos cálculos deterministas.

## Diseño del pipeline

El diseño del pipeline y la arquitectura del proyecto son exclusivamente míos:

```text
texto del usuario
  -> interpretación estructurada con IA
  -> clasificación sklearn
  -> búsqueda determinista en el catálogo
  -> selección de opciones
  -> cálculo Python de la cesta
```

La separación entre proveedor de IA, validación Pydantic, modelo sklearn,
búsqueda por pandas y frontend Streamlit forma parte de ese diseño propio.

## Llamada a Groq

La llamada real está encapsulada en
`src/proyecto_2/groq.py`. Primero se lee la clave y se crea el cliente compatible:

```python
api_key = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url=os.getenv(
        "GROQ_BASE_URL",
        "https://api.groq.com/openai/v1",
    ),
)
```

Después se envía la petición con un prompt de sistema, el texto del usuario,
el modelo configurado y una salida JSON:

```python
response = client.chat.completions.create(
    model=os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile",
    ),
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ],
    temperature=0,
    response_format={"type": "json_object"},
    timeout=20,
)
```

El contenido recibido se valida contra el modelo Pydantic solicitado:

```python
content = response.choices[0].message.content
if not content:
    raise LLMError("Groq devolvió una respuesta vacía.")

data = json.loads(content)
return response_model.model_validate(data)
```

## Ejecución del cliente

El proveedor se selecciona en `src/proyecto_2/ai_client.py`:

```python
provider = os.getenv("AI_PROVIDER", "groq").strip().casefold()

if provider == "groq":
    return groq_structured_chat(text, system_prompt, response_model)
```

Por defecto local se usa Groq. En tests y GitHub Actions se usa el proveedor
mock mediante `AI_PROVIDER=mock`, de forma que CI no necesite una clave real.

## Tareas realizadas por Groq

1. Convertir una frase de compra en una estructura con productos, cantidades,
   unidades, características y código postal.
2. Interpretar qué opciones mostradas eligió el usuario y cuántas unidades
   comerciales quiere.

Groq no decide qué fila del catálogo coincide, no calcula totales y no elige
presentaciones basándose en precios. Esas operaciones las realiza el código
Python.

## Modelo utilizado

El modelo configurado por defecto es
`openai/gpt-oss-20b`. Puede modificarse mediante `GROQ_MODEL` sin cambiar
el código. Aunque Groq es el proveedor de ejecución, el contrato de salida
permanece basado en Pydantic.

## Configuración y secretos

Las variables se configuran en `.env`:

```dotenv
AI_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
LLM_MAX_ATTEMPTS=3
```

Las claves reales no se incluyen en el repositorio. `.env.example` muestra el
contrato de configuración sin secretos.