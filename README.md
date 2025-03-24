# Asistente de Diagnóstico Médico

Esta aplicación proporciona una interfaz de chat intuitiva para médicos, donde pueden ingresar síntomas y recibir predicciones de diagnósticos basadas en la nomenclatura ORPHA de enfermedades raras.

## Requisitos previos

- Python 3.8 o superior
- Docker y Docker Compose
- Conexión a Internet

## Configuración

1. Clone este repositorio:

git clone
cd sintomas_diagnostico_ai_app


2. Configure las variables de entorno (opcional):
- Copie el archivo `.env.example` a `.env`
- Modifique las variables según sea necesario

## Ejecución

Para iniciar la aplicación completa, simplemente ejecute:

python run.py


Este script realizará automáticamente las siguientes acciones:
- Configurar el entorno virtual
- Instalar las dependencias
- Iniciar Milvus usando Docker Compose
- Importar los datos XML de ORPHA (si no se han importado previamente)
- Iniciar el servidor backend
- Iniciar la interfaz frontend de Streamlit
- Abrir la aplicación en su navegador

## Estructura del proyecto

sintomas_diagnostico_ai_app/
├── .env                  # Variables de entorno
├── requirements.txt      # Dependencias de Python
├── docker-compose.yml    # Configuración de Docker para Milvus
├── run.py                # Script para ejecutar la aplicación
├── README.md             # Este archivo
├── scripts/
│   └── data_importer.py  # Script para importar datos XML a Milvus
├── backend/
│   └── main.py           # API FastAPI para el backend
└── frontend/
└── app.py            # Interfaz de usuario con Streamlit


## Uso

1. Una vez que la aplicación esté en funcionamiento, acceda a la interfaz web en `http://localhost:8501`
2. Ingrese los síntomas del paciente en el campo de chat
3. El sistema analizará los síntomas y proporcionará posibles diagnósticos basados en la base de datos ORPHA
4. Los resultados incluirán diagnósticos probables, junto con información adicional sobre cada enfermedad

## Tecnologías utilizadas

- **Frontend**: Streamlit
- **Backend**: FastAPI, LangChain
- **Base de datos vectorial**: Milvus
- **Embeddings y RAG**: FAISS
- **Modelo de lenguaje**: DeepSeek-R1 (HuggingFace)

