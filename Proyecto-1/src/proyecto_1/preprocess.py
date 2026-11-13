import pandas as pd
from pathlib import Path
import preprocess_formato

ROOT = Path(__file__).parents[3]
INPUT_PATH = Path(ROOT / "Data" / "Raw" / "catalogo_madrid_centro.csv")
EXPORT_PATH = Path(ROOT  / "Data" / "Clean" / "preprocesado_0_madrid_centro.csv")

def main():
    df = pd.read_csv(INPUT_PATH)

    # Precio total: lo que pago al comprar ese producto
    df["precio"] = df["precio_unidad"].str.replace(',','.').str.strip().str.removesuffix('€').str.strip()
    df = df.drop("precio_unidad", axis=1)

    # Precio por kg, L, ud., ...
    df["formato"] = df["formato_y_precio_por_kilo"].str.split('|').str[0].str.strip()
    df["precio_por_"] = df["formato_y_precio_por_kilo"].str.split('|').str[1].str.strip()
    df = df.drop("formato_y_precio_por_kilo", axis=1)

    df["unidades"] = df["precio_por_"].str.split('/').str[-1]

    # Renombramos algunos valores
    df.loc[df["unidades"] == 'dz', "unidades"] = 'docena'
    df.loc[df["unidades"] == 'dc', "unidades"] = 'docena'
    df.loc[df["unidades"] == "lv", "unidades"] = 'lavado'

    df["precio_por_"] = df["precio_por_"].str.split('€').str[0].str.strip().str.replace(',','.')

    # Dejamos las columnas del formato para el final
    columna_formato = df["formato"]
    df = df.drop("formato", axis=1)
    df = pd.concat([df, columna_formato], axis=1)

    df.to_csv(EXPORT_PATH, index=False, sep=';')

    preprocess_formato.main()

if __name__ == "__main__":
    main()