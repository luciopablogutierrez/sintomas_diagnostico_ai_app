from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

def get_mongodb_client():
    """Get MongoDB client instance"""
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    client = MongoClient(mongodb_uri)
    return client

def get_doctors_collection():
    """Get doctors collection from MongoDB"""
    client = get_mongodb_client()
    db = client.medichat
    return db.doctors