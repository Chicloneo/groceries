from typing import TypedDict
from langgraph.graph import StateGraph, START, END


def interpretar_con_llm():
    #TODO
    pass
def buscar_en_base_de_datos():
    #TODO
    pass
def generar_respuesta():
    #TODO
    pass

# Estado compartido: los datos que viajan entre pasos
class Estado(TypedDict):
    peticion_usuario: str
    productos_entendidos: dict
    productos_encontrados: list
    respuesta_final: str

# PASO 1: entender lo que pide el usuario
def entender_peticion(estado: Estado) -> dict:
    texto = estado["peticion_usuario"]

    # Aquí irá tu LLM con salida JSON estructurada.
    # Por ahora, versión abstracta:
    productos_entendidos = interpretar_con_llm(texto)

    return {"productos_entendidos": productos_entendidos}

# PASO 2: buscar en tu base de datos
def buscar_productos(estado: Estado) -> dict:
    productos_entendidos = estado["productos_entendidos"]

    # Aquí irá SQLite, no un LLM.
    productos_encontrados = buscar_en_base_de_datos(productos_entendidos)

    return {"productos_encontrados": productos_encontrados}

# PASO 3: generar la respuesta para el usuario
def responder_usuario(estado: Estado) -> dict:
    productos = estado["productos_encontrados"]

    # Aquí puede ir otro LLM, o incluso texto plantilla.
    respuesta_final = generar_respuesta(productos)

    return {"respuesta_final": respuesta_final}

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

# Ejemplo de uso
resultado = app.invoke({
    "peticion_usuario": "Quiero leche deslactosada y dos paquetes de arroz"
})

print(resultado["respuesta_final"])