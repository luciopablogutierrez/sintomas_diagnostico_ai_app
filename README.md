# Asistente de Diagnóstico Médico (Chat Médico con Diagnóstico Predictivo)

## Objetivo Principal

Crear una aplicación de chat intuitiva para doctores que ingrese síntomas y prediga diagnósticos basados en datos de ORPHAnomenclature (importados a Milvus), usando el stack especificado con máxima eficiencia.

## Stack Tecnológico Específico
```
Frontend: Next.js + Streamlit (UI)
Embeddings: FAISS (índices eficientes)
Backend/Model: LangChain (orquestación)
Vector DB: Milvus (almacenamiento/retrieval)
LLM: deepseek-ai/DeepSeek-R1 (HuggingFace)
```

## Requisitos previos

- Python 3.8 o superior
- Docker y Docker Compose
- Conexión a Internet

## Configuración

1. Clone este repositorio:

```bash
git clone
cd sintomas_diagnostico_ai_app
```

2. Configure las variables de entorno (opcional):
- Copie el archivo `.env.example` a `.env`
- Modifique las variables según sea necesario

## Ejecución

Para iniciar la aplicación completa, simplemente ejecute:

```bash
python run.py
```

Este script realizará automáticamente las siguientes acciones:
- Configurar el entorno virtual
- Instalar las dependencias
- Iniciar Milvus usando Docker Compose
- Importar los datos XML de ORPHA (si no se han importado previamente)
- Iniciar el servidor backend
- Iniciar la interfaz frontend de Streamlit
- Abrir la aplicación en su navegador

## Estructura del proyecto

```
sintomas_diagnostico_ai_app/
├── .env                      # Variables de entorno
├── .env.example             # Ejemplo de variables de entorno
├── requirements.txt         # Dependencias de Python
├── docker-compose.yml       # Configuración de Docker para Milvus
├── run.py                   # Script para ejecutar la aplicación
├── README.md                # Este archivo
├── ORPHAnomenclature_es_2024.xml  # Datos de enfermedades raras
├── scripts/
│   └── data_importer.py     # Script para importar datos XML a Milvus
├── backend/
│   ├── etl/                 # Scripts ETL
│   │   └── xml_to_milvus.py # Procesamiento de XML a Milvus
│   ├── milvus/              # Conexión a la base de datos
│   │   └── connection.py    # Configuración de conexión a Milvus
│   ├── rag/                 # Pipeline RAG
│   │   └── pipeline.py      # Configuración del pipeline RAG
│   ├── main.py              # API FastAPI para el backend
│   └── requirements.txt     # Dependencias específicas del backend
└── frontend/
    ├── app.py               # Interfaz principal
    ├── next-app/            # Aplicación Next.js
    │   └── pages/           # Páginas de la aplicación Next.js
    └── streamlit-admin/     # Interfaz de administración
        └── app.py           # Aplicación Streamlit para administración
```

## Flujo de Procesamiento

1. **Procesamiento de Datos**:
   - Carga del XML → Parseo → Chunking (512 tokens)
   - Generación de embeddings (DeepSeek-R1) → Almacenamiento en Milvus (índice FAISS)

2. **Pipeline RAG**:
   - Input de síntomas → Embedding → Búsqueda por similitud (FAISS)
   - Top 5 resultados → Prompt engineering → DeepSeek-R1
   - Formateo de respuesta (Markdown + evidencias)

## Uso

1. Una vez que la aplicación esté en funcionamiento, acceda a la interfaz web en `http://localhost:8501`
2. Ingrese los síntomas del paciente en el campo de chat
3. El sistema analizará los síntomas y proporcionará posibles diagnósticos basados en la base de datos ORPHA
4. Los resultados incluirán diagnósticos probables, junto con información adicional sobre cada enfermedad

## Optimizaciones de Rendimiento

1. **Caching Estratégico**:
   - Caché de embeddings generados
   - Pre-cálculo de embeddings para términos médicos comunes

2. **Optimización de Milvus**:
   - Configuración de índices FAISS optimizados
   - Parámetros ajustados para búsqueda eficiente

3. **Load Balancing**:
   - Procesamiento por lotes en peticiones al LLM
   - Implementación de async/await en el frontend

## Tecnologías utilizadas

- **Frontend**: Next.js, Streamlit
- **Backend**: FastAPI, LangChain
- **Base de datos vectorial**: Milvus
- **Embeddings y RAG**: FAISS
- **Modelo de lenguaje**: DeepSeek-R1 (HuggingFace)
- **Procesamiento de datos**: lxml, xmltodict






**Ejemplo para QA

El síndrome de Guillain-Barré-Strohl (SLGBS), también conocido como síndrome de Guillain-Barré (GB), es una enfermedad que afecta el sistema nervioso periférico. 
Síntomas 

Hormigueo en los pies, las piernas, los brazos o la cara
Debilidad muscular que progresa a parálisis
Dificultad para caminar o subir escaleras
Dificultad para mover los ojos
Dolor fuerte
Problemas para controlar la vejiga o los intestinos
Frecuencia cardíaca acelerada
Presión arterial alta o baja
Problemas para respirar

Tratamiento Inmunoglobulinas por vía intravenosa (IgIV), Plasmaféresis, Fisioterapia y rehabilitación. 

Pronóstico 
El pronóstico varía según el tipo de SGB y puede ir desde la recuperación completa hasta la incapacidad de caminar

Factores de riesgo
Se desconoce la causa exacta, pero suele ocurrir después de una infección viral respiratoria o gastrointestinal 
También se han descrito casos de SGB ocurridos después de una vacunación o una intervención quirúrgica 

Frecuencia 
Se estima que una persona de cada 100,000 la presenta