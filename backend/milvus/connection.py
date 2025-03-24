from pymilvus import connections, Collection, utility
import os
from dotenv import load_dotenv

load_dotenv()

def connect_to_milvus():
    """
    Establece conexión con el servidor Milvus y verifica su disponibilidad.
    
    Returns:
        bool: True si la conexión fue exitosa, False en caso contrario
    """
    try:
        print("Conectando a Milvus...")
        connections.connect(
            alias="default",
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=os.getenv("MILVUS_PORT", "19530"),
            timeout=10.0,
            keepalive_time=30,
            keepalive=True
        )
        
        # Verificar conexión listando colecciones
        collections = utility.list_collections()
        print(f"Conexión exitosa a Milvus. Colecciones disponibles: {collections}")
        return True
    except Exception as e:
        print(f"Error al conectar con Milvus: {e}")
        return False

def get_collection(collection_name="orphan_data"):
    """
    Obtiene una colección de Milvus por su nombre.
    
    Args:
        collection_name (str): Nombre de la colección a obtener
        
    Returns:
        Collection: Objeto de colección de Milvus o None si no existe
    """
    try:
        if not utility.has_collection(collection_name):
            print(f"La colección '{collection_name}' no existe")
            return None
        
        collection = Collection(collection_name)
        collection.load()
        return collection
    except Exception as e:
        print(f"Error al obtener la colección '{collection_name}': {e}")
        return None

def search_similar_vectors(collection, query_vector, limit=5, output_fields=None):
    """
    Busca vectores similares en una colección de Milvus.
    
    Args:
        collection (Collection): Colección de Milvus
        query_vector (list): Vector de consulta
        limit (int): Número máximo de resultados
        output_fields (list): Campos a incluir en los resultados
        
    Returns:
        list: Lista de resultados de búsqueda
    """
    try:
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10}
        }
        
        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            output_fields=output_fields if output_fields else ["text"]
        )
        
        return results
    except Exception as e:
        print(f"Error al realizar búsqueda en Milvus: {e}")
        return []