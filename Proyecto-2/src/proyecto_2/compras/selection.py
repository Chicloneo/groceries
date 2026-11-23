def buscar_opcion_por_numero(
    texto: str,
    opciones: list[dict],
) -> dict | None:
    numero = texto.strip()
    if not numero.isdigit():
        return None

    posicion = int(numero)
    if not 1 <= posicion <= len(opciones):
        return None
    return opciones[posicion - 1]
