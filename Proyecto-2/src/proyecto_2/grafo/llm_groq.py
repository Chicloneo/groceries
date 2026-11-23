import json
import os

from openai import OpenAI

from proyecto_2.contracts import Producto, ShoppingRequest


SYSTEM_PROMPT = """\
Convierte la petición de compra en JSON. La búsqueda posterior la hará Python
sobre el catálogo real; tú no inventes nombres oficiales, formatos, precios ni
disponibilidad.

Devuelve exactamente este formato:
{
  "cp": null,
  "products": [
    {
      "original_text": "texto correspondiente a este producto",
      "pseudo_name": "nombre breve de búsqueda",
      "search_terms": ["variante segura de búsqueda"],
      "requested_quantity": null,
      "requested_unit": null,
      "features": [],
      "categoria": null,
      "subcategoria": null
    }
  ]
}

requested_unit puede ser g, kg, ml, L, ud, docena o pack.
requested_quantity es la cantidad pedida por el usuario, no el tamaño del envase.
features contiene solo atributos expresamente dichos por el usuario.
No mezcles distintos productos en un elemento.
"""


def extraer_peticion(texto: str, cp: str | None = None) -> ShoppingRequest:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta GROQ_API_KEY. Configúrala en el entorno o en .env."
        )

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": texto},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Groq devolvió una respuesta vacía.")

    payload = json.loads(content)
    postal_code = cp if cp is not None else payload.get("cp")

    products = [
        Producto.model_validate(product)
        for product in payload.get("products", [])
    ]
    return ShoppingRequest(
        request=texto,
        cp=postal_code,
        products=products,
    )
