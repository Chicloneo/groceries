import argparse

from proyecto_2.grafo.graph import app


def main():
    parser = argparse.ArgumentParser(
        description="Busca productos y muestra opciones del catálogo."
    )
    parser.add_argument("request", nargs="?", help="Petición de compra")
    parser.add_argument("--cp", default="28012", help="Código postal")
    args = parser.parse_args()

    while True:
        peticion = args.request or input("Productos: ").strip()

        if peticion.lower() in {"salir", "exit", "quit", "quit()", "q", "exit()"}:
            print("¡Hasta luego!")
            break

        if not peticion:
            continue

        resultado = app.invoke({
            "peticion_usuario": peticion,
            "codigo_postal": args.cp,
        })

        print("\n")
        print(resultado["respuesta_final"])
        print()

        if args.request:
            break


if __name__ == "__main__":
    main()
