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

def check_docker_status():
    """Verificar el estado de los contenedores Docker.
    
    Esta función verifica:
    1. Estado de los contenedores Docker
    2. Uso de recursos (CPU, memoria)
    3. Logs recientes y errores
    4. Estado de la red Docker
    5. Estado de los volúmenes
    6. Salud del contenedor (health checks)
    7. Configuración de reinicio
    8. Estado de las imágenes
    9. Recursos no utilizados
    10. Métricas de rendimiento
    
    Returns:
        tuple: (bool, dict) - Un booleano indicando si todos los contenedores están saludables
               y un diccionario con información detallada del estado
    """
    try:
        # Verificar estado de los contenedores y su salud
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.State}}\t{{.Health}}\t{{.RestartCount}}"],
            capture_output=True, text=True, check=True
        )
        containers = [line.split('\t') for line in result.stdout.strip().split('\n') if line]
        
        # Verificar configuración de reinicio
        inspect_result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}}\t{{.HostConfig.RestartPolicy.Name}}", "$(docker ps -q)"],
            capture_output=True, text=True, shell=True
        )
        restart_policies = dict(line.strip().split('\t') for line in inspect_result.stdout.strip().split('\n') if line)
        
        # Obtener estadísticas de uso de recursos
        stats = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"],
            capture_output=True, text=True, check=True
        )
        resources = [line.split('\t') for line in stats.stdout.strip().split('\n') if line]
        
        # Verificar logs recientes (últimas 5 líneas)
        logs = {}
        for container in containers:
            container_name = container[0]
            log_result = subprocess.run(
                ["docker", "logs", "--tail", "5", container_name],
                capture_output=True, text=True
            )
            logs[container_name] = log_result.stdout.strip().split('\n')
        
        # Verificar red Docker y conexiones entre contenedores
        network = subprocess.run(
            ["docker", "network", "ls", "--format", "{{.Name}}\t{{.Driver}}\t{{.Scope}}"],
            capture_output=True, text=True, check=True
        )
        
        # Obtener información detallada de las redes
        networks_info = {}
        for network_line in network.stdout.strip().split('\n'):
            if network_line:
                network_name = network_line.split('\t')[0]
                inspect_result = subprocess.run(
                    ["docker", "network", "inspect", network_name],
                    capture_output=True, text=True, check=True
                )
                networks_info[network_name] = inspect_result.stdout
        
        # Verificar volúmenes y su espacio
        volumes = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True, text=True, check=True
        )
        
        # Obtener información detallada de cada volumen
        volume_info = {}
        for volume in volumes.stdout.strip().split('\n'):
            if volume:
                inspect_result = subprocess.run(
                    ["docker", "volume", "inspect", volume],
                    capture_output=True, text=True, check=True
                )
                volume_info[volume] = inspect_result.stdout
        
        # Verificar imágenes Docker
        images = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}"],
            capture_output=True, text=True, check=True
        )
        
        # Verificar recursos no utilizados
        dangling_volumes = subprocess.run(
            ["docker", "volume", "ls", "--filter", "dangling=true", "--format", "{{.Name}}"],
            capture_output=True, text=True, check=True
        )
        
        dangling_images = subprocess.run(
            ["docker", "images", "--filter", "dangling=true", "--format", "{{.ID}}"],
            capture_output=True, text=True, check=True
        )
        
        # Verificar métricas de rendimiento detalladas
        detailed_stats = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", 
             "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"],
            capture_output=True, text=True, check=True
        )
        performance_metrics = [line.split('\t') for line in detailed_stats.stdout.strip().split('\n') if line]
        
        status_info = {
            'containers': {
                name: {
                    'status': status,
                    'state': state,
                    'health': health if len(health.strip()) > 0 else 'N/A',
                    'restart_count': restart_count,
                    'restart_policy': restart_policies.get(name, 'N/A')
                }
                for name, status, state, health, restart_count in containers
            },
            'resources': {
                name: {'cpu': cpu, 'memory': mem}
                for name, cpu, mem in resources
            },
            'performance': {
                name: {
                    'cpu_percent': metrics[1],
                    'memory_usage': metrics[2],
                    'memory_percent': metrics[3],
                    'network_io': metrics[4],
                    'block_io': metrics[5],
                    'pids': metrics[6]
                }
                for metrics in performance_metrics if len(metrics) >= 7
            },
            'logs': logs,
            'networks': [line.split('\t') for line in network.stdout.strip().split('\n')],
            'volumes': volumes.stdout.strip().split('\n'),
            'images': [line.split('\t') for line in images.stdout.strip().split('\n')],
            'cleanup_needed': {
                'dangling_volumes': dangling_volumes.stdout.strip().split('\n'),
                'dangling_images': dangling_images.stdout.strip().split('\n')
            }
        }
        
        # Verificar si todos los contenedores están saludables
        all_healthy = all(info['state'] == 'running' for info in status_info['containers'].values())
        
        return all_healthy, status_info
        
    except subprocess.CalledProcessError as e:
        return False, {"error": f"Error al ejecutar comando Docker: {str(e)}"}
    except Exception as e:
        return False, {"error": f"Error inesperado: {str(e)}"}
def check_mongodb_connection(retry=False):
    """Verificar conexión con la base de datos MongoDB.
    
    MongoDB se utiliza para almacenar información estructurada sobre enfermedades,
    síntomas, y diagnósticos. Esta función intenta establecer una conexión con
    el servidor MongoDB usando los parámetros configurados en las variables de entorno.
    
    Args:
        retry (bool): Indica si es un reintento de conexión
    
    Returns:
        tuple: (bool, str) - Un booleano indicando si la conexión fue exitosa
               y un mensaje describiendo el resultado o error
    """
    try:
        # Importar pymongo solo cuando se necesite
        import pymongo
        from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
        
        # Obtener parámetros de conexión desde variables de entorno
        mongo_host = os.getenv("MONGODB_HOST", "localhost")
        mongo_port = int(os.getenv("MONGODB_PORT", "27017"))
        mongo_user = os.getenv("MONGODB_USER", "")
        mongo_pass = os.getenv("MONGODB_PASSWORD", "")
        mongo_db = os.getenv("MONGODB_DATABASE", "sintomas_diagnostico")
        
        # Verificar si Docker está ejecutándose y si el contenedor MongoDB está activo
        try:
            import subprocess
            
            # Verificar contenedores de MongoDB
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=mongodb", "--format", "{{.Names}} ({{.Status}})"],
                capture_output=True, text=True, check=True
            )
            mongodb_containers = result.stdout.strip()
            
            if not mongodb_containers:
                # Verificar si el contenedor existe pero no está en ejecución
                result = subprocess.run(
                    ["docker", "ps", "-a", "--filter", "name=mongodb", "--format", "{{.Names}} ({{.Status}})"],
                    capture_output=True, text=True, check=True
                )
                stopped_containers = result.stdout.strip()
                
                if stopped_containers:
                    console.print(f"[yellow]Contenedor MongoDB encontrado pero no está en ejecución: {stopped_containers}[/yellow]")
                    console.print("[cyan]Intentando iniciar el contenedor MongoDB...[/cyan]")
                    
                    # Intentar iniciar el contenedor
                    try:
                        container_name = stopped_containers.split()[0].split('(')[0].strip()
                        subprocess.run(
                            ["docker", "start", container_name],
                            capture_output=True, text=True, check=True
                        )
                        console.print(f"[green]Contenedor {container_name} iniciado correctamente[/green]")
                        # Esperar a que el contenedor esté listo
                        console.print("[cyan]Esperando 5 segundos para que MongoDB se inicialice...[/cyan]")
                        time.sleep(5)
                    except subprocess.CalledProcessError as e:
                        console.print(f"[red]Error al iniciar el contenedor MongoDB: {e}[/red]")
                        return False, f"Error al iniciar el contenedor MongoDB: {e}"
                else:
                    console.print("[yellow]No se encontró ningún contenedor de MongoDB. Creando uno nuevo...[/yellow]")
                    
                    # Crear un nuevo contenedor MongoDB
                    try:
                        # Crear volumen persistente para los datos
                        console.print("[cyan]Creando volumen persistente para MongoDB...[/cyan]")
                        subprocess.run(
                            ["docker", "volume", "create", "mongodb_data"],
                            capture_output=True, text=True, check=True
                        )
                        
                        # Ejecutar contenedor MongoDB
                        console.print("[cyan]Ejecutando contenedor MongoDB...[/cyan]")
                        
                        # Determinar si usar autenticación
                        if mongo_user and mongo_pass:
                            # Con autenticación
                            subprocess.run(
                                ["docker", "run", "-d",
                                 "--name", "mongodb",
                                 "-p", f"{mongo_port}:27017",
                                 "-v", "mongodb_data:/data/db",
                                 "-e", f"MONGO_INITDB_ROOT_USERNAME={mongo_user}",
                                 "-e", f"MONGO_INITDB_ROOT_PASSWORD={mongo_pass}",
                                 "-e", f"MONGO_INITDB_DATABASE={mongo_db}",
                                 "mongo:latest"],
                                capture_output=True, text=True, check=True
                            )
                        else:
                            # Sin autenticación (para desarrollo)
                            subprocess.run(
                                ["docker", "run", "-d",
                                 "--name", "mongodb",
                                 "-p", f"{mongo_port}:27017",
                                 "-v", "mongodb_data:/data/db",
                                 "mongo:latest"],
                                capture_output=True, text=True, check=True
                            )
                        
                        console.print("[green]Contenedor MongoDB creado correctamente[/green]")
                        # Esperar a que el contenedor esté listo
                        console.print("[cyan]Esperando 10 segundos para que MongoDB se inicialice...[/cyan]")
                        time.sleep(10)
                    except subprocess.CalledProcessError as e:
                        console.print(f"[red]Error al crear el contenedor MongoDB: {e}[/red]")
                        return False, f"Error al crear el contenedor MongoDB: {e}"
            else:
                console.print(f"[green]Contenedores MongoDB en ejecución: {mongodb_containers}[/green]")
        except Exception as e:
            console.print(f"[yellow]Error al verificar contenedores Docker para MongoDB: {e}[/yellow]")
        
        # Lista de hosts a probar en Windows con Docker
        hosts_to_try = [mongo_host]
        if os.name == "nt" and mongo_host == "localhost":  # Windows
            hosts_to_try = ["host.docker.internal", "localhost", "127.0.0.1"]
        
        # Intentar conectar con diferentes hosts
        last_error = None
        for current_host in hosts_to_try:
            try:
                # Construir URI de conexión
                if mongo_user and mongo_pass:
                    uri = f"mongodb://{mongo_user}:{mongo_pass}@{current_host}:{mongo_port}/{mongo_db}?authSource=admin"
                else:
                    uri = f"mongodb://{current_host}:{mongo_port}/{mongo_db}"
                
                # Intentar conectar con timeout aumentado en reintentos
                timeout = 10.0 if retry else 5.0
                console.print(f"[cyan]Intentando conectar a MongoDB en {current_host}:{mongo_port} (timeout: {timeout}s)...[/cyan]")
                
                # Crear cliente MongoDB con timeout
                client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=int(timeout * 1000))
                
                # Verificar la conexión con una operación simple
                server_info = client.server_info()
                db_names = client.list_database_names()
                
                # Verificar la base de datos específica
                db = client[mongo_db]
                collections = db.list_collection_names()
                
                # Actualizar la variable de entorno con el host que funcionó
                if current_host != mongo_host:
                    console.print(f"[green]Conexión exitosa usando host alternativo: {current_host}[/green]")
                    console.print(f"[yellow]Considere actualizar su archivo .env con MONGODB_HOST={current_host}[/yellow]")
                
                return True, f"Conexión exitosa a MongoDB {server_info.get('version')} en {current_host}:{mongo_port}. Bases de datos: {db_names}. Colecciones en {mongo_db}: {collections}"
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                last_error = e
                error_msg = str(e)
                console.print(f"[yellow]Error al conectar con {current_host}: {error_msg}[/yellow]")
            except Exception as e:
                last_error = e
                error_msg = str(e)
                console.print(f"[yellow]Error inesperado al conectar con {current_host}: {error_msg}[/yellow]")
            finally:
                # Cerrar la conexión si se creó
                try:
                    if 'client' in locals():
                        client.close()
                except:
                    pass
        
        # Si llegamos aquí, todos los intentos fallaron
        error_msg = str(last_error) if last_error else "Error desconocido"
        
        # Proporcionar mensajes de error más descriptivos según el tipo de error
        suggestions = ""
        if "Connection refused" in error_msg:
            suggestions = " Verifique que MongoDB esté en ejecución y accesible. En Windows con Docker, intente usar 'host.docker.internal' como host."
        elif "Authentication failed" in error_msg:
            suggestions = " Verifique que las credenciales (usuario y contraseña) sean correctas."
        
        return False, f"Error de conexión a MongoDB: {error_msg}.{suggestions}"
    except Exception as e:
        return False, f"Error inesperado al verificar MongoDB: {str(e)}"

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
        
        # Verificar si Docker está ejecutándose y si el contenedor Milvus está activo
        try:
            import subprocess
            # Verificar si Docker está en ejecución
            docker_running = False
            try:
                result = subprocess.run(
                    ["docker", "info"],
                    capture_output=True, text=True, check=True
                )
                docker_running = True
                console.print("[green]Docker está en ejecución[/green]")
            except subprocess.CalledProcessError:
                console.print("[yellow]Docker no está en ejecución. Intentando iniciar Docker Desktop...[/yellow]")
                
                # Intentar iniciar Docker Desktop automáticamente
                try:
                    # Ruta común de Docker Desktop en Windows
                    docker_paths = [
                        os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'Docker', 'Docker', 'Docker Desktop.exe'),
                        os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), 'Docker', 'Docker', 'Docker Desktop.exe'),
                        os.path.join(os.environ.get('LocalAppData', 'C:\\Users\\' + os.environ.get('USERNAME', 'user') + '\\AppData\\Local'), 'Docker', 'Docker', 'Docker Desktop.exe')
                    ]
                    
                    docker_path = None
                    for path in docker_paths:
                        if os.path.exists(path):
                            docker_path = path
                            break
                    
                    if docker_path:
                        console.print(f"[cyan]Iniciando Docker Desktop desde: {docker_path}[/cyan]")
                        # Iniciar Docker Desktop en segundo plano
                        subprocess.Popen([docker_path], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Esperar a que Docker se inicie completamente
                        console.print("[cyan]Esperando a que Docker se inicie (60 segundos)...[/cyan]")
                        
                        # Mostrar progreso de espera
                        with Progress() as progress:
                            task = progress.add_task("[cyan]Iniciando Docker...", total=60)
                            docker_started = False
                            
                            for i in range(60):
                                time.sleep(1)
                                progress.update(task, advance=1)
                                
                                # Verificar si Docker ya está disponible
                                if i > 10 and i % 5 == 0:  # Empezar a verificar después de 10 segundos, cada 5 segundos
                                    try:
                                        check_result = subprocess.run(
                                            ["docker", "info"],
                                            capture_output=True, text=True, check=True,
                                            timeout=2  # Timeout corto para no bloquear demasiado tiempo
                                        )
                                        docker_started = True
                                        console.print("[green]¡Docker iniciado correctamente![/green]")
                                        docker_running = True
                                        break
                                    except:
                                        pass  # Seguir esperando
                            
                            if not docker_started:
                                console.print("[red]No se pudo iniciar Docker automáticamente después de 60 segundos.[/red]")
                                return False, "No se pudo iniciar Docker automáticamente. Por favor, inicie Docker Desktop manualmente."
                    else:
                        console.print("[red]No se encontró Docker Desktop en las rutas habituales.[/red]")
                        return False, "Docker no está en ejecución y no se encontró en las rutas habituales. Inicie Docker Desktop manualmente."
                except Exception as e:
                    console.print(f"[red]Error al intentar iniciar Docker: {e}[/red]")
                    return False, f"Error al intentar iniciar Docker: {e}. Inicie Docker Desktop manualmente."
            except FileNotFoundError:
                console.print("[red]Docker no está instalado o no está en el PATH.[/red]")
                return False, "Docker no está instalado o no está en el PATH. Instale Docker Desktop."
            
            # Continuar con la verificación de Milvus si Docker está en ejecución
            if docker_running:
                # Verificar contenedores de Milvus
                result = subprocess.run(
                    ["docker", "ps", "--filter", "name=milvus", "--format", "{{.Names}} ({{.Status}})"],
                    capture_output=True, text=True, check=True
                )
                milvus_containers = result.stdout.strip()
                
                if not milvus_containers:
                    # Verificar si el contenedor existe pero no está en ejecución
                    result = subprocess.run(
                        ["docker", "ps", "-a", "--filter", "name=milvus", "--format", "{{.Names}} ({{.Status}})"],
                        capture_output=True, text=True, check=True
                    )
                    stopped_containers = result.stdout.strip()
                    
                    if stopped_containers:
                        console.print(f"[yellow]Contenedor Milvus encontrado pero no está en ejecución: {stopped_containers}[/yellow]")
                        console.print("[cyan]Intentando iniciar el contenedor Milvus...[/cyan]")
                        
                        # Intentar iniciar el contenedor
                        try:
                            container_name = stopped_containers.split()[0].split('(')[0].strip()
                            subprocess.run(
                                ["docker", "start", container_name],
                                capture_output=True, text=True, check=True
                            )
                            console.print(f"[green]Contenedor {container_name} iniciado correctamente[/green]")
                            # Esperar a que el contenedor esté listo
                            console.print("[cyan]Esperando 10 segundos para que el contenedor se inicialice...[/cyan]")
                            time.sleep(10)
                        except subprocess.CalledProcessError as e:
                            console.print(f"[red]Error al iniciar el contenedor: {e}[/red]")
                            return False, f"Error al iniciar el contenedor Milvus: {e}"
                    else:
                        console.print("[yellow]No se encontró ningún contenedor de Milvus. Creando uno nuevo con configuración optimizada...[/yellow]")
                        
                        # Crear un nuevo contenedor Milvus con configuración optimizada para Windows
                        try:
                            # Detener y eliminar contenedores previos si existen (por si acaso)
                            subprocess.run(
                                ["docker", "rm", "-f", "milvus-standalone"],
                                capture_output=True, text=True, check=False  # Ignorar errores si no existe
                            )
                            
                            # Crear volumen persistente para los datos
                            subprocess.run(
                                ["docker", "volume", "create", "milvus_data"],
                                capture_output=True, text=True, check=True
                            )
                            
                            # Ejecutar contenedor Milvus standalone
                            console.print("[cyan]Ejecutando contenedor Milvus standalone...[/cyan]")
                            subprocess.run(
                                ["docker", "run", "-d",
                                 "--name", "milvus-standalone",
                                 "-p", "19530:19530",
                                 "-p", "9091:9091",
                                 "-v", "milvus_data:/var/lib/milvus",
                                 "-e", "ETCD_USE_EMBED=true",
                                 "-e", "MINIO_USE_EMBED=true",
                                 "milvusdb/milvus:v2.3.3"],
                                capture_output=True, text=True, check=True
                            )
                            
                            console.print("[green]Contenedor Milvus creado correctamente[/green]")
                            # Esperar a que el contenedor esté listo
                            console.print("[cyan]Esperando 20 segundos para que Milvus se inicialice...[/cyan]")
                            
                            # Mostrar progreso de espera
                            with Progress() as progress:
                                task = progress.add_task("[cyan]Inicializando Milvus...", total=20)
                                for i in range(20):
                                    time.sleep(1)
                                    progress.update(task, advance=1)
                        except subprocess.CalledProcessError as e:
                            console.print(f"[red]Error al crear el contenedor Milvus: {e}[/red]")
                            return False, f"Error al crear el contenedor Milvus: {e}"
                else:
                    console.print(f"[green]Contenedores Milvus en ejecución: {milvus_containers}[/green]")
        except Exception as e:
            console.print(f"[yellow]Error al verificar contenedores Docker para Milvus: {e}[/yellow]")
        
        # Obtener parámetros de conexión desde variables de entorno
        milvus_host = os.getenv("MILVUS_HOST", "localhost")
        milvus_port = os.getenv("MILVUS_PORT", "19530")
        
        # Lista de hosts a probar en Windows con Docker
        hosts_to_try = [milvus_host]
        if os.name == "nt" and milvus_host == "localhost":  # Windows
            hosts_to_try = ["host.docker.internal", "localhost", "127.0.0.1"]
        
        # Intentar conectar con diferentes hosts
        last_error = None
        for host in hosts_to_try:
            try:
                # Aumentar el timeout en reintentos
                timeout = 10.0 if retry else 5.0
                console.print(f"[cyan]Intentando conectar a Milvus en {host}:{milvus_port} (timeout: {timeout}s)...[/cyan]")
                
                # Intentar conectar a Milvus
                connections.connect(
                    alias="default",
                    host=host,
                    port=milvus_port,
                    timeout=timeout
                )
                
                # Verificar la conexión con una operación simple
                from pymilvus import utility
                
                # Listar colecciones para verificar que la conexión funciona
                collections = utility.list_collections()
                
                # Actualizar la variable de entorno con el host que funcionó
                if host != milvus_host:
                    console.print(f"[green]Conexión exitosa usando host alternativo: {host}[/green]")
                    console.print(f"[yellow]Considere actualizar su archivo .env con MILVUS_HOST={host}[/yellow]")
                
                return True, f"Conexión exitosa a Milvus en {host}:{milvus_port}. Colecciones: {collections}"
            except Exception as e:
                last_error = e
                error_msg = str(e)
                console.print(f"[yellow]Error al conectar con {host}: {error_msg}[/yellow]")
                
                # Desconectar antes de intentar con otro host
                try:
                    connections.disconnect("default")
                except:
                    pass
        
        # Si llegamos aquí, todos los intentos fallaron
        error_msg = str(last_error) if last_error else "Error desconocido"
        
        # Proporcionar mensajes de error más descriptivos según el tipo de error
        suggestions = ""
        if "Connection refused" in error_msg:
            suggestions = " Verifique que el contenedor Milvus esté en ejecución. En Windows con Docker, intente usar 'host.docker.internal' como host."
        elif "timed out" in error_msg.lower():
            suggestions = " El servidor Milvus no respondió a tiempo. Verifique el estado del contenedor y la configuración de red."
        
        return False, f"Error de conexión a Milvus: {error_msg}.{suggestions}"
    except Exception as e:
        return False, f"Error inesperado al verificar Milvus: {str(e)}"

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
    
    # Verificar conexión MongoDB con reintentos
    console.print("[bold cyan]Verificando conexión con MongoDB (con reintentos)...")
    mongodb_attempts = 1
    mongodb_status, mongodb_details = check_mongodb_connection()
    
    # Si falla el primer intento, usar reintentos con backoff
    if not mongodb_status:
        console.print("[yellow]Primer intento de conexión a MongoDB falló, iniciando reintentos...")
        mongodb_status, mongodb_details = retry_with_backoff(check_mongodb_connection, max_retries=max_retries)
        mongodb_attempts = max_retries
    
    table.add_row(
        "Conexión MongoDB",
        "✅ OK" if mongodb_status else "❌ Error",
        mongodb_details,
        f"{1 if mongodb_status else mongodb_attempts}/{max_retries}"
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