# Install FastAPI if not installed: pip install fastapi
try:
    from fastapi import FastAPI, HTTPException
except ImportError:
    raise ImportError("FastAPI is not installed. Please run: pip install fastapi")
from pydantic import BaseModel
from langchain_community.llms import HuggingFaceHub
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer
import os
import time
from dotenv import load_dotenv

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
                connections.connect(
                    alias="default", 
                    host=os.getenv("MILVUS_HOST", "localhost"),
                    port=os.getenv("MILVUS_PORT", "19530"),
                    timeout=10.0
                )
                break
            except Exception as e:
                print(f"Milvus connection attempt {attempt+1}/{max_attempts} failed: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5)
                else:
                    raise
        
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

@app.post("/diagnose")
async def diagnose(request: ChatRequest):
    # Check if components are initialized
    if not initialization_complete:
        if initialization_error:
            raise HTTPException(status_code=500, detail=f"Initialization failed: {str(initialization_error)}")
        raise HTTPException(status_code=503, detail="Service components not initialized")
    
    try:
        # Add except clause to handle potential errors
        # Generate embedding for the symptoms
        # Check if embedding_model is initialized before using it
        if embedding_model is None:
            raise HTTPException(status_code=500, detail="Embedding model not initialized")
        symptoms_embedding = embedding_model.encode(request.symptoms)
        
        # Search for similar diseases in Milvus
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10}
        }
        
        results = collection.search(
            data=[symptoms_embedding],
            anns_field="embedding",
            param=search_params,
            limit=5,
            output_fields=["code", "name", "symptoms", "description"]
        )
        
        # Extract the top matches
        matches = []
        hits = results[0]  # Access first (and only) result since we're searching with a single query
        for hit in hits:
            matches.append({
                "code": hit.entity.get('code'),
                "name": hit.entity.get('name'),
                "symptoms": hit.entity.get('symptoms'),
                "description": hit.entity.get('description'),
                "similarity": hit.distance
            })
        
        # Create a prompt for the LLM
        context = "\n".join([
            f"Enfermedad: {match['name']}\n"
            f"Síntomas: {match['symptoms']}\n"
            f"Descripción: {match['description']}\n"
            for match in matches
        ])
        
        prompt_template = PromptTemplate(
            input_variables=["symptoms", "context"],
            template="""
            Eres un asistente médico especializado en diagnósticos. 
            
            El paciente presenta los siguientes síntomas:
            {symptoms}
            
            Basado en la base de datos de enfermedades raras ORPHA, estas son las posibles coincidencias:
            {context}
            
            Por favor, proporciona un análisis detallado de los posibles diagnósticos, ordenados por probabilidad.
            Para cada diagnóstico, explica por qué los síntomas coinciden y qué pruebas adicionales podrían ser necesarias.
            """
        )
        
        # Create and run the chain
        chain = LLMChain(llm=llm, prompt=prompt_template)
        response = chain.run(symptoms=request.symptoms, context=context)
        
        return {
            "diagnosis": response,
            "matches": matches
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