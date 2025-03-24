from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer
import os
import time
import logging
import sys
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("medichat")

load_dotenv()

app = FastAPI()

# Initialize global variables
embedding_model = None
collection = None
llm = None
initialization_complete = False
initialization_error = None

# Add a health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "initialization": "complete" if initialization_complete else "in_progress"}

# Add a status endpoint to check component initialization
@app.get("/status")
async def status():
    return {
        "initialization_complete": initialization_complete,
        "error": str(initialization_error) if initialization_error else None,
        "components": {
            "embedding_model": embedding_model is not None,
            "collection": collection is not None,
            "llm": llm is not None
        }
    }

# Initialize components
def initialize_components():
    global embedding_model, collection, llm, initialization_complete, initialization_error
    
    try:
        print("Connecting to Milvus...")
        # Retry Milvus connection with backoff
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                try:
                    connections.disconnect("default")
                except:
                    pass
                connections.connect(
                    alias="default",
                    host=os.getenv("MILVUS_HOST", "localhost"),
                    port=os.getenv("MILVUS_PORT", "19530"),
                    timeout=10.0,
                    keepalive_time=30,
                    keepalive=True
                )
                break
            except Exception as e:
                print(f"Milvus connection attempt {attempt+1}/{max_attempts} failed: {e}")
                if "server ID mismatch" in str(e):
                    print("Resetting connection due to server ID mismatch...")
                    try:
                        connections.remove_connection("default")
                    except:
                        pass
                if attempt < max_attempts - 1:
                    time.sleep(5 + attempt*2)
                else:
                    raise RuntimeError("Failed to establish stable connection to Milvus after retries")
        
        print("Loading disease collection...")
        try:
            # Check if collection exists
            collection = Collection("diseases")
            print("Collection exists, checking index...")
        except Exception as e:
            print(f"Collection does not exist: {e}")
            from pymilvus import FieldSchema, CollectionSchema, DataType
            
            # Define fields for the collection
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="code", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="symptoms", dtype=DataType.VARCHAR, max_length=10000),
                FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=10000),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768)
            ]
            
            # Create collection schema
            schema = CollectionSchema(fields, "Disease collection for medical diagnosis")
            collection = Collection("diseases", schema)
            print("Collection created successfully")
        
        # Create index if it doesn't exist
        try:
            # Drop any existing index first to ensure clean state
            try:
                collection.drop_index()
                print("Dropped existing index")
            except Exception:
                print("No existing index to drop")
            
            print("Creating new index...")
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            print("Index created successfully")
            
            collection.load()
            print("Collection loaded successfully")
        except Exception as e:
            print(f"Error with collection indexing: {e}")
            raise
        
        print("Initializing embedding model...")
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("Initializing language model...")
        llm = HuggingFaceHub(
            repo_id="deepseek-ai/DeepSeek-R1",
            model_kwargs={"temperature": 0.5, "max_length": 512},
            huggingfacehub_api_token=os.getenv("HUGGINGFACE_API_TOKEN")
        )
        
        initialization_complete = True
        print("All components initialized successfully")
    except Exception as e:
        initialization_error = e
        print(f"Error during initialization: {e}")
        # Don't raise the exception, just log it
        # This allows the server to continue running

# Start initialization in background
import threading
threading.Thread(target=initialize_components, daemon=True).start()

class ChatRequest(BaseModel):
    symptoms: str

# Importar módulos necesarios para el pipeline RAG
from backend.rag.pipeline import generate_diagnosis, search_similar_diseases
import time

@app.post("/diagnose")
async def diagnose(request: ChatRequest):
    # Check if components are initialized
    if not initialization_complete:
        if initialization_error:
            raise HTTPException(status_code=500, detail=f"Initialization failed: {str(initialization_error)}")
        raise HTTPException(status_code=503, detail="Service components not initialized")
    
    # Registrar estadísticas
    start_time = time.time()
    
    try:
        # Importar módulos de RAG
        from backend.rag.pipeline import setup_rag
        from backend.milvus.connection import get_collection
        
        # Verificar componentes
        if llm is None or embeddings is None or vector_db is None:
            logger.error("Componentes RAG no inicializados")
            raise HTTPException(status_code=500, detail="Componentes RAG no inicializados")
        
        logger.info(f"Procesando síntomas: {request.symptoms}")
        
        # Buscar enfermedades similares
        similar_diseases = search_similar_diseases(vector_db, embeddings, request.symptoms, limit=5)
        
        # Preparar contexto para el LLM
        context = "\n\n".join([doc.page_content for doc in similar_diseases])
        
        # Generar diagnóstico
        diagnosis = generate_diagnosis(llm, request.symptoms, context)
        
        # Extraer información de las enfermedades similares
        matches = []
        for i, doc in enumerate(similar_diseases):
            # Extraer información del documento
            text = doc.page_content
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            
            # Crear objeto de coincidencia
            match = {
                "id": i + 1,
                "text": text,
                "similarity": metadata.get('score', 100 - i*10)  # Valor aproximado si no hay score real
            }
            
            # Intentar extraer más información si está disponible
            if 'code' in metadata:
                match['code'] = metadata['code']
            if 'name' in metadata:
                match['name'] = metadata['name']
            
            matches.append(match)
        
        # Registrar estadísticas
        end_time = time.time()
        response_time = end_time - start_time
        
        # Actualizar estadísticas globales
        global query_stats
        query_stats["total_queries"] += 1
        query_stats["query_history"].append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "symptoms": request.symptoms,
            "response_time": response_time
        })
        
        # Limitar historial a las últimas 100 consultas
        if len(query_stats["query_history"]) > 100:
            query_stats["query_history"] = query_stats["query_history"][-100:]
        
        # Calcular tiempo promedio de respuesta
        total_times = sum(q["response_time"] for q in query_stats["query_history"])
        query_stats["avg_response_time"] = total_times / len(query_stats["query_history"])
        
        logger.info(f"Diagnóstico generado en {response_time:.2f} segundos")
        
        # Devolver respuesta formateada
        return {
            "diagnosis": diagnosis,
            "matches": matches,
            "response_time": response_time
        }
    except Exception as e:
        print(f"Error in diagnose endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add this near the other endpoint definitions
@app.get("/milvus-status")
async def milvus_status():
    """Get Milvus collection statistics and status."""
    if not initialization_complete:
        if initialization_error:
            raise HTTPException(status_code=500, detail=f"Initialization failed: {str(initialization_error)}")
        raise HTTPException(status_code=503, detail="Service components not initialized")
    
    try:
        stats = collection.get_stats()
        return {
            "status": "ok",
            "collection_name": collection.name,
            "row_count": stats.get("row_count", 0),
            "index_status": "created" if collection.index() else "not created",
            "loaded": collection.is_loaded
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting Milvus status: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint that provides API information and available endpoints."""
    return {
        "app": "Síntomas Diagnóstico AI API",
        "status": "running",
        "initialization": "complete" if initialization_complete else "in_progress",
        "available_endpoints": [
            {"path": "/", "method": "GET", "description": "This information page"},
            {"path": "/health", "method": "GET", "description": "Health check endpoint"},
            {"path": "/status", "method": "GET", "description": "Component initialization status"},
            {"path": "/milvus-status", "method": "GET", "description": "Milvus collection statistics"},
            {"path": "/diagnose", "method": "POST", "description": "Submit symptoms for diagnosis"}
        ],
        "documentation": [
            {"path": "/docs", "description": "Swagger UI API documentation"},
            {"path": "/redoc", "description": "ReDoc API documentation"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)