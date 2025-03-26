import streamlit as st
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de la página
st.set_page_config(
    page_title="Chat Médico - Diagnóstico Predictivo",
    page_icon="🏥",
    layout="wide"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main { background-color: #f5f7f9; }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .chat-message.user {
        background-color: #e6f3ff;
    }
    .chat-message.bot {
        background-color: #f0f0f0;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.3rem;
    }
    .user-info {
        padding: 1rem;
        background-color: white;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Inicialización del estado de la sesión
def init_session_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_patient" not in st.session_state:
        st.session_state.current_patient = None

init_session_state()

# Función de autenticación
def authenticate(username, password):
    try:
        response = requests.post(
            f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/auth/login",
            json={"username": username, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.authenticated = True
            st.session_state.user_id = data["user_id"]
            st.session_state.user_name = username
            return True
        return False
    except Exception as e:
        st.error(f"Error de autenticación: {str(e)}")
        return False

# Pantalla de login
def show_login():
    st.title("🏥 Acceso al Chat Médico")
    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Iniciar Sesión")
        
        if submit:
            if authenticate(username, password):
                st.success("Autenticación exitosa")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

# Interfaz principal del chat
def show_chat_interface():
    # Barra lateral con información del usuario y paciente
    with st.sidebar:
        st.header(f"👋 Dr. {st.session_state.user_name}")
        
        # Selector de paciente
        st.subheader("🏥 Información del Paciente")
        patient_id = st.text_input("ID del Paciente")
        if st.button("Nueva Consulta"):
            if patient_id:
                st.session_state.current_patient = patient_id
                st.session_state.messages = []
                st.rerun()
        
        # Botón de cierre de sesión
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()
    
    # Área principal del chat
    st.title("Chat Médico - Diagnóstico Predictivo")
    
    if st.session_state.current_patient:
        st.info(f"📋 Consulta actual: Paciente ID {st.session_state.current_patient}")
        
        # Mostrar historial de mensajes
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Campo de entrada de síntomas
        symptoms = st.chat_input("Describa los síntomas del paciente...")
        
        if symptoms:
            # Agregar mensaje del usuario
            st.session_state.messages.append({"role": "user", "content": symptoms})
            with st.chat_message("user"):
                st.markdown(symptoms)
            
            # Procesar diagnóstico
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                message_placeholder.markdown("🤔 Analizando síntomas...")
                
                try:
                    response = requests.post(
                        f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/diagnose",
                        json={
                            "symptoms": symptoms,
                            "user_id": st.session_state.user_id,
                            "patient_id": st.session_state.current_patient
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        diagnosis = result["diagnosis"]
                        matches = result["matches"]
                        
                        formatted_response = f"{diagnosis}\n\n"
                        formatted_response += "**Enfermedades relacionadas encontradas:**\n"
                        
                        for i, match in enumerate(matches[:3], 1):
                            formatted_response += f"**{i}. {match['name']} (Código ORPHA: {match['code']})**\n"
                            formatted_response += f"   Similitud: {100 - match['similarity']:.2f}%\n"
                        
                        message_placeholder.markdown(formatted_response)
                        st.session_state.messages.append({"role": "assistant", "content": formatted_response})
                    else:
                        error_msg = f"Error: {response.status_code} - {response.text}"
                        message_placeholder.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                except Exception as e:
                    error_msg = f"Error al conectar con el servidor: {str(e)}"
                    message_placeholder.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
    else:
        st.warning("👆 Por favor, ingrese un ID de paciente para iniciar una nueva consulta")

# Flujo principal de la aplicación
if not st.session_state.authenticated:
    show_login()
else:
    show_chat_interface()