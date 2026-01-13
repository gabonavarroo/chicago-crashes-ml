"""
Modelos Pydantic para la tabla vehicle_violations.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CreateVehicleViolation(BaseModel):
    """
    Schema para crear violaciones de vehículo.
    
    Validaciones:
        - vehicle_id: Debe existir en la tabla vehicle (validado en router)
        - vehicle_defect: Máximo 100 caracteres
        - Booleanos: Acepta True/False, 1/0, "true"/"false", etc.
    
    Restricciones de negocio:
        - Solo puede existir UN registro de violaciones por vehículo
        - El vehículo debe existir ANTES de crear sus violaciones
    
    Ejemplos:
        {
            "vehicle_id": 1234567,
            "cmrc_veh_i": false,
            "exceed_speed_limit_i": true,
            "hazmat_present_i": false,
            "vehicle_defect": "BRAKES"
        }
    """
    vehicle_id: int = Field(
        ..., 
        description="ID del vehículo (debe existir en vehicle)"
    )
    cmrc_veh_i: Optional[bool] = Field(
        None,
        description="Indicador de vehículo comercial (acepta true/false, 1/0)"
    )
    exceed_speed_limit_i: Optional[bool] = Field(
        None,
        description="Indicador de exceso de límite de velocidad"
    )
    hazmat_present_i: Optional[bool] = Field(
        None,
        description="Indicador de materiales peligrosos presentes"
    )
    vehicle_defect: Optional[str] = Field(
        None, 
        max_length=100,
        description="Descripción del defecto del vehículo (máx 100 caracteres)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "vehicle_id": 1234567,
                    "cmrc_veh_i": False,
                    "exceed_speed_limit_i": True,
                    "hazmat_present_i": False,
                    "vehicle_defect": "BRAKES"
                },
                {
                    "vehicle_id": 9876543,
                    "cmrc_veh_i": 1,
                    "exceed_speed_limit_i": 0,
                    "hazmat_present_i": "false",
                    "vehicle_defect": "TIRES"
                }
            ]
        }
    }


class ReadVehicleViolation(BaseModel):
    """
    Schema para leer violaciones de vehículo.
    Incluye todos los campos de la tabla.
    """
    vehicle_id: int = Field(..., description="ID del vehículo")
    cmrc_veh_i: Optional[bool] = Field(None, description="Vehículo comercial")
    exceed_speed_limit_i: Optional[bool] = Field(None, description="Excedió límite de velocidad")
    hazmat_present_i: Optional[bool] = Field(None, description="Materiales peligrosos")
    vehicle_defect: Optional[str] = Field(None, description="Defecto del vehículo")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "vehicle_id": 1234567,
                    "cmrc_veh_i": False,
                    "exceed_speed_limit_i": True,
                    "hazmat_present_i": False,
                    "vehicle_defect": "BRAKES"
                }
            ]
        }
    }


class UpdateVehicleViolation(BaseModel):
    """
    Schema para actualizar violaciones de vehículo.
    Todos los campos son opcionales (solo se actualizan los proporcionados).
    
    Nota: vehicle_id NO puede actualizarse (es la PK)
    
    Ejemplos:
        {
            "exceed_speed_limit_i": false
        }
        
        {
            "vehicle_defect": "LIGHTS",
            "cmrc_veh_i": true
        }
    """
    cmrc_veh_i: Optional[bool] = None
    exceed_speed_limit_i: Optional[bool] = None
    hazmat_present_i: Optional[bool] = None
    vehicle_defect: Optional[str] = Field(None, max_length=100)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "exceed_speed_limit_i": False
                },
                {
                    "vehicle_defect": "LIGHTS",
                    "cmrc_veh_i": True
                }
            ]
        }
    }