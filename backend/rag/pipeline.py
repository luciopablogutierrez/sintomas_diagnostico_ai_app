from langchain.llms import HuggingFacePipeline
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Milvus
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os
from dotenv import load_dotenv

load_dotenv()

def setup_rag():
    """
    Configura el pipeline RAG con el modelo DeepSeek-R1 y la conexión a Milvus.
    
    Returns:
        tuple: (llm, embeddings, vector_db) - Componentes del pipeline RAG
    """
    # Modelo ligero en GPU si disponible
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Usando dispositivo: {device}")
    
    # Cargar solo lo necesario
    print("Cargando tokenizer y modelo DeepSeek-R1...")
    tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-R1")
    model = AutoModelForCausalLM.from_pretrained(
        "deepseek-ai/DeepSeek-R1",
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        token=os.getenv("HUGGINGFACE_API_TOKEN")
    ).to(device)
    
    # Pipeline eficiente
    print("Configurando pipeline de generación de texto...")
    llm = HuggingFacePipeline.from_model_id(
        model_id="deepseek-ai/DeepSeek-R1",
        task="text-generation",
        device=device,
        model_kwargs={"temperature": 0.2, "max_length": 512},
        token=os.getenv("HUGGINGFACE_API_TOKEN")
    )
    
    # Embeddings con cache
    print("Configurando modelo de embeddings...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    # Conexión reusable a Milvus
    print("Conectando a Milvus...")
    vector_db = Milvus(
        embedding_function=embeddings,
        connection_args={
            "host": os.getenv("MILVUS_HOST", "localhost"),
            "port": os.getenv("MILVUS_PORT", "19530")
        },
        collection_name="orphan_data"
    )
    
    return llm, embeddings, vector_db

def generate_diagnosis(llm, symptoms, context):
    """
    Genera un diagnóstico basado en los síntomas y el contexto médico.
    
    Args:
        llm: Modelo de lenguaje
        symptoms (str): Síntomas del paciente
        context (str): Contexto médico de enfermedades similares
        
    Returns:
        str: Diagnóstico generado
    """
    prompt_template = """
    Eres un asistente médico especializado en diagnóstico de enfermedades raras.
    Basándote en los síntomas proporcionados y la información de la base de datos ORPHA,
    genera un posible diagnóstico diferencial.
    
    SÍNTOMAS DEL PACIENTE:
    {symptoms}
    
    INFORMACIÓN DE ENFERMEDADES SIMILARES EN LA BASE DE DATOS:
    {context}
    
    Por favor, proporciona:
    1. Un análisis de los síntomas principales
    2. Posibles diagnósticos diferenciales ordenados por probabilidad
    3. Recomendaciones para pruebas diagnósticas adicionales
    4. Referencias a las enfermedades de la base de datos ORPHA que coinciden con el perfil
    
    DIAGNÓSTICO:
    """
    
    # Reemplazar variables en el prompt
    prompt = prompt_template.replace("{symptoms}", symptoms).replace("{context}", context)
    
    # Generar respuesta
    response = llm(prompt)
    
    return response

def search_similar_diseases(vector_db, embeddings, symptoms, limit=5):
    """
    Busca enfermedades similares basadas en los síntomas.
    
    Args:
        vector_db: Base de datos vectorial
        embeddings: Modelo de embeddings
        symptoms (str): Síntomas del paciente
        limit (int): Número máximo de resultados
        
    Returns:
        list: Lista de enfermedades similares
    """
    # Generar embedding para los síntomas
    query_embedding = embeddings.embed_query(symptoms)
    
    # Buscar documentos similares
    results = vector_db.similarity_search_by_vector(
        query_embedding,
        k=limit
    )
    
    return results