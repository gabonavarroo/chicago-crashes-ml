"""
Modelos Pydantic para la tabla vehicle_maneuvers.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CreateVehicleManeuver(BaseModel):
    """
    Schema para crear información de maniobra de un vehículo.
    
    Nota: La maniobra se asocia directamente a un vehículo existente.
    
    Validaciones:
        - vehicle_id: Debe existir en vehicle (requerido)
        - maneuver: Máximo 150 caracteres
    """
    vehicle_id: int = Field(
        ..., 
        gt=0,
        le = 99999999,
        description="ID del vehículo (debe existir en vehicle)"
    )
    maneuver: Optional[str] = Field(
        None, 
        max_length=150,
        description="Tipo de maniobra realizada por el vehículo"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "vehicle_id": 1,
                    "maneuver": "GOING STRAIGHT"
                },
                {
                    "vehicle_id": 2,
                    "maneuver": "TURNING LEFT"
                }
            ]
        }
    }


class ReadVehicleManeuver(BaseModel):
    """
    Schema para leer información de maniobra de un vehículo existente.
    """
    vehicle_id: int = Field(
        ..., 
        description="ID del vehículo"
    )
    maneuver: Optional[str] = Field(
        None,
        description="Tipo de maniobra realizada por el vehículo"
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "vehicle_id": 1,
                    "maneuver": "GOING STRAIGHT"
                },
                {
                    "vehicle_id": 2,
                    "maneuver": "TURNING LEFT"
                }
            ]
        }
    }


class UpdateVehicleManeuver(BaseModel):
    """
    Schema para actualizar información de maniobra de un vehículo.
    Todos los campos son opcionales.
    
    Nota: vehicle_id NO puede actualizarse (es PK)
    """
    maneuver: Optional[str] = Field(
        None, 
        max_length=150,
        description="Nuevo tipo de maniobra"
    )
