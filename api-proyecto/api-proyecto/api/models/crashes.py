"""
Modelos Pydantic para la tabla crashes.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional


class CreateCrash(BaseModel):
    """
    Schema para crear un nuevo crash.
    
    Nota: crash_record_id NO se incluye porque se genera automáticamente
    a partir del hash SHA-512 de los atributos.
    
    Validaciones:
        - incident_date: No puede ser futura
        - latitude: Rango -90 a 90
        - longitude: Rango -180 a 180
        - street_no: No negativo
        - street_name: Máximo 255 caracteres
    """
    incident_date: datetime = Field(
        ..., 
        description="Fecha y hora del incidente (no puede ser futura)"
    )
    latitude: float = Field(
        ..., 
        ge=-90, 
        le=90, 
        description="Latitud del crash (será truncada a 6 decimales)"
    )
    longitude: float = Field(
        ..., 
        ge=-180, 
        le=180, 
        description="Longitud del crash (será truncada a 6 decimales)"
    )
    street_no: Optional[int] = Field(
        None, 
        ge=0, 
        le=9999999,
        description="Número de calle"
    )
    street_name: Optional[str] = Field(
        None, 
        max_length=255, 
        description="Nombre de calle"
    )

    @field_validator('incident_date')
    @classmethod
    def validate_date_not_future(cls, v):
        """Valida que la fecha del incidente no sea futura."""
        if v > datetime.now():
            raise ValueError('La fecha del incidente no puede ser futura')
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "incident_date": "2024-01-15T14:30:00",
                    "latitude": 41.8781,
                    "longitude": -87.6298,
                    "street_no": "1234",
                    "street_name": "N MICHIGAN AVE"
                }
            ]
        }
    }

class ReadCrash(CreateCrash):
    pass


class ReadCrash(BaseModel):
    """
    Schema para leer un crash existente.
    Incluye el crash_record_id generado automáticamente.
    """
    crash_record_id: str = Field(
        ..., 
        description="ID único del crash (hash SHA-512 de 128 caracteres)"
    )
    incident_date: Optional[datetime] = Field(
        None, 
        description="Fecha y hora del incidente"
    )
    latitude: Optional[float] = Field(
        None, 
        description="Latitud del crash"
    )
    longitude: Optional[float] = Field(
        None, 
        description="Longitud del crash"
    )
    street_no: Optional[int] = Field(
        None, 
        description="Número de calle"
    )
    street_name: Optional[str] = Field(
        None, 
        description="Nombre de calle"
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "incident_date": "2024-01-15T14:30:00",
                    "latitude": 41.878100,
                    "longitude": -87.629800,
                    "street_no": "1234",
                    "street_name": "N MICHIGAN AVE"
                }
            ]
        }
    }


class UpdateCrash(BaseModel):
    """
    Schema para actualizar un crash existente.
    Todos los campos son opcionales.
    
    Nota: crash_record_id NO puede actualizarse (es PK)
    """
    incident_date: Optional[datetime] = Field(
        None, 
        description="Nueva fecha y hora del incidente"
    )
    latitude: Optional[float] = Field(
        None, 
        ge=-90, 
        le=90, 
        description="Nueva latitud"
    )
    longitude: Optional[float] = Field(
        None, 
        ge=-180, 
        le=180, 
        description="Nueva longitud"
    )
    street_no: Optional[int] = Field(
        None, 
        ge=0, 
        le=9999999,
        description="Nuevo número de calle"
    )
    street_name: Optional[str] = Field(
        None, 
        max_length=255, 
        description="Nuevo nombre de calle"
    )

    @field_validator('incident_date')
    @classmethod
    def validate_date_not_future(cls, v):
        """Valida que la fecha del incidente no sea futura."""
        if v and v > datetime.now():
            raise ValueError('La fecha del incidente no puede ser futura')
        return v
