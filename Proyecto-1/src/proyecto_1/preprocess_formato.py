"""Preprocesa la columna `formato` del catálogo limpio de Madrid Centro.

Lee Data/Clean/preprocesado_0_madrid_centro.csv y genera
Data/Clean/preprocesado_1_madrid_centro.csv, conservando todas las columnas
de entrada y añadiendo únicamente los campos derivados de `formato`.

Uso desde cualquier directorio:
    uv run python src/proyecto_1/preprocess_formato.py
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
INPUT_PATH = ROOT / "Data" / "Clean" / "preprocesado_0_madrid_centro.csv"
OUTPUT_PATH = ROOT / "Data" / "Clean" / "preprocesado_1_madrid_centro.csv"
CSV_SEPARATOR = ";"

OUTPUT_COLUMNS = [
    "es_pack",
    "numero_unidades_pack",
    "numero_subunidades_pack_por_unidad",
    "cantidad producto",
    "medida_producto",
]

NUMBER = r"\d+(?:[.,]\d+)?"
PHYSICAL_UNIT = r"kg|g|ml|l|m"
COUNT_UNIT = (
    r"ud\.?|uds?\.?|unidades?|sobres?|bolsitas?|pastillas?|sticks?|"
    r"chicles?|latas?|botellas?|botellines?|briks?|mini\s+briks?|botes?|"
    r"paquetes?|bolsas?|vasitos?|vasos?|monodosis|placas?|raciones?|"
    r"dosis|recambios?|cápsulas?|barras?|barritas?|piezas?|tabletas?|"
    r"porciones?|servicios?|lavados?|tarrinas?|tarros?|bandejas?"
)

COUNT_RE = re.compile(rf"(?P<count>{NUMBER})\s*(?P<unit>{COUNT_UNIT})\b", re.I)
PAREN_AMOUNT_RE = re.compile(
    rf"\(\s*(?P<amount>{NUMBER})\s*(?P<unit>{PHYSICAL_UNIT})\s*\)", re.I
)
DRAINED_RE = re.compile(
    rf"\(?\s*(?P<amount>{NUMBER})\s*(?P<unit>{PHYSICAL_UNIT})\s+escurrido\s*\)?",
    re.I,
)
MULTIPLIED_AMOUNT_RE = re.compile(
    rf"\bx\s*(?P<amount>{NUMBER})\s*(?P<unit>{PHYSICAL_UNIT})\b", re.I
)
PHYSICAL_AMOUNT_RE = re.compile(
    rf"(?P<amount>{NUMBER})\s*(?P<unit>{PHYSICAL_UNIT})\b", re.I
)


def parse_number(value: Any) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return float(str(value).strip().replace(",", "."))


def normalize_physical_amount(amount: float, unit: str) -> tuple[float, str]:
    """Normaliza masa a g, volumen a ml y longitud a m."""
    unit = unit.lower()
    if unit == "kg":
        return amount * 1000, "g"
    if unit == "g":
        return amount, "g"
    if unit == "l":
        return amount * 1000, "ml"
    if unit == "ml":
        return amount, "ml"
    return amount, "m"


def implied_total_from_price(row: pd.Series) -> tuple[float, str] | None:
    """Calcula el contenido total implícito en precio/precio por medida.

    Sirve para reconocer una excepción confirmada: cuando el precio por kg,
    litro, 100 g o 100 ml ya corresponde al total indicado entre paréntesis,
    ese valor no se multiplica por el recuento del pack.
    """
    price = parse_number(row.get("precio"))
    unit_price = parse_number(row.get("precio_por_"))
    price_unit = str(row.get("unidades", "")).strip().lower().replace(" ", "")
    if price is None or unit_price is None or unit_price <= 0:
        return None

    ratio = price / unit_price
    if price_unit == "kg":
        return ratio * 1000, "g"
    if price_unit == "100g":
        return ratio * 100, "g"
    if price_unit == "l":
        return ratio * 1000, "ml"
    if price_unit == "100ml":
        return ratio * 100, "ml"
    return None


def matches_parenthetical_total(
    row: pd.Series,
    amount: float,
    unit: str,
    multiplier: float,
) -> bool:
    """Detecta si el valor parentético ya es el total del envase.

    Se tolera un 12 % porque el precio unitario puede estar redondeado o
    expresado por 100 g/ml; las excepciones confirmadas se contrastaron con
    este cálculo sobre los datos del CSV.
    """
    implied = implied_total_from_price(row)
    if implied is None:
        return False
    candidate, candidate_unit = normalize_physical_amount(amount, unit)
    implied_amount, implied_unit = implied
    if candidate_unit != implied_unit:
        return False
    relative_difference = abs(implied_amount - candidate) / max(abs(candidate), 0.01)
    return relative_difference <= 0.12 and multiplier > 1


def extract_format_values(row: pd.Series) -> dict[str, Any]:
    """Extrae atributos acordados de un valor de formato."""
    text = str(row.get("formato", "")).strip()
    # La cantidad aproximada se considera exacta, según el criterio acordado.
    text = re.sub(r"\s+aprox\.?", "", text, flags=re.I).strip()

    # Recuento de unidades explícito. El primer recuento del formato es el
    # número de unidades principales del pack (p. ej. 3 botes, 20 bolsitas).
    count_matches = list(COUNT_RE.finditer(text))
    pack_count = parse_number(count_matches[0].group("count")) if count_matches else None
    is_pack = bool(pack_count is not None and pack_count > 1)

    # Escurrido prevalece siempre sobre el contenido neto. En un pack, el
    # valor escurrido expresado para cada envase se multiplica por el recuento.
    drained = DRAINED_RE.search(text)
    parenthetical = PAREN_AMOUNT_RE.search(text)
    if drained:
        amount = parse_number(drained.group("amount"))
        unit = drained.group("unit")
        total_multiplier = pack_count if is_pack else 1
    elif parenthetical:
        amount = parse_number(parenthetical.group("amount"))
        unit = parenthetical.group("unit")
        if is_pack and matches_parenthetical_total(row, amount, unit, pack_count):
            total_multiplier = 1
        else:
            total_multiplier = pack_count if is_pack else 1
    else:
        # En expresiones N x cantidad, la cantidad corresponde a cada unidad.
        multiplied = MULTIPLIED_AMOUNT_RE.search(text)
        physical = multiplied or PHYSICAL_AMOUNT_RE.search(text)
        if physical:
            amount = parse_number(physical.group("amount"))
            unit = physical.group("unit")
            total_multiplier = pack_count if is_pack else 1
        else:
            amount = None
            unit = None
            total_multiplier = 1

    if amount is not None and unit is not None:
        total_amount, measure = normalize_physical_amount(amount * total_multiplier, unit)
    else:
        total_amount, measure = pd.NA, pd.NA

    return {
        "es_pack": is_pack,
        "numero_unidades_pack": pack_count if is_pack else pd.NA,
        "numero_subunidades_pack_por_unidad": 1 if is_pack else pd.NA,
        "cantidad producto": total_amount,
        "medida_producto": measure,
    }


def main() -> None:
    if not INPUT_PATH.is_file():
        raise FileNotFoundError(f"No existe el CSV de entrada: {INPUT_PATH}")
    df = pd.read_csv(
        INPUT_PATH,
        sep=CSV_SEPARATOR,
        dtype="string",
        encoding="utf-8-sig",
    )
    required = {"formato", "precio", "precio_por_", "unidades"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}")

    collisions = set(OUTPUT_COLUMNS) & set(df.columns)
    if collisions:
        raise ValueError(
            "El CSV ya contiene columnas de este preprocesado: "
            + ", ".join(sorted(collisions))
        )

    parsed = pd.DataFrame(
        [extract_format_values(row) for _, row in df.iterrows()],
        index=df.index,
        columns=OUTPUT_COLUMNS,
    )
    for column in ("numero_unidades_pack", "numero_subunidades_pack_por_unidad", "cantidad producto"):
        parsed[column] = pd.to_numeric(parsed[column], errors="coerce").astype("Float64")
    parsed["es_pack"] = parsed["es_pack"].astype("boolean")
    result = pd.concat([df, parsed], axis=1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Se conserva el formato textual de las columnas preprocesadas; las nuevas
    # cantidades se escriben con punto decimal, sin reformatear `precio`.
    result.to_csv(OUTPUT_PATH, index=False, sep=CSV_SEPARATOR, encoding="utf-8-sig")

    print(f"Filas procesadas: {len(result)}")
    print(f"Packs: {int(result['es_pack'].sum())}")
    print(f"Cantidad producto nula: {int(result['cantidad producto'].isna().sum())}")
    print(f"CSV generado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
