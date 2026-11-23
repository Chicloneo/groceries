import streamlit as st

from proyecto_2.compras.graph import app


st.set_page_config(
    page_title="Asistente de compra",
    page_icon="🛒",
    layout="centered",
)

st.markdown(
    """
    <style>
    .stApp { background: #f6f5f1; }
    [data-testid="stChatMessage"] {
        background: white;
        border-radius: 14px;
        padding: 12px 16px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    }
    [data-testid="stSidebar"] { background: #1d1d1b; }
    [data-testid="stSidebar"] * { color: #f2f2f2; }
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

if not st.session_state.mensajes:
    st.info(
        "Escribe qué quieres comprar. Puedes indicar marca, variedad,"
        " cantidad y formato."
    )

for mensaje in st.session_state.mensajes:
    with st.chat_message(
        mensaje["role"],
        avatar="🧑‍💼" if mensaje["role"] == "user" else "🛒",
    ):
        st.markdown(mensaje["content"])

texto = st.chat_input("¿Qué quieres comprar?")
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
