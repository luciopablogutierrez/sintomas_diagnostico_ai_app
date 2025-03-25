# Importaciones necesarias para el funcionamiento del sistema
import os            # Operaciones del sistema operativo
import sys          # Funcionalidades del sistema
import requests     # Realizar peticiones HTTP
import time         # Manejo de tiempo y delays
import random       # Para implementar espera exponencial
from dotenv import load_dotenv            # Cargar variables de entorno
from xml.etree import ElementTree as ET   # Procesamiento de archivos XML
from pymilvus import connections          # Conexión con la base de datos vectorial Milvus
from rich.console import Console          # Consola con formato enriquecido
from rich.table import Table              # Tablas con formato enriquecido
from rich.progress import Progress        # Barra de progreso para reintentos

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

def check_milvus_connection(retry=False):
    """Verificar conexión con la base de datos vectorial Milvus.
    
    Milvus es una base de datos vectorial que se utiliza para almacenar y buscar
    vectores de características de las enfermedades y sus síntomas. Esta función
    intenta establecer una conexión con el servidor Milvus usando los parámetros
    configurados en las variables de entorno.
    
    Args:
        retry (bool): Indica si es un reintento de conexión
    
    Returns:
        tuple: (bool, str) - Un booleano indicando si la conexión fue exitosa
               y un mensaje describiendo el resultado o error
    """
    try:
        # Intentar desconectar primero si es un reintento para evitar errores de conexión duplicada
        if retry:
            try:
                connections.disconnect("default")
            except:
                pass  # Ignorar errores si no hay conexión previa
        
        # Intentar conectar con timeout aumentado en reintentos
        timeout = 15.0 if retry else 5.0
        connections.connect(
            alias="default",
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=os.getenv("MILVUS_PORT", "19530"),
            timeout=timeout
        )
        return True, "Conexión exitosa"
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

def check_backend_status(retry=False):
    """Verificar estado del servidor backend y su disponibilidad.
    
    El servidor backend es responsable de:
    1. Procesar las consultas de síntomas
    2. Interactuar con la base de datos Milvus
    3. Generar diagnósticos usando IA
    4. Gestionar la comunicación entre componentes
    
    Esta función verifica que el servidor esté en funcionamiento y responda
    correctamente a las peticiones de estado.
    
    Args:
        retry (bool): Indica si es un reintento de conexión
    
    Returns:
        tuple: (bool, dict/str) - Un booleano indicando si el servidor está activo
               y un diccionario con el estado o un mensaje de error
    """
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8000')
    try:
        # Aumentar el timeout en reintentos
        timeout = 10 if retry else 5
        response = requests.get(f"{backend_url}/status", timeout=timeout)
        if response.status_code == 200:
            status_data = response.json()
            return True, status_data
        return False, f"Estado del servidor: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Error al conectar con el backend: {str(e)}"

def check_milvus_collection(retry=False):
    """Verificar estado de la colección de vectores en Milvus.
    
    La colección en Milvus almacena:
    1. Vectores de características de enfermedades
    2. Metadatos asociados a cada enfermedad
    3. Índices para búsqueda eficiente
    
    Esta función verifica a través del backend:
    - La existencia de la colección
    - El número de registros almacenados
    - El estado del índice de búsqueda
    
    Args:
        retry (bool): Indica si es un reintento de conexión
    
    Returns:
        tuple: (bool, dict/str) - Un booleano indicando si la colección está disponible
               y un diccionario con estadísticas o un mensaje de error
    """
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8000')
    try:
        # Aumentar el timeout en reintentos
        timeout = 10 if retry else 5
        response = requests.get(f"{backend_url}/milvus-status", timeout=timeout)
        if response.status_code == 200:
            status_data = response.json()
            return True, status_data
        return False, f"Error al obtener estado de la colección: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Error al verificar colección: {str(e)}"

def retry_with_backoff(func, max_retries=5, initial_delay=1, max_delay=30, backoff_factor=2, **kwargs):
    """Ejecuta una función con reintentos y espera exponencial.
    
    Args:
        func: La función a ejecutar
        max_retries: Número máximo de reintentos
        initial_delay: Tiempo inicial de espera en segundos
        max_delay: Tiempo máximo de espera en segundos
        backoff_factor: Factor de incremento para la espera exponencial
        **kwargs: Argumentos adicionales para la función
    
    Returns:
        tuple: El resultado de la función (éxito/fracaso, detalles)
    """
    delay = initial_delay
    last_result = (False, "No se realizó ningún intento")
    
    with Progress() as progress:
        task = progress.add_task(f"[cyan]Intentando {func.__name__}...", total=max_retries)
        
        for attempt in range(max_retries):
            # Actualizar la barra de progreso
            progress.update(task, completed=attempt, description=f"[cyan]Intento {attempt+1}/{max_retries} de {func.__name__}...")
            
            # Ejecutar la función con el parámetro retry=True para indicar que es un reintento
            result = func(retry=True, **kwargs)
            
            # Si la función tuvo éxito, retornar el resultado
            if result[0]:
                progress.update(task, completed=max_retries, description=f"[green]✅ {func.__name__} exitoso!")
                return result
            
            # Guardar el último resultado para retornarlo en caso de fallo total
            last_result = result
            
            # Si no es el último intento, esperar antes de reintentar
            if attempt < max_retries - 1:
                # Añadir un poco de aleatoriedad a la espera (jitter)
                jitter = random.uniform(0.8, 1.2)
                wait_time = min(delay * jitter, max_delay)
                
                progress.update(task, description=f"[yellow]Esperando {wait_time:.1f}s antes de reintentar...")
                time.sleep(wait_time)
                
                # Incrementar el tiempo de espera para el próximo intento (espera exponencial)
                delay = min(delay * backoff_factor, max_delay)
        
        progress.update(task, completed=max_retries, description=f"[red]❌ {func.__name__} falló después de {max_retries} intentos")
    
    return last_result

def check_system_with_retries(max_retries=5):
    """Verifica el estado del sistema con reintentos automáticos.
    
    Args:
        max_retries: Número máximo de reintentos para cada componente
    
    Returns:
        bool: True si todos los componentes están funcionando correctamente
    """
    # Crear tabla de resultados
    table = Table(title="Estado del Sistema (con reintentos automáticos)")
    table.add_column("Componente", style="cyan")
    table.add_column("Estado", style="green")
    table.add_column("Detalles", style="yellow")
    table.add_column("Intentos", style="magenta")

    # Verificar variables de entorno (sin reintentos, es una verificación local)
    console.print("[bold cyan]Verificando variables de entorno...")
    env_status, missing_vars = check_env_variables()
    table.add_row(
        "Variables de Entorno",
        "✅ OK" if env_status else "❌ Error",
        "Todas las variables configuradas" if env_status else f"Faltantes: {', '.join(missing_vars)}",
        "1/1"
    )

    # Verificar archivo XML (sin reintentos, es una verificación local)
    console.print("[bold cyan]Verificando archivo XML...")
    xml_status, xml_details = check_xml_file()
    table.add_row(
        "Archivo XML",
        "✅ OK" if xml_status else "❌ Error",
        xml_details,
        "1/1"
    )

    # Verificar conexión Milvus con reintentos
    console.print("[bold cyan]Verificando conexión con Milvus (con reintentos)...")
    milvus_attempts = 1
    milvus_status, milvus_details = check_milvus_connection()
    
    # Si falla el primer intento, usar reintentos con backoff
    if not milvus_status:
        console.print("[yellow]Primer intento de conexión a Milvus falló, iniciando reintentos...")
        milvus_status, milvus_details = retry_with_backoff(check_milvus_connection, max_retries=max_retries)
        milvus_attempts = max_retries
    
    table.add_row(
        "Conexión Milvus",
        "✅ OK" if milvus_status else "❌ Error",
        milvus_details,
        f"{1 if milvus_status else milvus_attempts}/{max_retries}"
    )

    # Verificar estado del backend con reintentos
    console.print("[bold cyan]Verificando estado del backend (con reintentos)...")
    backend_attempts = 1
    backend_status, backend_details = check_backend_status()
    
    # Si falla el primer intento, usar reintentos con backoff
    if not backend_status:
        console.print("[yellow]Primer intento de conexión al backend falló, iniciando reintentos...")
        backend_status, backend_details = retry_with_backoff(check_backend_status, max_retries=max_retries)
        backend_attempts = max_retries
    
    if backend_status:
        status = "✅ OK" if backend_details.get('initialization_complete') else "⏳ Inicializando"
        details = "Todos los componentes inicializados" if backend_details.get('initialization_complete') else "Componentes en inicialización"
    else:
        status = "❌ Error"
        details = str(backend_details)
    
    table.add_row(
        "Servidor Backend", 
        status, 
        details,
        f"{1 if backend_status else backend_attempts}/{max_retries}"
    )

    # Verificar colección Milvus con reintentos (solo si la conexión a Milvus fue exitosa)
    collection_status = False
    collection_details = "No verificado (conexión a Milvus fallida)"
    collection_attempts = 0
    
    if milvus_status:
        console.print("[bold cyan]Verificando colección de Milvus (con reintentos)...")
        collection_attempts = 1
        collection_status, collection_details = check_milvus_collection()
        
        # Si falla el primer intento, usar reintentos con backoff
        if not collection_status:
            console.print("[yellow]Primer intento de verificar colección falló, iniciando reintentos...")
            collection_status, collection_details = retry_with_backoff(check_milvus_collection, max_retries=max_retries)
            collection_attempts = max_retries
        
        if collection_status:
            status = "✅ OK"
            details = f"Registros: {collection_details.get('row_count', 0)}, Índice: {collection_details.get('index_status')}"
        else:
            status = "❌ Error"
            details = str(collection_details)
        
        table.add_row(
            "Colección Milvus", 
            status, 
            details,
            f"{1 if collection_status else collection_attempts}/{max_retries}"
        )

    # Mostrar resultados
    console.print("\n[bold]Resultados finales después de reintentos:[/bold]")
    console.print(table)

    # Determinar estado general del sistema
    system_ok = env_status and xml_status and milvus_status and backend_status
    if not system_ok:
        console.print("\n[red bold]⚠️ Se encontraron errores en el sistema después de múltiples reintentos.[/red bold]")
        console.print("[yellow]Revise los detalles arriba y asegúrese de que todos los servicios estén en funcionamiento.[/yellow]")
    else:
        console.print("\n[green bold]✅ Todos los sistemas funcionando correctamente después de los reintentos![/green bold]")
    
    return system_ok

def main():
    """Función principal que ejecuta la verificación del sistema con reintentos."""
    console.print("[bold blue]=== Sistema de Diagnóstico Médico - Verificación de Componentes ===[/bold blue]")
    console.print("[italic]Verificando el estado de todos los componentes con reintentos automáticos...[/italic]\n")
    
    # Ejecutar verificación con reintentos
    max_retries = 5  # Número máximo de reintentos para cada componente
    system_ok = check_system_with_retries(max_retries)
    
    # Salir con código de error si el sistema no está funcionando correctamente
    if not system_ok:
        sys.exit(1)

if __name__ == "__main__":
    main()