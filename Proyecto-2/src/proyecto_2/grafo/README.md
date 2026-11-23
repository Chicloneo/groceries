El grafo tiene tres nodos:

1. `parse_request()` interpreta la petición con Groq.
2. `catalog_search.search()` busca filas reales en el CSV.
3. Una plantilla Python genera la respuesta.

Groq no busca ni calcula precios. El clasificador y el cálculo de importes
siguen siendo Python.

```bash
uv run --env-file .env proyecto-2-grafo \
  "Necesito leche semidesnatada Hacendado 1 litro"
```