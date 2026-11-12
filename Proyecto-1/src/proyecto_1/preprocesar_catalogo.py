"""Normaliza formatos del catálogo de Mercadona sin alterar los datos fuente.

Uso desde el directorio Proyecto-1:
    uv run python src/proyecto_1/preprocesar_catalogo.py

Lee catalogo_mercadona_cabo_palos.csv y produce un CSV normalizado y otro de
formatos pendientes. Las columnas originales se conservan literalmente.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT.parent / "catalogo_mercadona_cabo_palos.csv"
OUTPUT = ROOT.parent / "catalogo_mercadona_cabo_palos_normalizado.csv"
PENDING = ROOT.parent / "catalogo_mercadona_cabo_palos_pendientes.csv"

CONTAINERS = (
    "mini botella", "mini brik", "botellín", "benjamín", "garrafa",
    "botella", "brik", "lata", "bote", "tarrito", "tarro", "tarrina",
    "vaso", "sobre", "caja", "paquete", "bolsa", "malla", "bandeja",
    "pieza", "tableta", "pastilla", "tubo", "spray", "frasco", "bol",
    "saco", "manojo",
)

# Unidad física -> valor en unidad canónica y nombre canónico.
PHYSICAL_UNITS = {
    "g": (1.0, "g"), "kg": (1000.0, "g"),
    "ml": (1.0, "ml"), "l": (1000.0, "ml"),
    "m": (1.0, "m"),
}
COUNT_UNITS = {
    "ud", "uds", "unidad", "unidades", "cápsula", "cápsulas", "sobre",
    "sobres", "bolsita", "bolsitas", "lata", "latas", "botella", "botellas",
    "botellín", "botellines", "brik", "briks", "paquete", "paquetes",
    "bolsa", "bolsas", "pack", "packs", "ración", "raciones", "pastilla",
    "pastillas", "barrita", "barritas", "stick", "sticks", "porción",
    "porciones", "loncha", "lonchas", "rebanada", "rebanadas", "vasito",
    "vasitos", "placa", "placas", "chicle", "chicles", "quesito", "quesitos",
    "banda", "bandas", "tira", "tiras", "rollo", "rollos", "servicio",
    "servicios", "lavado", "lavados", "vela", "velas", "ración", "raciones",
    "oblea", "obleas", "lámina", "láminas", "monodosis", "bolsita", "bolsitas",
    "bandeja", "bandejas", "tarrina", "tarrinas", "vaso", "vasos", "tarro", "tarros",
    "bote", "botes", "lata", "latas", "botella", "botellas", "brik", "briks",
    "dosis", "recambio", "recambios",
}

OUT_COLUMNS = [
    "envase", "numero_unidades_venta", "tipo_unidad_venta",
    "numero_unidades_contenido", "tipo_unidad_contenido",
    "numero_unidades_contenido_total",
    "cantidad_por_unidad", "unidad_por_unidad", "cantidad_neta", "unidad_neta",
    "cantidad_escurrida", "unidad_escurrida", "es_pack",
    "estado_clasificacion",
]


def number(value: str) -> float:
    return float(value.replace(",", "."))


def physical(value: str, unit: str) -> tuple[float, str]:
    factor, canonical = PHYSICAL_UNITS[unit.lower()]
    return number(value) * factor, canonical


def container_prefix(text: str) -> tuple[str | None, str]:
    low = text.lower().strip()
    for container in CONTAINERS:
        match = re.match(rf"^{re.escape(container)}\b\s*", low)
        if match:
            # Preserve the spelling from source rather than canonicalizing labels.
            original = text[:len(container)]
            return original, text[match.end():].strip()
    return None, text.strip()


def parse_format(raw: Any) -> dict[str, Any]:
    result = {c: pd.NA for c in OUT_COLUMNS}
    result.update(estado_clasificacion="pendiente")
    if pd.isna(raw) or not str(raw).strip():
        return result

    original = str(raw).strip()
    text = re.sub(r"\s+aprox\.?", "", original, flags=re.IGNORECASE).strip()
    # Extract explicitly labelled drained weight first, whether parenthesized or trailing.
    drain_match = re.search(r"\(?\s*(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\s+escurrido\s*\)?", text, re.I)
    drained = None
    if drain_match:
        drained = physical(drain_match.group(1), drain_match.group(2))
        text = (text[:drain_match.start()] + text[drain_match.end():]).strip(" ()")

    envase, rest = container_prefix(text)
    if envase is not None:
        result["envase"] = envase

    half_piece = re.match(r"^1/2\s+pieza\s+", rest, re.I)
    if half_piece:
        result.update(numero_unidades_contenido=0.5,
                      tipo_unidad_contenido="pieza", es_pack=False)
        rest = rest[half_piece.end():].strip()

    # Explicit multiplication: N counted items x quantity per item.
    mult = re.match(r"^(\d+(?:[.,]\d+)?)\s+(.+?)\s+x\s+(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|m|ud\.?|uds\.?)\s*$", rest, re.I)
    if mult:
        count, kind, qty, unit = mult.groups()
        count_value = number(count)
        result.update(numero_unidades_venta=count_value,
                      tipo_unidad_venta=kind.strip().lower(), es_pack=count_value > 1)
        if unit.lower().startswith("ud"):
            result.update(numero_unidades_contenido=number(qty),
                          tipo_unidad_contenido="ud")
        else:
            per_value, per_unit = physical(qty, unit)
            # N recipientes con cantidad física por recipiente forman una sola
            # presentación comercial; N queda como contenido del pack.
            result.update(numero_unidades_venta=1,
                          tipo_unidad_venta="pack",
                          numero_unidades_contenido=count_value,
                          tipo_unidad_contenido=kind.strip().lower(),
                          cantidad_por_unidad=number(qty), unidad_por_unidad=unit,
                          cantidad_neta=count_value * per_value, unidad_neta=per_unit)
        if drained:
            result.update(cantidad_escurrida=drained[0], unidad_escurrida=drained[1])
        result.update(estado_clasificacion="clasificado")
        return result

    # A parenthesized physical amount is the agreed total net amount unless explicitly drained.
    parenthetical = re.search(r"\(\s*(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|m)\s*\)", rest, re.I)
    if parenthetical:
        net_value, net_unit = physical(parenthetical.group(1), parenthetical.group(2))
        result.update(cantidad_por_unidad=number(parenthetical.group(1)),
                      unidad_por_unidad=parenthetical.group(2),
                      cantidad_neta=net_value, unidad_neta=net_unit)
        rest = (rest[:parenthetical.start()] + rest[parenthetical.end():]).strip()

    # Parenthetical count gives the contents of a single outer package.
    parenthetical_count = re.search(r"\(\s*(\d+(?:[.,]\d+)?)\s+(ud\.?|uds?\.?|unidades?)\s*\)", rest, re.I)
    if parenthetical_count:
        result.update(numero_unidades_venta=1,
                      numero_unidades_contenido=number(parenthetical_count.group(1)),
                      tipo_unidad_contenido="ud", es_pack=number(parenthetical_count.group(1)) > 1)
        rest = (rest[:parenthetical_count.start()] + rest[parenthetical_count.end():]).strip()

    # Service-count-per-sale-unit form: "300 servicios (3 ud.)".
    service = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s+(servicios|lavados|raciones)\.?", rest, re.I)
    if service and not pd.isna(result["numero_unidades_venta"]):
        result.update(cantidad_por_unidad=number(service.group(1)),
                      unidad_por_unidad=service.group(2).lower())
        rest = ""

    # Counted contents before a parenthetical total, e.g. "16 cápsulas" or "10 raciones".
    count_match = re.search(r"(?:^|\s)(\d+(?:[.,]\d+)?)\s+([\wáéíóúñ]+)\.?\s*$", rest, re.I)
    if count_match:
        count_token, kind = count_match.groups()
        normalized_kind = kind.lower().rstrip(".")
        if normalized_kind in COUNT_UNITS:
            count = number(count_token)
            result.update(numero_unidades_contenido=count,
                          tipo_unidad_contenido=normalized_kind,
                          es_pack=(count > 1))
            rest = rest[:count_match.start()].strip()
        elif normalized_kind in PHYSICAL_UNITS:
            amount, unit = physical(count_token, normalized_kind)
            result.update(cantidad_por_unidad=number(count_token),
                          unidad_por_unidad=kind)
            if pd.isna(result["cantidad_neta"]):
                result.update(cantidad_neta=amount, unidad_neta=unit)
            rest = rest[:count_match.start()].strip()

    # A standalone or prefixed declared physical amount (e.g. "Caja 1 L", "150 ml").
    amount_matches = list(re.finditer(r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|m)\b", rest, re.I))
    if amount_matches and pd.isna(result["cantidad_neta"]):
        match = amount_matches[-1]
        amount, unit = physical(match.group(1), match.group(2))
        result.update(cantidad_por_unidad=number(match.group(1)),
                      unidad_por_unidad=match.group(2),
                      cantidad_neta=amount, unidad_neta=unit)
        rest = (rest[:match.start()] + rest[match.end():]).strip()

    if drained:
        result.update(cantidad_escurrida=drained[0], unidad_escurrida=drained[1])
        if pd.isna(result["cantidad_neta"]):
            # Approved rule: when only drained quantity is supplied, net equals it.
            result.update(cantidad_neta=drained[0], unidad_neta=drained[1])

    # Explicit non-multipack single-unit declarations.
    if pd.isna(result["es_pack"]) and not pd.isna(result["numero_unidades_contenido"]) and result["numero_unidades_contenido"] == 1:
        result["es_pack"] = False

    # Any unexplained residue means the record needs review rather than forced parsing.
    residue = re.sub(r"[().\s]", "", rest)
    known_prefix = envase is not None and not residue
    has_measure = not pd.isna(result["cantidad_neta"])
    has_count = not pd.isna(result["numero_unidades_contenido"])
    if (known_prefix or has_measure or has_count) and not residue:
        result["estado_clasificacion"] = "clasificado"
    else:
        result["estado_clasificacion"] = "pendiente"

    return result


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"No existe el CSV de entrada: {INPUT}")
    df = pd.read_csv(INPUT, dtype={"cp": "string"}, encoding="utf-8-sig")
    required = {"cp", "categoria", "subcategoria", "nombre", "formato_y_precio_por_kilo", "precio_unidad"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas originales requeridas: {sorted(missing)}")

    # Deriva `formato` sin sustituir ni editar ninguna columna de origen.
    df["formato"] = df["formato_y_precio_por_kilo"].astype("string").str.split("|", n=1).str[0].str.strip()
    parsed = pd.DataFrame([parse_format(x) for x in df["formato"]], index=df.index)
    result = pd.concat([df, parsed], axis=1)

    # Completa los nulos según los criterios acordados tras conservar el formato literal.
    result["envase"] = result["envase"].fillna("Revisar nombre")
    # Una presentación con envase singular reconocido cuenta como una unidad
    # de contenido si no se declaró un recuento interno diferente.
    missing_content_count = result["numero_unidades_contenido"].isna() & result["envase"].ne("Revisar nombre")
    result.loc[missing_content_count, "numero_unidades_contenido"] = 1
    result.loc[missing_content_count, "tipo_unidad_contenido"] = result.loc[missing_content_count, "envase"]
    result["numero_unidades_venta"] = pd.to_numeric(
        result["numero_unidades_venta"], errors="coerce"
    ).fillna(1).astype("Float64")
    result["tipo_unidad_venta"] = result["tipo_unidad_venta"].fillna(result["envase"])
    result["tipo_unidad_contenido"] = result["tipo_unidad_contenido"].fillna(result["envase"])
    result["es_pack"] = result["es_pack"].astype("boolean").fillna(False)

    # Si no se indicó el escurrido, usar la cantidad neta disponible como acordado.
    result["cantidad_escurrida"] = result["cantidad_escurrida"].fillna(
        result["cantidad_neta"]
    )
    result["unidad_escurrida"] = result["unidad_escurrida"].fillna(
        result["unidad_neta"]
    )

    # Numeric outputs use nullable pandas numbers; categorical flags retain unknowns.
    for col in ("numero_unidades_venta", "numero_unidades_contenido", "cantidad_por_unidad", "cantidad_neta", "cantidad_escurrida"):
        result[col] = pd.to_numeric(result[col], errors="coerce").astype("Float64")
    result["numero_unidades_contenido_total"] = (
        result["numero_unidades_venta"] * result["numero_unidades_contenido"]
    ).astype("Float64")
    result["es_pack"] = result["es_pack"].astype("boolean")
    result.to_csv(OUTPUT, index=False, encoding="utf-8-sig", decimal=",")
    pending = result[result["estado_clasificacion"] != "clasificado"]
    pending.to_csv(PENDING, index=False, encoding="utf-8-sig", decimal=",")

    print(f"Entrada: {len(df)} filas; formatos únicos: {df['formato'].nunique()}")
    print(f"Clasificados: {(result['estado_clasificacion'] == 'clasificado').sum()} "
          f"({(result['estado_clasificacion'] == 'clasificado').mean():.1%})")
    print(f"Pendientes: {len(pending)} ({len(pending) / len(result):.1%})")
    print("Estados:\n", result["estado_clasificacion"].value_counts(dropna=False).to_string())
    print("Envases:\n", result["envase"].value_counts(dropna=False).to_string())
    print(f"CSV normalizado: {OUTPUT}")
    print(f"Pendientes: {PENDING}")


if __name__ == "__main__":
    main()
