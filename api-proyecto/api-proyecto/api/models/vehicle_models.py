"""
Modelos Pydantic para la tabla vehicle_specs.
Define los schemas de validación para CREATE, READ y UPDATE.

Nota: El archivo se llama vehicle_models.py pero la tabla es vehicle_specs
(por razones históricas del proyecto).
"""
from pydantic import BaseModel, Field
from typing import Optional


class CreateVehicleModels(BaseModel):
    """
    Schema para crear especificaciones de vehículo.
    
    Validaciones:
        - vehicle_id: Debe existir en la tabla vehicle
        - Strings: Máximo 150 caracteres cada uno
    """
    vehicle_id: int = Field(
        ..., 
        description="ID del vehículo (debe existir en vehicle)"
    )
    vehicle_use: Optional[str] = Field(
        None, 
        max_length=150, 
        description="Uso del vehículo (COMMERCIAL, PERSONAL, etc.)"
    )
    vehicle_config: Optional[str] = Field(
        None, 
        max_length=150, 
        description="Configuración del vehículo"
    )
    cargo_body_type: Optional[str] = Field(
        None, 
        max_length=150, 
        description="Tipo de carrocería de carga"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "vehicle_id": 208730,
                    "vehicle_use": "COMMERCIAL",
                    "vehicle_config": "TRUCK",
                    "cargo_body_type": "VAN/ENCLOSED BOX"
                }
            ]
        }
    }


class ReadVehicleModels(BaseModel):
    """
    Schema para leer especificaciones de vehículo.
    Incluye todos los campos de la tabla vehicle_specs.
    """
    vehicle_id: int
    vehicle_use: Optional[str] = None
    vehicle_config: Optional[str] = None
    cargo_body_type: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "vehicle_id": 208730,
                    "vehicle_use": "COMMERCIAL",
                    "vehicle_config": "TRUCK",
                    "cargo_body_type": "VAN/ENCLOSED BOX"
                }
            ]
        }
    }


class UpdateVehicleModels(BaseModel):
    """
    Schema para actualizar especificaciones de vehículo.
    Todos los campos son opcionales (solo se actualizan los proporcionados).
    
    Nota: vehicle_id NO puede actualizarse (es la PK)
    """
    vehicle_use: Optional[str] = Field(None, max_length=150)
    vehicle_config: Optional[str] = Field(None, max_length=150)
    cargo_body_type: Optional[str] = Field(None, max_length=150)