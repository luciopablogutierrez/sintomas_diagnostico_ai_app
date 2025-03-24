import streamlit as st
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="Asistente de Diagnóstico Médico",
    page_icon="🏥",
    layout="wide"
)

# Custom CSS
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

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# App title
st.title("Asistente de Diagnóstico Médico")
st.subheader("Basado en la nomenclatura ORPHA para enfermedades raras")

# Sidebar for additional information
with st.sidebar:
    st.header("Información")
    st.info("""
    Este asistente utiliza inteligencia artificial para ayudar a los médicos a identificar posibles diagnósticos
    basados en los síntomas del paciente. La información se obtiene de la base de datos ORPHA de enfermedades raras.
    
    **Nota**: Esta herramienta es solo un asistente y no reemplaza el juicio clínico profesional.
    """)
    
    st.header("Historial de Consultas")
    if st.button("Limpiar historial"):
        st.session_state.messages = []
        try:
            st.rerun()
        except Exception as e:
            print(f"Error en rerun: {e}")
            st.experimental_rerun() if hasattr(st, 'experimental_rerun') else None

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
symptoms = st.chat_input("Describa los síntomas del paciente...")

if symptoms:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": symptoms})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(symptoms)
    
    # Display thinking indicator
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤔 Analizando síntomas...")
        
        try:
            # Send request to backend
            response = requests.post(
                f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/diagnose",
                json={"symptoms": symptoms},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                diagnosis = result["diagnosis"]
                matches = result["matches"]
                
                # Format the response
                formatted_response = f"{diagnosis}\n\n"
                formatted_response += "**Enfermedades relacionadas encontradas:**\n"
                
                for i, match in enumerate(matches[:3], 1):
                    formatted_response += f"**{i}. {match['name']} (Código ORPHA: {match['code']})**\n"
                    formatted_response += f"   Similitud: {100 - match['similarity']:.2f}%\n"
                
                # Update the message
                message_placeholder.markdown(formatted_response)
                
                # Add assistant message to chat history
                st.session_state.messages.append({"role": "assistant", "content": formatted_response})
            else:
                error_msg = f"Error: {response.status_code} - {response.text}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
        
        except Exception as e:
            error_msg = f"Error al conectar con el servidor: {str(e)}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})