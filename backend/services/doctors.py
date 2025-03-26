from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from mongodb.connection import get_doctors_collection
from models.doctors import DoctorCreate, DoctorUpdate, DoctorInDB, get_password_hash, verify_password

class DoctorService:
    def __init__(self):
        self.collection = get_doctors_collection()
    
    def create_doctor(self, doctor: DoctorCreate) -> DoctorInDB:
        """Create a new doctor"""
        doctor_dict = doctor.dict()
        hashed_password = get_password_hash(doctor_dict.pop('password'))
        
        doctor_in_db = {
            **doctor_dict,
            'hashed_password': hashed_password,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = self.collection.insert_one(doctor_in_db)
        doctor_in_db['id'] = str(result.inserted_id)
        
        return DoctorInDB(**doctor_in_db)
    
    def get_doctor_by_username(self, username: str) -> Optional[DoctorInDB]:
        """Get a doctor by username"""
        doctor = self.collection.find_one({'username': username})
        if doctor:
            doctor['id'] = str(doctor.pop('_id'))
            return DoctorInDB(**doctor)
        return None
    
    def get_doctor_by_id(self, doctor_id: str) -> Optional[DoctorInDB]:
        """Get a doctor by ID"""
        doctor = self.collection.find_one({'_id': ObjectId(doctor_id)})
        if doctor:
            doctor['id'] = str(doctor.pop('_id'))
            return DoctorInDB(**doctor)
        return None
    
    def get_all_doctors(self) -> List[DoctorInDB]:
        """Get all doctors"""
        doctors = []
        for doc in self.collection.find():
            doc['id'] = str(doc.pop('_id'))
            doctors.append(DoctorInDB(**doc))
        return doctors
    
    def update_doctor(self, doctor_id: str, doctor_update: DoctorUpdate) -> Optional[DoctorInDB]:
        """Update a doctor"""
        update_data = doctor_update.dict(exclude_unset=True)
        
        if 'password' in update_data:
            update_data['hashed_password'] = get_password_hash(update_data.pop('password'))
        
        update_data['updated_at'] = datetime.utcnow()
        
        result = self.collection.update_one(
            {'_id': ObjectId(doctor_id)},
            {'$set': update_data}
        )
        
        if result.modified_count:
            return self.get_doctor_by_id(doctor_id)
        return None
    
    def delete_doctor(self, doctor_id: str) -> bool:
        """Delete a doctor"""
        result = self.collection.delete_one({'_id': ObjectId(doctor_id)})
        return result.deleted_count > 0
    
    def authenticate_doctor(self, username: str, password: str) -> Optional[DoctorInDB]:
        """Authenticate a doctor"""
        doctor = self.get_doctor_by_username(username)
        if doctor and verify_password(password, doctor.hashed_password):
            return doctor
        return None