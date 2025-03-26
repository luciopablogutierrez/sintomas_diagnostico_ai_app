from fastapi import APIRouter, HTTPException, Depends
from typing import List
from services.doctors import DoctorService
from models.doctors import DoctorCreate, DoctorUpdate, DoctorInDB

router = APIRouter()
doctor_service = DoctorService()

@router.post("/", response_model=DoctorInDB)
async def create_doctor(doctor: DoctorCreate):
    """Create a new doctor"""
    db_doctor = doctor_service.get_doctor_by_username(doctor.username)
    if db_doctor:
        raise HTTPException(status_code=400, detail="Username already registered")
    return doctor_service.create_doctor(doctor)

@router.get("/", response_model=List[DoctorInDB])
async def read_doctors():
    """Get all doctors"""
    return doctor_service.get_all_doctors()

@router.get("/{doctor_id}", response_model=DoctorInDB)
async def read_doctor(doctor_id: str):
    """Get a specific doctor by ID"""
    db_doctor = doctor_service.get_doctor_by_id(doctor_id)
    if db_doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return db_doctor

@router.put("/{doctor_id}", response_model=DoctorInDB)
async def update_doctor(doctor_id: str, doctor: DoctorUpdate):
    """Update a doctor"""
    db_doctor = doctor_service.get_doctor_by_id(doctor_id)
    if db_doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor_service.update_doctor(doctor_id, doctor)

@router.delete("/{doctor_id}", response_model=dict)
async def delete_doctor(doctor_id: str):
    """Delete a doctor"""
    db_doctor = doctor_service.get_doctor_by_id(doctor_id)
    if db_doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    success = doctor_service.delete_doctor(doctor_id)
    if success:
        return {"message": "Doctor deleted successfully"}
    raise HTTPException(status_code=500, detail="Failed to delete doctor")