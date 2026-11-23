from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

from proyecto_2.catalog_search import search
from proyecto_2.contracts import ShoppingRequest
from proyecto_2.request_parser import parse_request


class Estado(TypedDict, total=False):
    peticion_usuario: str
    codigo_postal: str | None
    peticion_estructurada: ShoppingRequest
    productos_encontrados: list[dict[str, Any]]
    respuesta_final: str


def entender_peticion(estado: Estado) -> dict:
    peticion = parse_request(
        estado["peticion_usuario"],
        cp=estado.get("codigo_postal"),
    )
    return {
        "peticion_estructurada": peticion,
        "codigo_postal": peticion.cp,
    }


def buscar_productos(estado: Estado) -> dict:
    encontrados = search(estado["peticion_estructurada"])
    return {"productos_encontrados": encontrados}


def generar_respuesta(productos: list[dict[str, Any]]) -> str:
    if not productos:
        return "No encontré productos concretos en tu petición."

    lines: list[str] = []
    for resultado in productos:
        pedido = resultado["request_product"]
        lines.append(f"Producto pedido: {pedido['original_text']}")

        if resultado["status"] == "needs_postal_code":
            lines.append(resultado["clarification_question"])
        elif resultado["status"] == "needs_clarification":
            lines.append(resultado["clarification_question"])
        elif resultado["status"] == "no_matches":
            lines.append("No encontré coincidencias en el catálogo.")
        else:
            if resultado.get("notice"):
                lines.append(resultado["notice"])
            for position, opcion in enumerate(resultado["options"], start=1):
                producto = opcion["product"]
                lines.append(
                    f"Opción {position}: {producto['nombre']} | "
                    f"{producto['formato']} | {producto['precio']:.2f} €"
                )
    return "\n".join(lines)


def responder_usuario(estado: Estado) -> dict:
    respuesta = generar_respuesta(estado["productos_encontrados"])
    return {"respuesta_final": respuesta}

# Construcción del grafo
graph = StateGraph(Estado)

graph.add_node("entender_peticion", entender_peticion)
graph.add_node("buscar_productos", buscar_productos)
graph.add_node("responder_usuario", responder_usuario)

graph.add_edge(START, "entender_peticion")
graph.add_edge("entender_peticion", "buscar_productos")
graph.add_edge("buscar_productos", "responder_usuario")
graph.add_edge("responder_usuario", END)

app = graph.compile()