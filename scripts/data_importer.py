import os
import sys
import subprocess

# First, check and install basic dependencies
def install_package(package):
    print(f"Installing {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Check for basic dependencies first
try:
    import xmltodict
    print("xmltodict is already installed")
except ImportError:
    install_package("xmltodict")
    import xmltodict

try:
    from dotenv import load_dotenv
    print("python-dotenv is already installed")
except ImportError:
    install_package("python-dotenv")
    from dotenv import load_dotenv

import json
import requests

load_dotenv()

def main():
    print("Starting data import process...")
    
    # Check if XML file exists
    xml_path = os.path.join(os.getcwd(), "ORPHAnomenclature_es_2024.xml")
    if not os.path.exists(xml_path):
        print(f"Error: XML file not found at {xml_path}")
        print("Please download the ORPHA nomenclature XML file and place it in the project root directory.")
        print("\nYou can download the file from: https://www.orphadata.com/data/xml/")
        print("Or you can use the direct link: https://www.orphadata.com/data/xml/es_product1.xml")
        
        # Ask if user wants to download the file
        try:
            response = input("\nWould you like to download the file now? (y/n): ")
            if response.lower() == 'y':
                print("Downloading ORPHA nomenclature XML file...")
                try:
                    # Download the file
                    url = "https://www.orphadata.com/data/xml/es_product1.xml"
                    r = requests.get(url, stream=True)
                    r.raise_for_status()
                    
                    with open(xml_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    print(f"File downloaded successfully to {xml_path}")
                except Exception as e:
                    print(f"Error downloading file: {e}")
                    return create_sample_data()
            else:
                return create_sample_data()
        except Exception:
            return create_sample_data()
    
    # Try to install missing dependencies
    try:
        print("Checking and installing required dependencies...")
        import importlib
        
        # Check for pymilvus
        try:
            importlib.import_module('pymilvus')
            print("pymilvus is already installed")
        except ImportError:
            print("Installing pymilvus...")
            install_package("pymilvus")
        
        # Check for sentence_transformers
        try:
            importlib.import_module('sentence_transformers')
            print("sentence_transformers is already installed")
        except ImportError:
            print("Installing sentence_transformers...")
            install_package("sentence_transformers")
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        print("Please install the required dependencies manually:")
        print("pip install pymilvus sentence-transformers")
    
    # Now try to import the modules
    try:
        from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Falling back to local file storage since Milvus connection failed")
        
        # Process XML and save to local JSON as fallback
        try:
            process_xml_to_local_json(xml_path)
            return True
        except Exception as e:
            print(f"Error in fallback processing: {e}")
            return False
    
    # Connect to Milvus
    try:
        print("Connecting to Milvus...")
        connections.connect(
            alias="default", 
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=os.getenv("MILVUS_PORT", "19530")
        )
        
        # Check if collection exists and create if not
        collection_name = "diseases"
        
        if utility.has_collection(collection_name):
            print(f"Collection '{collection_name}' already exists")
            collection = Collection(collection_name)
            return True
        
        # Define fields for the collection
        print("Creating collection schema...")
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="code", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="symptoms", dtype=DataType.VARCHAR, max_length=10000),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=10000),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768)
        ]
        
        schema = CollectionSchema(fields, "Disease collection for medical diagnosis")
        collection = Collection(collection_name, schema)
    except Exception as e:
        print(f"Error connecting to Milvus: {e}")
        print("Falling back to local file storage since Milvus connection failed")
        
        # Process XML and save to local JSON as fallback
        try:
            process_xml_to_local_json(xml_path)
            return True
        except Exception as e:
            print(f"Error in fallback processing: {e}")
            return False
    
    try:
        # Process XML file
        print(f"Processing XML file: {xml_path}")
        diseases = process_xml(xml_path)
        
        if not diseases:
            print("No diseases found in the XML file")
            return False
        
        print(f"Processed {len(diseases)} diseases")
        
        # Generate embeddings
        print("Generating embeddings...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        embeddings = []
        for disease in diseases:
            text = f"{disease['name']} {disease['symptoms']} {disease['description']}"
            embedding = model.encode(text)
            embeddings.append(embedding)
        
        # Create an IVF_FLAT index for the embeddings
        print("Creating index...")
        # After creating the collection and before inserting data
        # Make sure to create the index
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        print("Index created successfully")
        
        # Import data to Milvus
        print("Importing data to Milvus...")
        
        # Prepare data for insertion
        entities = [
            [disease['code'] for disease in diseases],
            [disease['name'] for disease in diseases],
            [disease['symptoms'] for disease in diseases],
            [disease['description'] for disease in diseases],
            embeddings
        ]
        
        # Insert data
        collection.insert(entities)
        collection.flush()
        print(f"Imported {len(diseases)} diseases to Milvus")
        
        return True
    except Exception as e:
        print(f"Error during data import: {e}")
        
        # Fallback to local storage
        print("Falling back to local file storage")
        try:
            process_xml_to_local_json(xml_path)
            return True
        except Exception as e:
            print(f"Error in fallback processing: {e}")
            return False

def create_sample_data():
    """Create sample data for testing when XML file is not available"""
    print("\nCreating sample disease data for testing...")
    
    # Create sample diseases
    sample_diseases = [
        {
            "code": "ORPHA:166024",
            "name": "Síndrome de Marfan",
            "symptoms": "Aracnodactilia, Escoliosis, Hiperlaxitud articular, Prolapso de la válvula mitral, Dilatación aórtica",
            "description": "El síndrome de Marfan es un trastorno sistémico del tejido conectivo, caracterizado por una combinación variable de manifestaciones cardiovasculares, músculo-esqueléticas, oftalmológicas y pulmonares."
        },
        {
            "code": "ORPHA:98896",
            "name": "Enfermedad de Huntington",
            "symptoms": "Corea, Deterioro cognitivo, Trastornos psiquiátricos, Distonía, Rigidez",
            "description": "La enfermedad de Huntington es un trastorno neurodegenerativo progresivo caracterizado por movimientos coreicos involuntarios, deterioro cognitivo y trastornos psiquiátricos."
        },
        {
            "code": "ORPHA:586",
            "name": "Hemofilia A",
            "symptoms": "Hemartrosis, Hematomas, Sangrado prolongado, Hemorragia intracraneal, Hematuria",
            "description": "La hemofilia A es un trastorno hemorrágico hereditario causado por la deficiencia del factor VIII de coagulación."
        },
        {
            "code": "ORPHA:93552",
            "name": "Esclerosis lateral amiotrófica",
            "symptoms": "Debilidad muscular, Fasciculaciones, Espasticidad, Disfagia, Disartria",
            "description": "La esclerosis lateral amiotrófica es una enfermedad neurodegenerativa caracterizada por la degeneración progresiva de las neuronas motoras en la corteza cerebral, tronco del encéfalo y médula espinal."
        },
        {
            "code": "ORPHA:98473",
            "name": "Síndrome de Guillain-Barré",
            "symptoms": "Debilidad muscular ascendente, Arreflexia, Parestesias, Dolor, Disfunción autonómica",
            "description": "El síndrome de Guillain-Barré es una polineuropatía inflamatoria aguda caracterizada por debilidad muscular rápidamente progresiva que comienza en las extremidades inferiores y asciende."
        }
    ]
    
    # Save to JSON file
    output_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "diseases.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sample_diseases, f, ensure_ascii=False, indent=2)
    
    print(f"Created sample data with {len(sample_diseases)} diseases")
    print(f"Saved to {output_file}")
    return True

def process_xml(xml_path):
    with open(xml_path, 'r', encoding='utf-8') as file:
        doc = xmltodict.parse(file.read())
    
    diseases = []
    # Adjust the path based on the actual structure of your XML
    disorders = doc['JDBOR']['DisorderList']['Disorder']
    
    if not isinstance(disorders, list):
        disorders = [disorders]
    
    for disorder in disorders:
        try:
            # Extract symptoms if available
            symptoms = []
            if 'ClinicalSignList' in disorder and disorder['ClinicalSignList'] is not None:
                clinical_signs = disorder['ClinicalSignList'].get('ClinicalSign', [])
                if not isinstance(clinical_signs, list):
                    clinical_signs = [clinical_signs]
                
                for sign in clinical_signs:
                    if isinstance(sign, dict) and 'Name' in sign:
                        symptoms.append(sign['Name'].get('#text', ''))
            
            # Extract description if available
            description = ""
            if 'Definition' in disorder and disorder['Definition'] is not None:
                description = disorder['Definition'].get('#text', '')
            
            disease = {
                "code": disorder.get('OrphaCode', ''),
                "name": disorder.get('Name', {}).get('#text', ''),
                "symptoms": ", ".join(symptoms),
                "description": description
            }
            diseases.append(disease)
        except Exception as e:
            print(f"Error processing disorder: {e}")
    
    return diseases

def process_xml_to_local_json(xml_path):
    """Process XML and save to local JSON file as fallback when Milvus is unavailable"""
    print("Processing XML to local JSON file...")
    
    diseases = process_xml(xml_path)
    
    if not diseases:
        print("No diseases found in the XML file")
        return False
    
    # Save to JSON file
    output_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "diseases.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(diseases, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(diseases)} diseases to {output_file}")
    return True

if __name__ == "__main__":
    try:
        install_package("requests")
        import requests
    except Exception:
        pass
    
    success = main()
    if not success:
        sys.exit(1)