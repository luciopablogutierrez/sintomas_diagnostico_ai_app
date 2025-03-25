from lxml import etree
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
import xmltodict
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv
import torch
from sentence_transformers import SentenceTransformer

load_dotenv()

def process_xml():
    """
    Procesa el archivo XML de Orphanet y carga los datos en Milvus.
    
    Este script realiza las siguientes operaciones:
    1. Conecta con el servidor Milvus
    2. Parsea el archivo XML usando lxml
    3. Divide el contenido en chunks usando RecursiveCharacterTextSplitter
    4. Genera embeddings usando un modelo multilingüe de Sentence Transformers
    5. Crea una colección en Milvus e inserta los datos con sus embeddings
    6. Crea un índice FAISS para búsquedas eficientes
    
    Returns:
        bool: True si el procesamiento fue exitoso, False en caso de error
    """
    print("Iniciando procesamiento de XML a Milvus...")
    # Configuración Milvus
    # Establece conexión con el servidor Milvus usando credenciales de .env
    connections.connect(
        "default", 
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=os.getenv("MILVUS_PORT", "19530")
    )
    
    # Verificar si la colección existe
    collection_name = "orphan_data"
    # Verifica si la colección ya existe y la elimina si es necesario
    if utility.has_collection(collection_name):
        print(f"La colección '{collection_name}' ya existe, eliminándola para recrear...")
        utility.drop_collection(collection_name)
    
    # Parseo rápido con lxml
    xml_path = os.path.join(os.getcwd(), "ORPHAnomenclature_es_2024.xml")
    print(f"Parseando archivo XML: {xml_path}")
    # Parsea el archivo XML usando lxml para mejor rendimiento
    tree = etree.parse(xml_path)
    xml_data = xmltodict.parse(etree.tostring(tree))
    
    # Chunking optimizado
    print("Realizando chunking de datos...")
    # Crea un text splitter para dividir el contenido en chunks manejables
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=50,
        length_function=len,
        is_separator_regex=False
    )
    
    # Procesamiento paralelizable
    # Genera los chunks de texto a partir del XML parseado
    chunks = splitter.create_documents([str(xml_data)])
    print(f"Se generaron {len(chunks)} chunks de datos")
    
    # Definir esquema de colección
    print("Creando esquema de colección...")
    # Define el esquema de la colección Milvus
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768)
    ]
    
    schema = CollectionSchema(fields, "Orphanet data collection for medical diagnosis")
    collection = Collection(collection_name, schema)
    
    # Generar embeddings
    print("Generando embeddings...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Usando dispositivo: {device}")
    
    # Usar un modelo multilingüe para mejor rendimiento con texto en español
    # Carga el modelo multilingüe de Sentence Transformers para generar embeddings
    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    model.to(device)
    
    # Procesar chunks en lotes para evitar problemas de memoria
    batch_size = 32
    total_chunks = len(chunks)
    
    # Procesa los chunks en lotes para optimizar el uso de memoria
    for i in range(0, total_chunks, batch_size):
        end_idx = min(i + batch_size, total_chunks)
        batch_chunks = chunks[i:end_idx]
        
        print(f"Procesando lote {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size}...")
        
        # Generar embeddings para el lote
        texts = [chunk.page_content for chunk in batch_chunks]
        embeddings = model.encode(texts)
        
        # Preparar datos para inserción
        entities = [
            texts,
            embeddings.tolist()
        ]
        
        # Insertar datos
        collection.insert(entities)
    
    # Crear índice FAISS
    print("Creando índice FAISS...")
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 4096}
    }
    # Crea un índice FAISS para búsquedas vectoriales eficientes
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()
    
    # Verificar cantidad de entidades
    print(f"Importación completada. Entidades en la colección: {collection.num_entities}")
    return True

def main():
    """
    Función principal que ejecuta el proceso de ETL.
    
    Maneja excepciones y provee feedback sobre el éxito o fallo del proceso.
    
    Returns:
        bool: True si el proceso fue exitoso, False en caso de error
    """
    try:
        success = process_xml()
        return success
    except Exception as e:
        print(f"Error durante el procesamiento: {e}")
        return False

if __name__ == "__main__":
    main()