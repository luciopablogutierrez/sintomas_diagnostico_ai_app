from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_community.llms import HuggingFaceHub
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Initialize global variables
embedding_model = None
collection = None
llm = None

# Add a health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Initialize components
def initialize_components():
    global embedding_model, collection, llm
    
    try:
        print("Connecting to Milvus...")
        connections.connect(
            alias="default", 
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=os.getenv("MILVUS_PORT", "19530")
        )
        
        print("Loading disease collection...")
        collection = Collection("diseases")
        collection.load()
        
        print("Initializing embedding model...")
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("Initializing language model...")
        llm = HuggingFaceHub(
            repo_id="deepseek-ai/DeepSeek-R1",
            model_kwargs={"temperature": 0.5, "max_length": 512},
            huggingfacehub_api_token=os.getenv("HUGGINGFACE_API_TOKEN")
        )
        
        print("All components initialized successfully")
        return True
    except Exception as e:
        print(f"Error during initialization: {e}")
        return False

# Initialize on startup
initialize_components()

class ChatRequest(BaseModel):
    symptoms: str

@app.post("/diagnose")
async def diagnose(request: ChatRequest):
    # Check if components are initialized
    if embedding_model is None or collection is None or llm is None:
        # Try to initialize again
        if not initialize_components():
            raise HTTPException(status_code=503, detail="Service components not initialized")
    
    try:
        # Generate embedding for the symptoms
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
        for hits in results:
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)