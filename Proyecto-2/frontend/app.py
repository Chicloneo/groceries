import streamlit as st

from proyecto_2.clasificador.categorias import CATEGORIAS, SUBCATEGORIAS
from proyecto_2.compras.graph import app


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

with st.sidebar:
    st.markdown("### Prueba con...")
    for index, ejemplo in enumerate(EJEMPLOS):
        if st.button(ejemplo, key=f"ejemplo-{index}", use_container_width=True):
            st.session_state.pendiente = ejemplo
    st.markdown("---")
    if st.button("Nueva conversación", use_container_width=True):
        st.session_state.mensajes = []
        st.session_state.pendiente = None
        st.rerun()

st.title("🛒 Asistente de compra")
st.caption("Busca productos reales en el catálogo de Mercadona")

col_categoria, col_subcategoria = st.columns(2)
with col_categoria:
    categoria = st.selectbox(
        "Categoría",
        [""] + CATEGORIAS,
        index=0,
    )
with col_subcategoria:
    subcategoria = st.selectbox(
        "Subcategoría",
        [""] + SUBCATEGORIAS,
        index=0,
    )

producto = st.text_input(
    "Producto concreto",
    placeholder="Ej.: leche semidesnatada Hacendado 1 litro",
)

buscar = st.button("Buscar", use_container_width=True)

if not st.session_state.mensajes:
    st.info("Elige categoría y subcategoría si quieres acotar la búsqueda.")

for mensaje in st.session_state.mensajes:
    with st.chat_message(
        mensaje["role"],
        avatar="🧑‍💼" if mensaje["role"] == "user" else "🛒",
    ):
        st.markdown(mensaje["content"])

texto = None
if buscar:
    partes = []
    if categoria:
        partes.append(categoria)
    if subcategoria:
        partes.append(subcategoria)
    if producto.strip():
        partes.append(producto.strip())
    if partes:
        texto = " ".join(partes)

if st.session_state.pendiente:
    texto = st.session_state.pendiente
    st.session_state.pendiente = None

if texto:
    st.session_state.mensajes.append({"role": "user", "content": texto})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(texto)

    with st.chat_message("assistant", avatar="🛒"):
        with st.spinner("Buscando opciones..."):
            try:
                resultado = app.invoke({
                    "peticion_usuario": texto,
                    "codigo_postal": "28012",
                })
                respuesta = resultado["respuesta_final"]
                st.markdown(respuesta)
                st.session_state.mensajes.append({
                    "role": "assistant",
                    "content": respuesta,
                })
            except Exception as error:
                st.error(f"No pude procesar la petición: {error}")
                st.session_state.mensajes.pop()
