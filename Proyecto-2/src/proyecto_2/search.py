"""Recieve Producto, a json response from the LLM, and search for possible products
coincidences among every product in the csv. """

from .contracts import Producto, ShoppingRequest
import pandas as pd
from pathlib import Path

DATAPATH = Path(__file__).parents[2] / "Data" / "Clean" / "preprocesado_1_madrid_centro.csv"

"""
{
  "request": "Necesito comprar 6 L de leche semidesnatada y carne picada",
  "cp": null,
  "products": [
    {
      "original_text": "6 L de leche semidesnatada",
      "pseudo_name": "leche semidesnatada",
      "search_terms": [
        "leche semidesnatada"
      ],
      "requested_quantity": 6.0,
      "requested_unit": "L",
      "features": [
        "semidesnatada"
      ],
      "categoria": "Huevos, leche y mantequilla",
      "subcategoria": "Leche y bebidas vegetales"
    },
    {
      "original_text": "carne picada",
      "pseudo_name": "carne picada",
      "search_terms": [
        "carne picada"
      ],
      "requested_quantity": null,
      "requested_unit": null,
      "features": [],
      "categoria": "Carne",
      "subcategoria": "Hamburguesas y picadas"
    }
  ]
}
"""

def load_dataframe():
   return pd.read_csv(DATAPATH, sep=';')

def search(response: ShoppingRequest) -> list[dict]:

    df = load_dataframe()

    lista_productos = response.products

    for producto in lista_productos:
      
      original_text = producto["original_text"]
      pseudo_name = producto["pseudo_name"]
      search_terms = producto["search_terms"]

      requested_quantity = producto["requested_quantity"]
      requested_unit = producto["requested_unit"]

      features = producto["features"]

      categoria = producto["categoria"]
      subcategoria = producto["subcategoria"]