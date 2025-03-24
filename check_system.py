# Importaciones necesarias para el funcionamiento del sistema
import os            # Operaciones del sistema operativo
import sys          # Funcionalidades del sistema
import requests     # Realizar peticiones HTTP
import time         # Manejo de tiempo y delays
from dotenv import load_dotenv            # Cargar variables de entorno
from xml.etree import ElementTree as ET   # Procesamiento de archivos XML
from pymilvus import connections          # Conexión con la base de datos vectorial Milvus
from rich.console import Console          # Consola con formato enriquecido
from rich.table import Table              # Tablas con formato enriquecido

# Inicializar consola para salida formateada con colores y estilos
console = Console()

def check_env_variables():
    """Verificar variables de entorno requeridas para el funcionamiento del sistema.
    
    Esta función carga y verifica la presencia de todas las variables de entorno
    necesarias para el funcionamiento del sistema, incluyendo:
    - MILVUS_HOST: Host donde se ejecuta Milvus
    - MILVUS_PORT: Puerto de conexión de Milvus
    - BACKEND_URL: URL del servidor backend
    - HUGGINGFACEHUB_API_TOKEN: Token de autenticación para HuggingFace
    
    Returns:
        tuple: (bool, list) - Un booleano indicando si todas las variables están presentes
               y una lista de las variables faltantes si las hay
    """
    load_dotenv()
    required_vars = [
        'MILVUS_HOST',
        'MILVUS_PORT',
        'BACKEND_URL',
        'HUGGINGFACEHUB_API_TOKEN'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    return len(missing_vars) == 0, missing_vars

def check_xml_file():
    """Verificar existencia y validez del archivo XML de nomenclatura ORPHA.
    
    Esta función verifica:
    1. La existencia del archivo XML en el directorio del proyecto
    2. La validez del formato XML
    3. La presencia de enfermedades en el archivo
    
    El archivo XML contiene la nomenclatura ORPHA con información detallada
    sobre enfermedades raras, sus síntomas y clasificaciones.
    
    Returns:
        tuple: (bool, str) - Un booleano indicando si el archivo es válido
               y un mensaje describiendo el resultado o error
    """
    xml_path = 'ORPHAnomenclature_es_2024.xml'
    if not os.path.exists(xml_path):
        return False, "Archivo XML no encontrado"
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        return True, f"XML válido con {len(root.findall('.//Disorder'))} enfermedades"
    except ET.ParseError as e:
        return False, f"Error al parsear XML: {str(e)}"

def check_milvus_connection():
    """Verificar conexión con la base de datos vectorial Milvus.
    
    Milvus es una base de datos vectorial que se utiliza para almacenar y buscar
    vectores de características de las enfermedades y sus síntomas. Esta función
    intenta establecer una conexión con el servidor Milvus usando los parámetros
    configurados en las variables de entorno.
    
    Returns:
        tuple: (bool, str) - Un booleano indicando si la conexión fue exitosa
               y un mensaje describiendo el resultado o error
    """
    try:
        connections.connect(
            alias="default",
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=os.getenv("MILVUS_PORT", "19530")
        )
        return True, "Conexión exitosa"
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

def check_backend_status():
    """Verificar estado del servidor backend y su disponibilidad.
    
    El servidor backend es responsable de:
    1. Procesar las consultas de síntomas
    2. Interactuar con la base de datos Milvus
    3. Generar diagnósticos usando IA
    4. Gestionar la comunicación entre componentes
    
    Esta función verifica que el servidor esté en funcionamiento y responda
    correctamente a las peticiones de estado.
    
    Returns:
        tuple: (bool, dict/str) - Un booleano indicando si el servidor está activo
               y un diccionario con el estado o un mensaje de error
    """
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8000')
    try:
        response = requests.get(f"{backend_url}/status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            return True, status_data
        return False, f"Estado del servidor: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Error al conectar con el backend: {str(e)}"

def check_milvus_collection():
    """Verificar estado de la colección de vectores en Milvus.
    
    La colección en Milvus almacena:
    1. Vectores de características de enfermedades
    2. Metadatos asociados a cada enfermedad
    3. Índices para búsqueda eficiente
    
    Esta función verifica a través del backend:
    - La existencia de la colección
    - El número de registros almacenados
    - El estado del índice de búsqueda
    
    Returns:
        tuple: (bool, dict/str) - Un booleano indicando si la colección está disponible
               y un diccionario con estadísticas o un mensaje de error
    """
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8000')
    try:
        response = requests.get(f"{backend_url}/milvus-status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            return True, status_data
        return False, f"Error al obtener estado de la colección: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Error al verificar colección: {str(e)}"

def main():
    # Crear tabla de resultados
    table = Table(title="Estado del Sistema")
    table.add_column("Componente", style="cyan")
    table.add_column("Estado", style="green")
    table.add_column("Detalles", style="yellow")

    # Verificar variables de entorno
    env_status, missing_vars = check_env_variables()
    table.add_row(
        "Variables de Entorno",
        "✅ OK" if env_status else "❌ Error",
        "Todas las variables configuradas" if env_status else f"Faltantes: {', '.join(missing_vars)}"
    )

    # Verificar archivo XML
    xml_status, xml_details = check_xml_file()
    table.add_row(
        "Archivo XML",
        "✅ OK" if xml_status else "❌ Error",
        xml_details
    )

    # Verificar conexión Milvus
    milvus_status, milvus_details = check_milvus_connection()
    table.add_row(
        "Conexión Milvus",
        "✅ OK" if milvus_status else "❌ Error",
        milvus_details
    )

    # Verificar estado del backend
    backend_status, backend_details = check_backend_status()
    if backend_status:
        status = "✅ OK" if backend_details.get('initialization_complete') else "⏳ Inicializando"
        details = "Todos los componentes inicializados" if backend_details.get('initialization_complete') else "Componentes en inicialización"
    else:
        status = "❌ Error"
        details = str(backend_details)
    table.add_row("Servidor Backend", status, details)

    # Verificar colección Milvus
    if milvus_status:
        collection_status, collection_details = check_milvus_collection()
        if collection_status:
            status = "✅ OK"
            details = f"Registros: {collection_details.get('row_count', 0)}, Índice: {collection_details.get('index_status')}"
        else:
            status = "❌ Error"
            details = str(collection_details)
        table.add_row("Colección Milvus", status, details)

    # Mostrar resultados
    console.print(table)

    # Determinar estado general del sistema
    if not env_status or not xml_status or not milvus_status or not backend_status:
        console.print("\n[red]⚠️ Se encontraron errores en el sistema. Por favor, revise los detalles arriba.[/red]")
        sys.exit(1)
    else:
        console.print("\n[green]✅ Todos los sistemas funcionando correctamente.[/green]")

if __name__ == "__main__":
    main()