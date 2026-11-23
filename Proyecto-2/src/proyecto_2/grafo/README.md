```mermaid
flowchart TD
    A([START]) --> B["PASO 1: entender la petición"]
    B --> C["PASO 2: buscar productos"]
    C --> D["PASO 3: responder al usuario"]
    D --> E([END])
```

Paso A: interpretar con LLM

Paso B: buscar con Python

Paso C: responder con plantilla

Groq se integra sustituyendo al cliente LLM dentro de `request_parser.py`.
El grafo reutiliza `parse_request()` y `catalog_search.search()` del pipeline
existente.

La implementación actual usa Groq solo en el primer nodo para estructurar la
petición. Python busca en el CSV y genera la respuesta con una plantilla.

```bash
uv run --env-file .env proyecto-2-grafo \
  "Necesito leche semidesnatada Hacendado 1 litro"
```