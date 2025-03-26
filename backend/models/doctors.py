from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from passlib.context import CryptContext

# Configuración del hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DoctorBase(BaseModel):
    username: str
    full_name: str
    email: str
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    active: bool = True

class DoctorCreate(DoctorBase):
    password: str

class DoctorUpdate(DoctorBase):
    password: Optional[str] = None

class DoctorInDB(DoctorBase):
    id: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)