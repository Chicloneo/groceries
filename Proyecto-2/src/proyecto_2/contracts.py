"""Modelos Pydantic y contratos de datos del pipeline LLM."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .categorias import CATEGORIAS, SUBCATEGORIAS

# --------------------------------------------------------------------------
# Esquemas Pydantic
# --------------------------------------------------------------------------
# Dejamos los campos requeridos en el JSON incluso cuando aceptan null. Así el
# modelo debe declarar qué información no pudo extraer, en vez de omitirla.

Unit = Literal['L','kg','100 g','ud','100 ml','docena','lavado','m']
# Separada de Unit: estas son magnitudes que la persona puede pedir.
RequestedUnit = Literal["g", "kg", "ml", "L", "ud", "docena", "pack"]
# El preprocesado convierte el contenido físico a gramos, mililitros o metros.
ProductMeasure = Literal["g", "ml", "m"]

class Producto(BaseModel):
    """Intención pedida por el usuario, todavía sin datos de catálogo."""

    original_text: str = Field(
        min_length=1,
        description="Fragmento del mensaje original que corresponde al producto.",
    )
    pseudo_name: str = Field(
        min_length=1,
        description="Descripción breve de búsqueda; no tiene que ser el nombre del CSV.",
    )
    search_terms: list[str] = Field(
        min_length=1,
        max_length=3,
        description=(
            "Consultas en español para buscar este producto; conservan las "
            "características expresadas por el usuario."
        ),
    )
    requested_quantity: float | None = Field(
        gt=0,
        description=(
            "Cantidad solicitada por el usuario, no contenido del envase. "
            "null si no se especificó."
        ),
    )
    requested_unit: RequestedUnit | None = Field(
        description=(
            "Unidad de la cantidad solicitada: g, kg, ml, L, ud, docena o pack; "
            "null si falta."
        )
    )
    features: list[str] = Field(
        description=(
            "Atributos expresados por el usuario que ayudan a buscar, como marca, "
            "variedad, sabor o presentación; [] si no hay. No inferirlos."
        )
    )
    categoria: str | None = Field(
        description=(
            "Categoría predicha como pista para Python; null si no es clara. "
            "No confirma que exista una fila coincidente."
        )
    )
    subcategoria: str | None = Field(
        description="Pista de subclasificación; null si no es clara."
    )

    @field_validator("categoria", mode='before')
    @classmethod
    def validar_categoria(cls, value):
        if value is not None and value not in CATEGORIAS:
            raise ValueError(f"El modelo falló al predecir la categoría \
                             {value} dentro de CATEGORIAS")
        return value

    @field_validator("subcategoria", mode='before')
    @classmethod
    def validar_subcategoria(cls, value):
        if value is not None and value not in SUBCATEGORIAS:
            raise ValueError(f"El modelo falló al predecir la subcategoría \
                             {value} dentro de SUBCATEGORIAS")
        return value


class _ShoppingRequestPayload(BaseModel):
    """JSON de extracción antes de que Python adjunte el texto original."""

    cp: str | None = Field(
        pattern=r"^\d{5}$",
        description="Código postal de cinco dígitos si se indicó; null si falta.",
    )
    products: list[Producto]


class ShoppingRequest(BaseModel):
    """Solicitud validada que recibe el backend de búsqueda."""

    request: str
    cp: str | None = Field(pattern=r"^\d{5}$")
    products: list[Producto]


class CatalogProduct(BaseModel):
    """Fila real de preprocesado_1; estos datos los aporta Python/pandas."""

    model_config = ConfigDict(populate_by_name=True)

    cp: str = Field(pattern=r"^\d{5}$")
    categoria: str
    subcategoria: str
    nombre: str
    precio: float = Field(gt=0)
    precio_por_: float | None
    unidades: Unit | None
    formato: str
    es_pack: bool
    numero_unidades_pack: int | None
    numero_subunidades_pack_por_unidad: int | None
    cantidad_producto: float | None = Field(alias="cantidad producto") #quitar el alias si vuelvo a ejecutar el script de extracción
    medida_producto: ProductMeasure | None

    @field_validator(
        "precio_por_",
        "unidades",
        "numero_unidades_pack",
        "numero_subunidades_pack_por_unidad",
        "cantidad_producto",
        "medida_producto",
        mode="before",
    )
    @classmethod
    def normalizar_nulos_csv(cls, value):
        """Trata celdas vacías y nulos comunes de pandas como ausencia de dato."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if type(value).__name__ in {"NAType", "NaTType"}:
            return None
        try:
            if math.isnan(value):
                return None
        except (TypeError, ValueError):
            pass
        return value

    @field_validator("categoria", mode="before")
    @classmethod
    def validar_categoria_catalogo(cls, value):
        if value not in CATEGORIAS:
            raise ValueError(f"Categoría fuera de CATEGORIAS: {value}")
        return value

    @field_validator("subcategoria", mode="before")
    @classmethod
    def validar_subcategoria_catalogo(cls, value):
        if value not in SUBCATEGORIAS:
            raise ValueError(f"Subcategoría fuera de SUBCATEGORIAS: {value}")
        return value


class ProductOption(BaseModel):
    """Opción real mostrada al usuario, ligada a una fila del catálogo."""

    option_id: str = Field(min_length=1)
    product: CatalogProduct


class ProductSelection(BaseModel):
    """Elección posterior: cantidad de unidades comerciales de una opción."""

    option_id: str = Field(
        min_length=1,
        description="Identificador de una opción que el backend mostró al usuario.",
    )
    sale_quantity: int = Field(
        gt=0,
        description="Número de unidades comerciales que el usuario quiere comprar.",
    )


class SelectionRequest(BaseModel):
    selections: list[ProductSelection] = Field(
        description="Opciones elegidas y cantidad comercial de cada una."
    )
    needs_clarification: bool = Field(
        description="True si no se entiende qué opción quiere el usuario."
    )
    clarification_question: str | None = Field(
        description="Pregunta para resolver la ambigüedad; null si no hace falta."
    )


class LLMError(Exception):
    """Error de Ollama o de una respuesta que no cumple el contrato Pydantic."""



