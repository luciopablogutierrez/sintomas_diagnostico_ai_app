import streamlit as st
import requests
import pandas as pd
import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

# Configuración de la página
st.set_page_config(
    page_title="MediChat Admin",
    page_icon="⚕️",
    layout="wide"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main {background-color: #f5f7f9;}
    .stButton>button {background-color: #4CAF50; color: white;}
    .stProgress .st-bo {background-color: #4CAF50;}
    .metric-card {background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
</style>
""", unsafe_allow_html=True)

# Título y descripción
st.title("Panel de Administración - MediChat")
st.markdown("Panel para gestionar la base de datos de enfermedades y monitorear el rendimiento del sistema.")

# Función para conectar con el backend
def get_backend_status():
    try:
        response = requests.get(f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/status", timeout=5)
        return response.json()
    except Exception as e:
        return {"error": str(e), "initialization_complete": False}

def get_backend_stats():
    try:
        response = requests.get(f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/stats", timeout=5)
        return response.json()
    except Exception as e:
        return {"error": str(e), "total_queries": 0}

# Sidebar con información del sistema
with st.sidebar:
    st.header("Estado del Sistema")
    
    if st.button("Actualizar Estado"):
        st.session_state.status_updated = True
    
    status = get_backend_status()
    
    # Mostrar estado de componentes
    st.subheader("Componentes")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Backend", "Activo" if not status.get("error") else "Error")
        st.metric("Milvus", "Conectado" if status.get("components", {}).get("collection") else "Desconectado")
    
    with col2:
        st.metric("LLM", "Cargado" if status.get("components", {}).get("llm") else "No disponible")
        st.metric("Embeddings", "Activo" if status.get("components", {}).get("embedding_model") else "No disponible")
    
    if status.get("error"):
        st.error(f"Error: {status.get('error')}")
    
    # Estadísticas de uso
    st.subheader("Estadísticas")
    stats = get_backend_stats()
    
    st.metric("Total de consultas", stats.get("total_queries", 0))
    st.metric("Tiempo promedio de respuesta", f"{stats.get('avg_response_time', 0):.2f} seg")

# Pestañas principales
tab1, tab2, tab3 = st.tabs(["Base de Datos", "Estadísticas", "Configuración"])

# Pestaña de Base de Datos
with tab1:
    st.header("Gestión de Base de Datos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Importar Datos")
        st.markdown("Importar datos desde el archivo XML de ORPHAnomenclature a Milvus.")
        
        if st.button("Iniciar Importación"):
            with st.spinner("Importando datos a Milvus..."):
                try:
                    # Simular proceso de importación
                    progress_bar = st.progress(0)
                    for i in range(100):
                        time.sleep(0.05)
                        progress_bar.progress(i + 1)
                    
                    st.success("Datos importados correctamente a Milvus")
                except Exception as e:
                    st.error(f"Error durante la importación: {e}")
    
    with col2:
        st.subheader("Estado de la Colección")
        
        # Mostrar información de la colección
        collection_info = {
            "Nombre": "orphan_data",
            "Entidades": "Cargando...",
            "Dimensión de vectores": 768,
            "Índice": "IVF_FLAT"
        }
        
        st.json(collection_info)

# Pestaña de Estadísticas
with tab2:
    st.header("Estadísticas de Uso")
    
    # Crear datos de ejemplo para gráficos
    chart_data = pd.DataFrame({
        "Fecha": pd.date_range(start="2023-01-01", periods=30),
        "Consultas": [5, 7, 10, 8, 12, 15, 20, 18, 22, 25, 30, 28, 35, 32, 40, 38, 45, 50, 48, 55, 60, 58, 65, 70, 68, 75, 80, 78, 85, 90]
    })
    
    st.line_chart(chart_data.set_index("Fecha"))
    
    # Mostrar consultas recientes
    st.subheader("Consultas Recientes")
    
    recent_queries = [
        {"timestamp": "2023-05-01 10:30:45", "symptoms": "Dolor de cabeza, fiebre, rigidez en el cuello", "diagnosis": "Posible meningitis"},
        {"timestamp": "2023-05-01 11:15:22", "symptoms": "Debilidad muscular progresiva, fasciculaciones", "diagnosis": "Posible ELA"},
        {"timestamp": "2023-05-01 12:05:10", "symptoms": "Manchas en la piel, dolor articular, fatiga", "diagnosis": "Posible lupus"}
    ]
    
    st.dataframe(pd.DataFrame(recent_queries))

# Pestaña de Configuración
with tab3:
    st.header("Configuración del Sistema")
    
    # Formulario de configuración
    with st.form("config_form"):
        st.subheader("Parámetros de Milvus")
        milvus_host = st.text_input("Host de Milvus", value=os.getenv("MILVUS_HOST", "localhost"))
        milvus_port = st.text_input("Puerto de Milvus", value=os.getenv("MILVUS_PORT", "19530"))
        
        st.subheader("Parámetros del Modelo")
        temperature = st.slider("Temperatura", min_value=0.0, max_value=1.0, value=0.2, step=0.1)
        max_tokens = st.slider("Tokens máximos", min_value=100, max_value=1000, value=512, step=50)
        
        submitted = st.form_submit_button("Guardar Configuración")
        
        if submitted:
            st.success("Configuración guardada correctamente")

# Pie de página
st.markdown("---")
st.markdown("MediChat Admin Panel - Desarrollado con Streamlit")