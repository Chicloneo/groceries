from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

from .catalog_search import search
from .contracts import ShoppingRequest
from .interpreter import parse_request


class Estado(TypedDict, total=False):
    peticion_usuario: str
    codigo_postal: str | None
    categoria_seleccionada: str | None
    subcategoria_seleccionada: str | None
    peticion_estructurada: ShoppingRequest
    productos_encontrados: list[dict[str, Any]]
    respuesta_final: str


def entender_peticion(estado: Estado) -> dict:
    peticion = parse_request(
        estado["peticion_usuario"],
        cp=estado.get("codigo_postal"),
    )
    categoria = estado.get("categoria_seleccionada")
    subcategoria = estado.get("subcategoria_seleccionada")
    if categoria or subcategoria:
        productos = []
        for producto in peticion.products:
            values = producto.model_dump()
            values["categoria"] = categoria
            values["subcategoria"] = subcategoria
            productos.append(type(producto).model_validate(values))
        peticion = peticion.model_copy(update={"products": productos})
    return {
        "peticion_estructurada": peticion,
        "codigo_postal": peticion.cp,
    }


def buscar_productos(estado: Estado) -> dict:
    encontrados = search(
        estado["peticion_estructurada"],
        taxonomy_only=bool(
            estado.get("categoria_seleccionada")
            or estado.get("subcategoria_seleccionada")
        ),
    )
    return {"productos_encontrados": encontrados}


def generar_respuesta(productos: list[dict[str, Any]]) -> str:
    if not productos:
        return "No encontré productos concretos en tu petición."

    lines = []
    for resultado in productos:
        pedido = resultado["request_product"]
        lines.append(f"Producto pedido: {pedido['original_text']}")

        status = resultado["status"]
        if status in {"needs_postal_code", "needs_clarification"}:
            lines.append(resultado["clarification_question"])
        elif status == "no_matches":
            lines.append("No encontré coincidencias en el catálogo.")
        else:
            if resultado.get("notice"):
                lines.append(resultado["notice"])
            lines.append("Elige una de estas opciones. Indica el número:")
            for position, opcion in enumerate(resultado["options"], start=1):
                producto = opcion["product"]
                lines.append(
                    f"{position}. {producto['nombre']} | "
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