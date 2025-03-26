from pymilvus import connections, Collection, utility
import os
import time
import random
import socket
import subprocess
from dotenv import load_dotenv

load_dotenv()

def check_milvus_container_status():
    """
    Verifica el estado del contenedor de Milvus usando Docker.
    
    Returns:
        tuple: (bool, str) - Estado del contenedor y mensaje descriptivo
    """
    try:
        # Verificar si el contenedor está en ejecución
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=milvus", "--format", "{{.Status}}"],
            capture_output=True, text=True, check=True
        )
        
        if "Up" in result.stdout:
            return True, f"Contenedor en ejecución: {result.stdout.strip()}"
        elif result.stdout.strip():
            return False, f"Contenedor no está activo: {result.stdout.strip()}"
        else:
            return False, "Contenedor no encontrado"
            
    except subprocess.CalledProcessError as e:
        return False, f"Error al verificar estado del contenedor: {e}"
    except Exception as e:
        return False, f"Error inesperado: {e}"

def check_port_availability(host, port):
    """
    Verifica si un puerto está abierto y disponible en el host especificado.
    
    Args:
        host (str): Dirección del host
        port (str): Puerto a verificar
    
    Returns:
        bool: True si el puerto está disponible, False en caso contrario
    """
    try:
        # Convertir puerto a entero
        port = int(port)
        
        # Crear socket y probar conexión
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)  # Timeout corto para prueba rápida
        result = sock.connect_ex((host, port))
        sock.close()
        
        # Si result es 0, la conexión fue exitosa (puerto abierto)
        return result == 0
    except Exception as e:
        print(f"Error al verificar disponibilidad del puerto {port}: {e}")
        return False

def connect_to_milvus(max_retries=5, initial_backoff=1.0, max_backoff=60.0):
    """
    Establece conexión con el servidor Milvus y verifica su disponibilidad.
    Implementa un mecanismo de reintentos con espera exponencial.
    
    Args:
        max_retries (int): Número máximo de intentos de conexión
        initial_backoff (float): Tiempo inicial de espera entre reintentos en segundos
        
    Returns:
        bool: True si la conexión fue exitosa, False en caso contrario
    """
    print("Conectando a Milvus...")
    
    # Verificar estado del contenedor Docker
    container_status, container_message = check_milvus_container_status()
    if not container_status:
        print(f"Advertencia: {container_message}")
        print("Intentando conexión de todos modos...")
    else:
        print(f"Contenedor Milvus: {container_message}")
    
    # Obtener puertos alternativos
    alternate_ports = os.getenv("MILVUS_ALTERNATE_PORTS", "").split(",")
    if alternate_ports == [""]:  # Si no hay puertos alternativos
        # Usar puertos comunes de Milvus como alternativas
        alternate_ports = ["19121", "19530", "19531", "19532"]
    
    # Asegurar que el puerto principal esté primero y eliminar duplicados
    main_port = os.getenv("MILVUS_PORT", "19530")
    ports = [main_port]
    for port in alternate_ports:
        if port and port.strip() and port != main_port:
            ports.append(port.strip())
    
    # Obtener hosts alternativos
    alternate_hosts = os.getenv("MILVUS_ALTERNATE_HOSTS", "").split(",")
    if alternate_hosts == [""]:  # Si no hay hosts alternativos
        # Usar hosts comunes como alternativas
        alternate_hosts = ["milvus", "127.0.0.1"]
    
    # Asegurar que el host principal esté primero y eliminar duplicados
    main_host = os.getenv("MILVUS_HOST", "localhost")
    hosts = [main_host]
    for host in alternate_hosts:
        if host and host.strip() and host != main_host:
            hosts.append(host.strip())
    
    # Verificar disponibilidad de puertos
    available_endpoints = []
    for host in hosts:
        for port in ports:
            if check_port_availability(host, port):
                available_endpoints.append((host, port))
                print(f"Endpoint disponible: {host}:{port}")
    
    # Si no hay endpoints disponibles, usar todos los posibles
    if not available_endpoints:
        print("No se encontraron endpoints disponibles. Intentando con todas las combinaciones...")
        available_endpoints = [(host, port) for host in hosts for port in ports]
    
    # Intentar conectar con cada combinación de host/puerto
    for host, port in available_endpoints:
        # Implementar reintentos con backoff exponencial
        for attempt in range(max_retries):
            try:
                # Desconectar si hay una conexión previa
                try:
                    connections.disconnect("default")
                except Exception:
                    pass
                
                print(f"Intento {attempt+1}/{max_retries} - Conectando a Milvus en {host}:{port}...")
                
                # Parámetros de conexión con valores más robustos
                timeout_value = min(10.0 + (attempt * 5.0), 30.0)  # Limitar timeout máximo a 30 segundos
                connections.connect(
                    alias="default",
                    host=host,
                    port=port,
                    timeout=timeout_value,
                    keepalive_time=60,  # Aumentar keepalive_time para conexiones más estables
                    keepalive=True,
                    secure=False  # Explícitamente desactivar SSL para evitar problemas de certificados
                )
                
                # Verificar conexión listando colecciones
                collections = utility.list_collections()
                print(f"Conexión exitosa a Milvus en {host}:{port}. Colecciones disponibles: {collections}")
                return True
                
            except Exception as e:
                print(f"Intento {attempt+1}/{max_retries} - Error al conectar a Milvus en {host}:{port}: {e}")
                
                # Si es el último intento con este puerto, probar con el siguiente puerto
                if attempt == max_retries - 1:
                    print(f"Agotados los intentos para el puerto {port}")
                    break
                
                # Calcular tiempo de espera con jitter para evitar tormentas de conexión
                # Limitar el backoff máximo para evitar esperas excesivas
                backoff = min(initial_backoff * (2 ** attempt) + random.uniform(0, 1), max_backoff)
                print(f"Esperando {backoff:.2f} segundos antes del siguiente intento...")
                time.sleep(backoff)
    
    print("No se pudo establecer conexión con Milvus después de agotar todos los puertos e intentos")
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