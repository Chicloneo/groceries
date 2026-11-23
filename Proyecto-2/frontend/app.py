import streamlit as st

from proyecto_2.clasificador.taxonomia import (
    cargar_mapa_categoria_subcategoria,
)
from proyecto_2.compras.graph import app
from proyecto_2.compras.selection import (
    interpretar_seleccion,
    sumar_cesta,
    intentar_seleccion_determinista,
)


st.set_page_config(
    page_title="Asistente de compra",
    page_icon="🛒",
    layout="centered",
)

st.markdown(
    """
    <style>
    :root { color-scheme: dark; }
    html, body, .stApp {
        background: #111827;
        color: #f8fafc;
    }
    [data-testid="stHeader"] {
        background: #111827;
    }
    [data-testid="stToolbar"] {
        background: transparent;
    }
    [data-testid="stMain"] {
        background: #111827;
    }
    [data-testid="stAppViewContainer"] {
        background: #111827;
    }
    [data-testid="stAppViewContainer"] .main .block-container {
        background: #111827;
        color: #f8fafc;
        max-width: 900px;
        padding-top: 2.5rem;
    }
    h1, h2, h3, p, span, label, caption, small {
        color: #f8fafc !important;
    }
    [data-testid="stCaptionContainer"] {
        color: #cbd5e1 !important;
    }
    [data-testid="stChatMessage"] {
        background: #1f2937;
        color: #f8fafc;
        border-radius: 14px;
        padding: 12px 16px;
        border: 1px solid #374151;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.20);
    }
    [data-testid="stChatMessage"] * {
        color: #f8fafc !important;
    }
    [data-testid="stChatInput"] {
        background: #1f2937;
        border: 1px solid #4b5563;
        border-radius: 12px;
    }
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input {
        color: #f8fafc !important;
        -webkit-text-fill-color: #f8fafc;
        caret-color: #f8fafc;
    }
    [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stChatInput"] input::placeholder {
        color: #94a3b8 !important;
        opacity: 1;
    }
    [data-testid="stAlert"] {
        background: #1f2937;
        color: #f8fafc;
        border: 1px solid #374151;
    }
    [data-testid="stAlert"] * {
        color: #f8fafc !important;
    }
    [data-baseweb="select"] > div {
        background: #1f2937 !important;
        color: #f8fafc !important;
        border-color: #4b5563 !important;
    }
    [data-baseweb="input"] > div,
    [data-testid="stTextInput"] input {
        background: #1f2937 !important;
        color: #f8fafc !important;
        -webkit-text-fill-color: #f8fafc;
        border-color: #4b5563 !important;
    }
    [data-testid="stSidebar"] {
        background: #0b1120;
        border-right: 1px solid #263244;
    }
    [data-testid="stSidebar"] * {
        color: #f8fafc;
    }
    [data-testid="stSidebar"] .stButton button {
        background: #1f2937;
        color: #f8fafc;
        border: 1px solid #4b5563;
        border-radius: 10px;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: #374151;
        color: #ffffff;
        border-color: #64748b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

EJEMPLOS = [
    "Leche semidesnatada Hacendado 1 litro",
    "Aceite de oliva virgen extra Hacendado 1 litro",
    "Huevos frescos 12 unidades",
]

if "mensajes" not in st.session_state:
    st.session_state.mensajes = []
    st.session_state.pendiente = None
    st.session_state.opciones_pendientes = []
    st.session_state.seleccion_actual = None
    st.session_state.categoria_seleccionada = None
    st.session_state.subcategoria_seleccionada = None
    st.session_state.cesta = {}
    st.session_state.opciones_por_id = {}
    st.session_state.seleccion_cache = {}
    st.session_state.seleccion_cache = {}

with st.sidebar:
    st.markdown("### Prueba con...")
    for index, ejemplo in enumerate(EJEMPLOS):
        if st.button(ejemplo, key=f"ejemplo-{index}", use_container_width=True):
            st.session_state.pendiente = ejemplo
            st.session_state.categoria_seleccionada = None
            st.session_state.subcategoria_seleccionada = None
            st.session_state.cesta = {}
            st.session_state.opciones_por_id = {}
            st.session_state.seleccion_cache = {}
    st.markdown("---")
    if st.button("Nueva conversación", use_container_width=True):
        st.session_state.mensajes = []
        st.session_state.pendiente = None
        st.session_state.opciones_pendientes = []
        st.session_state.seleccion_actual = None
        st.session_state.categoria_seleccionada = None
        st.session_state.subcategoria_seleccionada = None
        st.session_state.cesta = {}
        st.session_state.opciones_por_id = {}
        st.session_state.seleccion_cache = {}
        st.rerun()

    if st.session_state.cesta:
        st.markdown("---")
        st.markdown("### Cesta")
        for option_id, cantidad in st.session_state.cesta.items():
            opcion = st.session_state.opciones_por_id[option_id]
            producto = opcion["product"]
            st.markdown(
                f"- {cantidad} × {producto['nombre']} "
                f"({producto['formato']}): "
                f"{producto['precio'] * cantidad:.2f} €"
            )
        total = sumar_cesta(
            st.session_state.cesta,
            st.session_state.opciones_por_id,
        )
        st.markdown(f"**Total: {total:.2f} €**")

st.title("🛒 Asistente de compra")
st.caption("Busca productos reales en el catálogo de Mercadona")

col_categoria, col_subcategoria = st.columns(2)
mapa_taxonomia = cargar_mapa_categoria_subcategoria()

with col_categoria:
    categoria = st.selectbox(
        "Categoría",
        [""] + sorted(mapa_taxonomia),
        index=0,
    )

subcategorias_disponibles = (
    [""] + mapa_taxonomia[categoria]
    if categoria
    else [""]
)
with col_subcategoria:
    subcategoria = st.selectbox(
        "Subcategoría",
        subcategorias_disponibles,
        index=0,
    )

with st.form("busqueda_producto", clear_on_submit=False):
    producto = st.text_input(
        "Producto concreto",
        placeholder="Ej.: leche semidesnatada Hacendado 1 litro",
    )
    buscar = st.form_submit_button("Buscar", use_container_width=True)

if not st.session_state.mensajes:
    st.info("Elige categoría y subcategoría si quieres acotar la búsqueda.")

for mensaje in st.session_state.mensajes:
    with st.chat_message(
        mensaje["role"],
        avatar="🧑‍💼" if mensaje["role"] == "user" else "🛒",
    ):
        st.markdown(mensaje["content"])

texto = st.chat_input(
    "Elige una opción por su número"
    if st.session_state.opciones_pendientes
    else "¿Qué quieres comprar?"
)

if buscar:
    texto = producto.strip()
    st.session_state.categoria_seleccionada = categoria or None
    st.session_state.subcategoria_seleccionada = subcategoria or None
    if not texto:
        st.warning("Escribe el producto concreto que quieres buscar.")
        texto = None

if st.session_state.pendiente:
    texto = st.session_state.pendiente
    st.session_state.pendiente = None

if texto:
    st.session_state.mensajes.append({"role": "user", "content": texto})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(texto)

    with st.chat_message("assistant", avatar="🛒"):
        if st.session_state.opciones_pendientes:
            ids_opciones = tuple(
                opcion["option_id"]
                for opcion in st.session_state.opciones_pendientes
            )
            clave_seleccion = (texto.strip().casefold(), ids_opciones)
            seleccion = st.session_state.seleccion_cache.get(clave_seleccion)

            if seleccion is None:
                seleccion = intentar_seleccion_determinista(
                    texto,
                    st.session_state.opciones_pendientes,
                )
                if seleccion is None:
                    with st.spinner("Interpretando tu selección..."):
                        seleccion = interpretar_seleccion(
                            texto,
                            st.session_state.opciones_pendientes,
                        )
                st.session_state.seleccion_cache[clave_seleccion] = seleccion

            if seleccion.needs_clarification:
                respuesta = (
                    seleccion.clarification_question
                    or "¿Qué opción quieres y cuántas unidades?"
                )
                st.markdown(respuesta)
                st.session_state.mensajes.append({
                    "role": "assistant",
                    "content": respuesta,
                })
                st.stop()

            opciones_por_id = {
                opcion["option_id"]: opcion
                for opcion in st.session_state.opciones_pendientes
            }
            for linea in seleccion.selections:
                opcion = opciones_por_id[linea.option_id]
                producto = opcion["product"]
                cantidad = linea.sale_quantity
                cesta = st.session_state.cesta
                cesta[linea.option_id] = (
                    cesta.get(linea.option_id, 0) + cantidad
                )
                st.session_state.cesta = cesta
                st.session_state.opciones_por_id[linea.option_id] = opcion

            total = sumar_cesta(
                st.session_state.cesta,
                st.session_state.opciones_por_id,
            )
            lineas = []
            for linea in seleccion.selections:
                opcion = opciones_por_id[linea.option_id]
                producto = opcion["product"]
                subtotal = (
                    float(producto["precio"]) * linea.sale_quantity
                )
                lineas.append(
                    f"- {linea.sale_quantity} × {producto['nombre']} "
                    f"({producto['formato']}) | "
                    f"{producto['precio']:.2f} €/unidad | "
                    f"{subtotal:.2f} €"
                )
            respuesta = "\n".join(lineas)
            respuesta += f"\n\n**Total cesta: {total:.2f} €**"
            st.markdown(respuesta)
            st.session_state.mensajes.append({
                "role": "assistant",
                "content": respuesta,
            })
            st.session_state.opciones_pendientes = []
            st.session_state.categoria_seleccionada = None
            st.session_state.subcategoria_seleccionada = None
            st.stop()

        with st.spinner("Buscando opciones..."):
            try:
                resultado = app.invoke({
                    "peticion_usuario": texto,
                    "codigo_postal": "28012",
                    "categoria_seleccionada":
                        st.session_state.categoria_seleccionada,
                    "subcategoria_seleccionada":
                        st.session_state.subcategoria_seleccionada,
                })
                respuesta = resultado["respuesta_final"]
                st.markdown(respuesta)
                st.session_state.mensajes.append({
                    "role": "assistant",
                    "content": respuesta,
                })

                opciones = []
                for resultado_busqueda in resultado.get(
                    "productos_encontrados", []
                ):
                    opciones.extend(resultado_busqueda.get("options", []))
                st.session_state.opciones_pendientes = opciones
                st.session_state.seleccion_actual = None
            except Exception as error:
                st.error(f"No pude procesar la petición: {error}")
                st.session_state.mensajes.pop()
