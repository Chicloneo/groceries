from proyecto_2.compras.contracts import (
    Producto,
    ShoppingRequest,
    _ShoppingRequestPayload,
)
from proyecto_2.compras import graph
from proyecto_2 import groq


def make_request():
    return ShoppingRequest(
        request="Leche semidesnatada Hacendado 1 litro",
        cp="28012",
        products=[
            Producto(
                original_text="Leche semidesnatada Hacendado 1 litro",
                pseudo_name="leche semidesnatada",
                search_terms=["leche semidesnatada"],
                requested_quantity=1,
                requested_unit="L",
                features=["Hacendado", "semidesnatada"],
                categoria=None,
                subcategoria=None,
            )
        ],
    )


def test_simple_graph_template(monkeypatch):
    request = make_request()
    monkeypatch.setattr(graph, "parse_request", lambda text, cp=None: request)
    monkeypatch.setattr(
        graph,
        "search",
        lambda parsed: [
            {
                "request_product": request.products[0].model_dump(mode="json"),
                "status": "options",
                "notice": None,
                "options": [
                    {
                        "option_id": "producto-1-opcion-1",
                        "product": {
                            "nombre": "Leche semidesnatada",
                            "formato": "Brik 1 L",
                            "precio": 1.05,
                        },
                    }
                ],
            }
        ],
    )

    result = graph.app.invoke(
        {
            "peticion_usuario": request.request,
            "codigo_postal": "28012",
        }
    )

    assert "Leche semidesnatada" in result["respuesta_final"]
    assert "1.05 €" in result["respuesta_final"]


def test_groq_client_returns_pydantic_payload(monkeypatch):
    payload = {
        "cp": "28012",
        "products": [],
    }

    class FakeCompletions:
        def create(self, **kwargs):
            return type("Response", (), {
                "choices": [
                    type("Choice", (), {
                        "message": type("Message", (), {
                            "content": __import__("json").dumps(payload),
                        })()
                    })()
                ]
            })()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {
                "completions": FakeCompletions()
            })()

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(groq, "OpenAI", FakeClient)

    result = groq._structured_chat(
        "Nada",
        "Devuelve JSON",
        _ShoppingRequestPayload,
    )

    assert result.cp == "28012"
    assert result.products == []
