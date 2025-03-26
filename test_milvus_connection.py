import os
import time
import random
import subprocess
from pymilvus import connections, utility
from dotenv import load_dotenv

def check_milvus_container_status():
    """Verifica el estado del contenedor de Milvus usando Docker."""
    try:
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
    """Verifica si un puerto está abierto y disponible."""
    import socket
    try:
        port = int(port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"Error al verificar disponibilidad del puerto {port}: {e}")
        return False

def test_milvus_connection():
    """Prueba la conexión con Milvus usando diferentes configuraciones."""
    print("\n===== PRUEBA DE CONEXIÓN A MILVUS =====\n")
    
    # Cargar variables de entorno
    load_dotenv()
    print("Variables de entorno cargadas")
    
    # Verificar estado del contenedor Docker
    container_status, container_message = check_milvus_container_status()
    print(f"Estado del contenedor Milvus: {container_message}")
    
    # Obtener configuración de .env
    main_host = os.getenv("MILVUS_HOST", "localhost")
    main_port = os.getenv("MILVUS_PORT", "19530")
    alternate_hosts = os.getenv("MILVUS_ALTERNATE_HOSTS", "").split(",")
    alternate_ports = os.getenv("MILVUS_ALTERNATE_PORTS", "").split(",")
    
    print(f"\nConfiguración en .env:")
    print(f"- Host principal: {main_host}")
    print(f"- Puerto principal: {main_port}")
    print(f"- Hosts alternativos: {alternate_hosts}")
    print(f"- Puertos alternativos: {alternate_ports}")
    
    # Verificar disponibilidad de puertos
    print("\nVerificando disponibilidad de endpoints:")
    hosts = [main_host] + [h for h in alternate_hosts if h and h.strip() and h != main_host]
    ports = [main_port] + [p for p in alternate_ports if p and p.strip() and p != main_port]
    
    available_endpoints = []
    for host in hosts:
        for port in ports:
            if check_port_availability(host, port):
                available_endpoints.append((host, port))
                print(f"✓ Endpoint disponible: {host}:{port}")
            else:
                print(f"✗ Endpoint no disponible: {host}:{port}")
    
    if not available_endpoints:
        print("\n⚠️ No se encontraron endpoints disponibles.")
        print("Verificando contenedores Docker...")
        try:
            result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
            print("\nContenedores en ejecución:")
            print(result.stdout)
        except Exception as e:
            print(f"Error al verificar contenedores Docker: {e}")
        return False
    
    # Intentar conexión con cada endpoint disponible
    print("\nIntentando conexión con endpoints disponibles:")
    max_retries = 3
    initial_backoff = 1.0
    
    for host, port in available_endpoints:
        for attempt in range(max_retries):
            try:
                # Desconectar si hay una conexión previa
                try:
                    connections.disconnect("default")
                except Exception:
                    pass
                
                print(f"\nIntento {attempt+1}/{max_retries} - Conectando a Milvus en {host}:{port}...")
                
                # Conectar a Milvus
                connections.connect(
                    alias="default",
                    host=host,
                    port=port,
                    timeout=10.0,
                    keepalive=True,
                    secure=False
                )
                
                # Verificar conexión listando colecciones
                collections = utility.list_collections()
                print(f"✓ Conexión exitosa a Milvus en {host}:{port}")
                print(f"Colecciones disponibles: {collections}")
                
                # Verificar estado del servicio
                try:
                    status = utility.get_server_version()
                    print(f"Versión del servidor Milvus: {status}")
                except Exception as e:
                    print(f"No se pudo obtener la versión del servidor: {e}")
                
                connections.disconnect("default")
                print("\n✅ PRUEBA COMPLETADA CON ÉXITO")
                return True
                
            except Exception as e:
                print(f"✗ Error al conectar a Milvus en {host}:{port}: {e}")
                
                if attempt < max_retries - 1:
                    backoff = initial_backoff * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Esperando {backoff:.2f} segundos antes del siguiente intento...")
                    time.sleep(backoff)
    
    print("\n❌ NO SE PUDO ESTABLECER CONEXIÓN CON MILVUS")
    print("Verificando estado de Docker...")
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
        print("\nContenedores en ejecución:")
        print(result.stdout)
    except Exception as e:
        print(f"Error al verificar contenedores Docker: {e}")
    
    return False

if __name__ == "__main__":
    test_milvus_connection()