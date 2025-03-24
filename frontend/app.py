# Importaciones necesarias para la interfaz de usuario
import streamlit as st      # Framework para la interfaz web
import requests             # Para realizar peticiones HTTP al backend
import json                 # Manejo de datos JSON
import os                   # Operaciones del sistema
from dotenv import load_dotenv  # Cargar variables de entorno

# Cargar configuración del entorno
load_dotenv()

# Configuración de la página web
st.set_page_config(
    page_title="Asistente de Diagnóstico Médico",  # Título de la pestaña del navegador
    page_icon="🏥",                               # Icono de la pestaña
    layout="wide"                                 # Layout expandido
)

# Estilos CSS personalizados para mejorar la apariencia de la interfaz
st.markdown("""
<style>
    .main {
        background-color: #f5f7f9;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
    }
    .chat-message.user {
        background-color: #e6f3ff;
    }
    .chat-message.bot {
        background-color: #f0f0f0;
    }
    .chat-message .avatar {
        width: 20%;
    }
    .chat-message .avatar img {
        max-width: 78px;
        max-height: 78px;
        border-radius: 50%;
        object-fit: cover;
    }
    .chat-message .message {
        width: 80%;
        padding: 0 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar el estado de la sesión para mantener el historial del chat
if "messages" not in st.session_state:
    st.session_state.messages = []  # Lista para almacenar mensajes del usuario y respuestas

# Título principal de la aplicación
st.title("Asistente de Diagnóstico Médico")
st.subheader("Basado en la nomenclatura ORPHA para enfermedades raras")

# Barra lateral con información adicional y controles
with st.sidebar:
    # Sección de información sobre el asistente
    st.header("Información")
    st.info("""
    Este asistente utiliza inteligencia artificial para ayudar a los médicos a identificar posibles diagnósticos
    basados en los síntomas del paciente. La información se obtiene de la base de datos ORPHA de enfermedades raras.
    
    **Nota**: Esta herramienta es solo un asistente y no reemplaza el juicio clínico profesional.
    """)
    
    # Control para limpiar el historial de consultas
    st.header("Historial de Consultas")
    if st.button("Limpiar historial"):
        st.session_state.messages = []  # Reiniciar el historial
        try:
            st.rerun()  # Actualizar la interfaz
        except Exception as e:
            print(f"Error en rerun: {e}")
            # Fallback para versiones anteriores de Streamlit
            st.experimental_rerun() if hasattr(st, 'experimental_rerun') else None

# Mostrar el historial de conversación
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])  # Renderizar mensajes con formato Markdown

# Campo de entrada para los síntomas
symptoms = st.chat_input("Describa los síntomas del paciente...")

# Procesar la entrada del usuario cuando se ingresa texto
if symptoms:
    # Agregar el mensaje del usuario al historial
    st.session_state.messages.append({"role": "user", "content": symptoms})
    
    # Mostrar el mensaje del usuario en la interfaz
    with st.chat_message("user"):
        st.markdown(symptoms)
    
    # Mostrar indicador de procesamiento
    with st.chat_message("assistant"):
        message_placeholder = st.empty()  # Espacio para la respuesta
        message_placeholder.markdown("🤔 Analizando síntomas...")
        
        try:
            # Enviar solicitud al backend para análisis
            response = requests.post(
                f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/diagnose",
                json={"symptoms": symptoms},
                timeout=60  # Tiempo máximo de espera
            )
            
            if response.status_code == 200:
                # Procesar respuesta exitosa
                result = response.json()
                diagnosis = result["diagnosis"]  # Diagnóstico general
                matches = result["matches"]    # Enfermedades coincidentes
                
                # Formatear la respuesta con diagnóstico y coincidencias
                formatted_response = f"{diagnosis}\n\n"
                formatted_response += "**Enfermedades relacionadas encontradas:**\n"
                
                # Mostrar las 3 mejores coincidencias con porcentaje de similitud
                for i, match in enumerate(matches[:3], 1):
                    formatted_response += f"**{i}. {match['name']} (Código ORPHA: {match['code']})**\n"
                    formatted_response += f"   Similitud: {100 - match['similarity']:.2f}%\n"
                
                # Actualizar el mensaje en la interfaz
                message_placeholder.markdown(formatted_response)
                
                # Agregar la respuesta al historial
                st.session_state.messages.append({"role": "assistant", "content": formatted_response})
            else:
                # Manejar error de respuesta del servidor
                error_msg = f"Error: {response.status_code} - {response.text}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
        
        except Exception as e:
            # Manejar errores de conexión
            error_msg = f"Error al conectar con el servidor: {str(e)}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})