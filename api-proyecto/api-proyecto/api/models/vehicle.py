from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional


class CreateVehicle(BaseModel):
    """
    Modelo para crear un nuevo vehículo.
    vehicle_id y crash_unit_id se generan automáticamente.
    """
    crash_record_id: str = Field(..., description="ID del crash al que pertenece")
    unit_no: Optional[int] = Field(None, ge=0, description="Número de unidad")
    unit_type: Optional[str] = Field(None, max_length=30, description="Tipo de unidad")
    num_passengers: Optional[int] = Field(None, ge=0, description="Número de pasajeros")
    vehicle_year: Optional[int] = Field(None, ge=1900, description="Año del vehículo")
    make: Optional[str] = Field(None, max_length=200, description="Marca del vehículo")
    model: Optional[str] = Field(None, max_length=200, description="Modelo del vehículo")
    vehicle_type: Optional[str] = Field(None, max_length=200, description="Tipo de vehículo")

    @field_validator('vehicle_year')
    @classmethod
    def validate_year(cls, v):
        if v is not None:
            current_year = datetime.now().year
            if v > current_year + 1:
                raise ValueError(f'El año del vehículo no puede ser mayor a {current_year + 1}')
        return v


class ReadVehicle(BaseModel):
    """
    Modelo para leer un vehículo existente.
    Incluye vehicle_id y crash_unit_id generados.
    """
    vehicle_id: int = Field(..., description="ID único del vehículo (generado automáticamente)")
    crash_unit_id: int = Field(..., description="ID de la unidad de crash (generado automáticamente)")
    crash_record_id: str = Field(..., description="ID del crash al que pertenece")
    unit_no: Optional[int] = None
    unit_type: Optional[str] = None
    num_passengers: Optional[int] = None
    vehicle_year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    vehicle_type: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateVehicle(BaseModel):
    """
    Modelo para actualizar un vehículo existente.
    Todos los campos son opcionales excepto los IDs.
    """
    crash_record_id: Optional[str] = None
    unit_no: Optional[int] = Field(None, ge=0)
    unit_type: Optional[str] = Field(None, max_length=30)
    num_passengers: Optional[int] = Field(None, ge=0)
    vehicle_year: Optional[int] = Field(None, ge=1900)
    make: Optional[str] = Field(None, max_length=200)
    model: Optional[str] = Field(None, max_length=200)
    vehicle_type: Optional[str] = Field(None, max_length=200)

    @field_validator('vehicle_year')
    @classmethod
    def validate_year(cls, v):
        if v is not None:
            current_year = datetime.now().year
            if v > current_year + 1:
                raise ValueError(f'El año del vehículo no puede ser mayor a {current_year + 1}')
