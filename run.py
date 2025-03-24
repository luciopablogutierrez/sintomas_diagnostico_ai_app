import os
import subprocess
import time
import sys
import webbrowser
import requests
from dotenv import load_dotenv
import threading

# Cargar variables de entorno
load_dotenv()

load_dotenv()

def check_python():
    """Verificar la instalación y disponibilidad de Python en el sistema.
    
    Esta función comprueba si Python está instalado y accesible en el PATH
    del sistema, lo cual es esencial para ejecutar la aplicación.
    
    Returns:
        bool: True si Python está instalado y disponible, False en caso contrario
    """
    try:
        subprocess.run([sys.executable, "--version"], check=True)
        return True
    except:
        print("Python is not installed or not in PATH. Please install Python first.")
        return False

def check_docker():
    """Verificar la instalación y disponibilidad de Docker en el sistema.
    
    Docker es necesario para ejecutar Milvus y sus dependencias (etcd, MinIO).
    Esta función verifica que Docker esté instalado y accesible en el sistema.
    
    Returns:
        bool: True si Docker está instalado y disponible, False en caso contrario
    """
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Docker is installed: {result.stdout.strip()}")
            return True
        else:
            print("Docker is not installed or not in PATH.")
            return False
    except FileNotFoundError:
        print("Docker is not installed or not in PATH.")
        return False

def setup_environment():
    """Configurar el entorno virtual y las dependencias del proyecto.
    
    Esta función realiza las siguientes tareas:
    1. Crea un entorno virtual si no existe
    2. Activa el entorno virtual
    3. Instala todas las dependencias del archivo requirements.txt
    4. Si falla la instalación en masa, intenta instalar cada dependencia individualmente
    
    El entorno virtual aísla las dependencias del proyecto para evitar conflictos
    con otros proyectos Python en el sistema.
    """
    print("Setting up virtual environment...")
    if not os.path.exists(".venv"):
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
    
    # Activate virtual environment and install dependencies
    print("Installing dependencies...")
    if os.name == "nt":  # Windows
        pip_cmd = f".venv\\Scripts\\pip install -r requirements.txt"
    else:  # Unix/Linux
        pip_cmd = f".venv/bin/pip install -r requirements.txt"
    
    try:
        subprocess.run(pip_cmd, shell=True, check=True)
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        print("Trying to install dependencies one by one...")
        
        # Try to install dependencies one by one
        with open("requirements.txt", "r") as f:
            dependencies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        for dep in dependencies:
            try:
                if os.name == "nt":  # Windows
                    subprocess.run(f".venv\\Scripts\\pip install {dep}", shell=True, check=True)
                else:  # Unix/Linux
                    subprocess.run(f".venv/bin/pip install {dep}", shell=True, check=True)
                print(f"Installed {dep}")
            except subprocess.CalledProcessError:
                print(f"Failed to install {dep}")

def start_milvus():
    """Iniciar y configurar el servidor Milvus y sus dependencias.
    
    Milvus es una base de datos vectorial que requiere varios componentes:
    - etcd: Para gestión de metadatos y configuración
    - MinIO: Para almacenamiento de datos
    - Milvus standalone: El servidor principal
    
    Esta función maneja:
    1. Verificación de Docker
    2. Gestión de contenedores
    3. Inicialización de servicios
    4. Verificación de disponibilidad
    
    Returns:
        bool: True si Milvus se inició correctamente, False en caso contrario
    """
    if not check_docker():
        print("Docker is required to run Milvus. Please install Docker and try again.")
        print("You can download Docker Desktop from: https://www.docker.com/products/docker-desktop")
        return False
    
    # Check if Docker is running
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        print("Docker is installed but not running. Please start Docker Desktop and try again.")
        return False
    
    print("Starting Milvus...")
    max_restart_attempts = 3
    for restart_attempt in range(max_restart_attempts):
        try:
            # Stop and remove existing containers to ensure clean state
            print("Stopping any existing Milvus containers...")
            subprocess.run(["docker-compose", "down"], check=True)
            time.sleep(5)  # Wait for containers to stop completely
            
            # Start the containers
            print("Starting fresh Milvus containers...")
            subprocess.run(["docker-compose", "up", "-d"], check=True)
            print("Milvus containers started")
            
            # Wait for containers to be in running state
            print("Waiting for containers to be ready...")
            time.sleep(10)  # Initial wait time increased
            
            # Check container status
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=milvus-standalone", "--format", "{{.Status}}"],
                capture_output=True, text=True, check=True
            )
            
            if "Up" not in result.stdout:
                print(f"Container not in 'Up' state. Current status: {result.stdout}")
                if restart_attempt < max_restart_attempts - 1:
                    print(f"Retrying... (attempt {restart_attempt + 1}/{max_restart_attempts})")
                    continue
                return False
            
            # Check container logs for readiness
            print("Checking Milvus container logs...")
            subprocess.run(["docker", "logs", "milvus-standalone"], check=False)
            
            # More robust waiting for Milvus to be ready
            max_connection_attempts = 30  # Increased from 20 to 30
            for attempt in range(max_connection_attempts):
                print(f"Checking Milvus availability (attempt {attempt+1}/{max_connection_attempts})...")
                try:
                    # Try to connect to Milvus with increased timeout
                    from pymilvus import connections
                    connections.connect("default", host="localhost", port="19530", timeout=15.0)
                    
                    # Test the connection with a simple operation
                    from pymilvus import utility
                    collections = utility.list_collections()
                    print(f"Successfully connected to Milvus. Available collections: {collections}")
                    
                    connections.disconnect("default")
                    print("Milvus is ready!")
                    return True
                except Exception as e:
                    print(f"Milvus not ready yet: {e}")
                    
                    # Check container health more frequently
                    if attempt % 2 == 0:  # Check every 2 attempts instead of 3
                        try:
                            result = subprocess.run(
                                ["docker", "ps", "--filter", "name=milvus-standalone", "--format", "{{.Status}}"],
                                capture_output=True, text=True, check=True
                            )
                            if "Up" not in result.stdout:
                                print(f"Container status changed: {result.stdout}")
                                break  # Break inner loop to trigger container restart
                            print(f"Container status: {result.stdout}")
                        except Exception as container_error:
                            print(f"Error checking container status: {container_error}")
                    
                    time.sleep(5)
            
            if restart_attempt < max_restart_attempts - 1:
                print("Milvus failed to initialize. Attempting restart...")
                continue
            else:
                print("Milvus failed to start after multiple attempts.")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"Error in Milvus startup process: {e}")
            if restart_attempt < max_restart_attempts - 1:
                print(f"Retrying... (attempt {restart_attempt + 1}/{max_restart_attempts})")
                continue
            return False
    
    return False  # Should not reach here, but just in case

def start_backend():
    print("Starting backend server...")
    
    backend_path = os.path.join(os.getcwd(), "backend", "main.py")
    if not os.path.exists(backend_path):
        print(f"Error: Backend file not found at {backend_path}")
        return None
    
    try:
        # Verify backend dependencies
        print("Checking backend dependencies...")
        subprocess.run(
            [".venv\\Scripts\\pip", "install", "-r", "requirements.txt"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Start backend with real-time output
        print("Executing: .venv\\Scripts\\python backend\\main.py")
        backend_process = subprocess.Popen(
            [".venv\\Scripts\\python", "backend\\main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True  # This ensures text mode
        )

        # Monitor startup in real-time
        print("Monitoring backend startup...")
        start_time = time.time()
        while time.time() - start_time < 30:  # 30-second timeout
            # Check process status
            if backend_process.poll() is not None:
                print(f"Backend process exited with code: {backend_process.returncode}")
                stderr = backend_process.stderr.read()  # Already text due to universal_newlines=True
                print(f"Error output: {stderr}")
                return None
            
            # Check server responsiveness
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    print("Backend server is ready")
                    return backend_process
            except (requests.ConnectionError, requests.Timeout):
                pass
            
            time.sleep(1)
        
        print("Backend server failed to start within 30 seconds")
        return None

    except Exception as e:
        print(f"Critical error starting backend: {str(e)}")
        return None

def start_frontend():
    print("Starting frontend...")
    
    # Check if frontend app exists
    frontend_path = os.path.join(os.getcwd(), "frontend", "app.py")
    if not os.path.exists(frontend_path):
        print(f"Error: Frontend file not found at {frontend_path}")
        print("Please make sure the frontend/app.py file exists.")
        return None
        
    try:
        if os.name == "nt":  # Windows
            # Add more verbose output to debug the issue
            print("Executing: .venv\\Scripts\\streamlit run frontend\\app.py")
            # Add --server.headless=true to prevent Streamlit from opening browser automatically
            frontend_process = subprocess.Popen(
                [".venv\\Scripts\\streamlit", "run", "frontend\\app.py", "--server.headless=true"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Check if process started successfully
            if frontend_process.poll() is not None:
                print(f"Frontend process exited immediately with code: {frontend_process.returncode}")
                stderr = frontend_process.stderr.read().decode('utf-8') if frontend_process and frontend_process.stderr else "No error output available"
                print(f"Error output: {stderr}")
                return None
        else:  # Unix/Linux
            frontend_process = subprocess.Popen(
                [".venv/bin/streamlit", "run", "frontend/app.py", "--server.headless=true"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        return frontend_process
    except Exception as e:
        print(f"Error starting frontend: {e}")
        return None

def import_data():
    print("Checking if data needs to be imported...")
    # Check if data is already imported
    try:
        from pymilvus import connections, Collection
        connections.connect("default", host="localhost", port="19530")
        collection = Collection("diseases")
        count = collection.num_entities
        if count > 0:
            print(f"Data already imported ({count} entities found)")
            return True
    except Exception as e:
        print(f"No existing data found: {e}")
    
    # Import data
    print("Importing data from XML...")
    if os.name == "nt":  # Windows
        # Around line 118-121, there's a syntax error with mismatched parentheses
        # The error is likely in a code block similar to this:
        
        # Original problematic code might look like:
        
        # subprocess.run(
        #     ["cmd", "/c", "something"],
        #     check=True
        # )
        
        # Fix by ensuring the brackets and parentheses match properly:
        subprocess.run(
            ["cmd", "/c", ".venv\\Scripts\\activate && python scripts\\data_importer.py"],
            check=True
        )
    else:  # Unix/Linux
        subprocess.run(
            ["/bin/bash", "-c", "source .venv/bin/activate && python scripts/data_importer.py"],
            check=True
        )
    return True

def main():
    if not check_python():
        return
    
    setup_environment()
    start_milvus()
    
    try:
        import_data()
        backend_process = start_backend()
        
        if backend_process is None:
            print("Failed to start backend server. Exiting...")
            subprocess.run(["docker-compose", "down"], check=True)
            return
            
        frontend_process = start_frontend()
        
        if frontend_process is None:
            print("Failed to start frontend. Exiting...")
            backend_process.terminate()
            subprocess.run(["docker-compose", "down"], check=True)
            return
        
        # Wait longer for services to start
        print("Waiting for services to start...")
        time.sleep(10)
        
        # Check if processes are still running
        if backend_process.poll() is not None:
            print(f"Backend process exited with code: {backend_process.returncode}")
            stderr = backend_process.stderr.read()  # Already text due to universal_newlines=True
            stdout = backend_process.stdout.read()  # Already text due to universal_newlines=True
            print(f"Backend error output: {stderr}")
            print(f"Backend standard output: {stdout}")
            frontend_process.terminate()
            subprocess.run(["docker-compose", "down"], check=True)
            return
            
        if frontend_process.poll() is not None:
            print(f"Frontend process exited with code: {frontend_process.returncode}")
            stderr = frontend_process.stderr.read()  # Already text due to universal_newlines=True
            stdout = frontend_process.stdout.read()  # Already text due to universal_newlines=True
            print(f"Frontend error output: {stderr}")
            print(f"Frontend standard output: {stdout}")
            backend_process.terminate()
            subprocess.run(["docker-compose", "down"], check=True)
            return
        
        # Open browser - only once
        print("\nApplication is running!")
        print("Frontend: http://localhost:8501")
        print("Backend: http://localhost:8000")
        print("\nOpening browser...")
        try:
            # Use a more controlled browser opening approach
            webbrowser.get().open("http://localhost:8501", new=1)
        except Exception as e:
            print(f"Could not automatically open browser: {e}")
            print("Please manually navigate to http://localhost:8501")
        
        print("\nPress Ctrl+C to stop the application")
        
        # Keep the script running and monitor processes
        try:
            while True:
                time.sleep(1)
                
                # Check if processes are still running
                if backend_process.poll() is not None:
                    print(f"Backend process exited with code: {backend_process.returncode}")
                    stderr = backend_process.stderr.read()  # Already text due to universal_newlines=True
                    print(f"Backend error output: {stderr}")
                    break
                    
                if frontend_process.poll() is not None:
                    print(f"Frontend process exited with code: {frontend_process.returncode}")
                    stderr = frontend_process.stderr.read()  # Already text due to universal_newlines=True
                    print(f"Frontend error output: {stderr}")
                    break
                    
        except KeyboardInterrupt:
            print("\nStopping application...")
        finally:
            if backend_process:
                backend_process.terminate()
            if frontend_process:
                frontend_process.terminate()
            subprocess.run(["docker-compose", "down"], check=True)
            print("Application stopped")
    
    except Exception as e:
        print(f"Error: {e}")
        subprocess.run(["docker-compose", "down"], check=True)

if __name__ == "__main__":
    main()