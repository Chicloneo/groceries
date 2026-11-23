from decimal import Decimal

from proyecto_2.compras.contracts import (
    Producto,
    ProductSelection,
    ShoppingRequest,
    SelectionRequest,
    _ShoppingRequestPayload,
)
from proyecto_2.compras import graph
from proyecto_2 import groq
from proyecto_2.compras.graph import generar_respuesta
from proyecto_2.compras.selection import buscar_opcion_por_numero
from proyecto_2.compras.selection import (
    interpretar_seleccion,
    sumar_cesta,
)
from proyecto_2.compras import selection
from proyecto_2.clasificador.taxonomia import cargar_mapa_categoria_subcategoria


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
        lambda parsed, taxonomy_only=False: [
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


def test_search_response_is_rendered_as_numbered_list():
    respuesta = generar_respuesta([
        {
            "request_product": {"original_text": "arroz integral"},
            "status": "options",
            "notice": None,
            "options": [
                {
                    "product": {
                        "nombre": "Arroz integral",
                        "formato": "Paquete 1 kg",
                        "precio": 1.65,
                    }
                },
                {
                    "product": {
                        "nombre": "Arroz integral largo",
                        "formato": "Paquete 1 kg",
                        "precio": 1.95,
                    }
                },
            ],
        }
    ])

    assert "1. Arroz integral" in respuesta
    assert "2. Arroz integral largo" in respuesta


def test_frontend_selects_option_by_number():
    opciones = [
        {"product": {"nombre": "Primera"}},
        {"product": {"nombre": "Segunda"}},
    ]

    assert buscar_opcion_por_numero("2", opciones) == opciones[1]
    assert buscar_opcion_por_numero("texto", opciones) is None



def test_taxonomy_contains_all_processed_categories():
    mapa = cargar_mapa_categoria_subcategoria()

    assert len(mapa) == 24
    assert "Huevos, leche y mantequilla" in mapa
    assert "Leche y bebidas vegetales" in mapa[
        "Huevos, leche y mantequilla"
    ]


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


def test_groq_normalizes_singular_product_payload():
    data = {
        "cp": "28012",
        "product": "Leche semidesnatada Hacendado 1 litro",
    }

    normalized = groq._normalize_shopping_payload(data)

    assert normalized["cp"] == "28012"
    assert len(normalized["products"]) == 1
    assert (
        normalized["products"][0]["original_text"]
        == "Leche semidesnatada Hacendado 1 litro"
    )


def test_selection_uses_groq_and_python_sums_catalog_price(monkeypatch):
    opciones = [
        {
            "option_id": "producto-1-opcion-1",
            "product": {
                "nombre": "Pizza carbonara",
                "formato": "430 g",
                "precio": 2.90,
            },
        },
        {
            "option_id": "producto-1-opcion-2",
            "product": {
                "nombre": "Pizza carbonara familiar",
                "formato": "600 g",
                "precio": 3.40,
            },
        },
    ]

    monkeypatch.setattr(
        selection,
        "_structured_chat",
        lambda text, prompt, model: SelectionRequest(
            selections=[
                ProductSelection(
                    option_id="producto-1-opcion-2",
                    sale_quantity=2,
                )
            ],
            needs_clarification=False,
            clarification_question=None,
        ),
    )

    parsed = interpretar_seleccion(
        "dos de la opción 2",
        opciones,
    )

    cesta = {
        parsed.selections[0].option_id: parsed.selections[0].sale_quantity,
    }
    total = sumar_cesta(
        cesta,
        {opcion["option_id"]: opcion for opcion in opciones},
    )

    assert parsed.selections[0].sale_quantity == 2
    assert total.quantize(Decimal("0.01")) == Decimal("6.80")


def test_numeric_selection_is_resolved_in_python(monkeypatch):
    opciones = [
        {
            "option_id": "producto-1-opcion-1",
            "product": {
                "nombre": "Pizza carbonara familiar",
                "formato": "600 g",
                "precio": 3.40,
            },
        }
    ]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Las selecciones numéricas no usan el LLM")

    monkeypatch.setattr(selection, "_structured_chat", fail_if_called)
    parsed = interpretar_seleccion(
        "1",
        opciones,
    )

    assert parsed.selections[0].sale_quantity == 1


def test_basket_accumulates_two_selections():
    opciones = {
        "pizza-1": {
            "product": {"nombre": "Pizza familiar", "precio": 3.40}
        },
        "pizza-2": {
            "product": {"nombre": "Pizza barbacoa", "precio": 2.50}
        },
    }
    cesta = {"pizza-1": 1}
    cesta["pizza-2"] = cesta.get("pizza-2", 0) + 2

    total = sumar_cesta(cesta, opciones)

    assert cesta == {"pizza-1": 1, "pizza-2": 2}
    assert total.quantize(Decimal("0.01")) == Decimal("8.40")
