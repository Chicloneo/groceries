from proyecto_2.grafo.graph import app

def main():
    print("Escribe qué quieres comprar.\n")

    while True:
        peticion = input("Productos: ").strip()

        if peticion.lower() in {"salir", "exit", "quit", "quit()", "q", "exit()"}:
            print("¡Hasta luego!")
            break

        if not peticion:
            continue

        resultado = app.invoke({
            "peticion_usuario": peticion
        })

        print("\n")
        print(resultado["respuesta_final"])
        print()

if __name__ == "__main__":
    main()
