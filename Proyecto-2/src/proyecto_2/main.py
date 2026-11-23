import argparse

from .compras.graph import app
from .clasificador.cli import main as clasificador_main


def main() -> int:
    parser = argparse.ArgumentParser(description="Herramientas de Proyecto 2")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    comprar = subparsers.add_parser(
        "comprar",
        help="Buscar productos por lenguaje natural",
    )
    comprar.add_argument("peticion")
    comprar.add_argument("--cp", default="28012")

    clasificar = subparsers.add_parser(
        "clasificar",
        help="Clasificar o entrenar productos",
    )
    clasificar.add_argument("argumentos", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    if args.comando == "comprar":
        result = app.invoke({
            "peticion_usuario": args.peticion,
            "codigo_postal": args.cp,
        })
        print(result["respuesta_final"])
        return 0

    return clasificador_main(args.argumentos)


if __name__ == "__main__":
    raise SystemExit(main())
