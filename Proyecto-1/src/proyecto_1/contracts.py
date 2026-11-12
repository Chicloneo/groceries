from pydantic import BaseModel, ConfigDict, Field, field_validator
import pandas as pd


class ProductoMercadona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cp: str = Field(pattern=r"^\d{5}$")
    categoria: str
    subcategoria: str
    nombre: str
    formato_y_precio_por_kilo: str
    precio_unidad: float = Field(gt=0)
    formato: str
    envase: str
    numero_unidades_venta: int = Field(gt=0)
    tipo_unidad_venta: str
    numero_unidades_contenido: float | None = None
    tipo_unidad_contenido: str | None = None
    numero_unidades_contenido_total: float | None = None
    cantidad_por_unidad: float | None = None
    unidad_por_unidad: str | None = None
    cantidad_neta: float | None = None
    unidad_neta: str | None = None
    cantidad_escurrida: float | None = None
    unidad_escurrida: str | None = None
    es_pack: bool

    @field_validator("numero_unidades_contenido",
                    "numero_unidades_contenido_total",
                    "cantidad_por_unidad",
                    "unidad_por_unidad",
                    "cantidad_neta",
                    "unidad_neta",
                    "cantidad_escurrida",
                    "unidad_escurrida",
                    mode="before")
    @classmethod
    def pandas_null_to_none(cls, value):
        if value is None or pd.isna(value) or value == "":
            return None
        return value

    @field_validator("precio_unidad",
                      "cantidad_por_unidad",
                      "cantidad_neta",
                      "cantidad_escurrida",
                      "numero_unidades_contenido_total",
                      "numero_unidades_contenido",
                      mode="before")
    @classmethod
    def parse_decimal(cls, value):
        if value is None or pd.isna(value) or value == "":
            return None
        if isinstance(value, str):
            value = value.strip().replace("€", "").replace(",", ".").split()[0]
        return float(value)

    @field_validator("numero_unidades_venta", 
                     mode="before")
    @classmethod
    def parse_integer(cls, value):
        if value is None or pd.isna(value) or value == "":
            return value
        if isinstance(value, str):
            value = value.strip().replace(",", ".").split()[0]
        number = float(value)
        if not number.is_integer():
            raise ValueError("debe ser un número entero")
        return int(number)

    @field_validator("es_pack", mode="before")
    @classmethod
    def parse_boolean(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1"}:
                return True
            if normalized in {"false", "0"}:
                return False
            raise ValueError("debe ser true/false o 1/0")
        if value is None or pd.isna(value):
            return value
        if value in (0, 1):
            return bool(value)
        raise ValueError("debe ser true/false o 1/0")

    @field_validator(
        "categoria",
        "subcategoria",
        "nombre",
        "formato_y_precio_por_kilo",
        "formato",
        "envase",
        "tipo_unidad_venta",
        mode="before",
    )
    @classmethod
    def required_text(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("no puede estar vacío")
        return value