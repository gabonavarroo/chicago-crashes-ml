"""
Modelos Pydantic para la tabla driver_info.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class CreateDriverInfo(BaseModel):
    """
    Schema para crear información de conductor.
    
    Nota: person_id debe existir previamente en la tabla people.
    
    Validaciones:
        - person_id: Formato Q + 7 dígitos (ej: Q0001234)
        - bac_result_value: No negativo (0.0 - 1.0 típicamente)
        - Strings: Longitud máxima según DDL
        - cell_phone_use: Booleano (acepta True/False, 1/0, "true"/"false")
    """
    person_id: str = Field(
        ...,
        min_length=8,
        max_length=8,
        pattern=r'^Q\d{7}$',
        description="ID de la persona (debe existir en people, formato Q0000001)"
    )
    driver_action: Optional[str] = Field(
        None,
        max_length=50,
        description="Acción del conductor al momento del crash"
    )
    driver_vision: Optional[str] = Field(
        None,
        max_length=50,
        description="Condición de visión del conductor"
    )
    physical_condition: Optional[str] = Field(
        None,
        max_length=50,
        description="Condición física del conductor"
    )
    bac_result_value: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Nivel de alcohol en sangre (BAC), típicamente 0.0-1.0"
    )
    cell_phone_use: Optional[bool] = Field(
        None,
        description="Indicador de uso de celular (true/false)"
    )
    drivers_license_class: Optional[str] = Field(
        None,
        max_length=10,
        description="Clase de licencia de conducir"
    )

    @field_validator('bac_result_value')
    @classmethod
    def validate_bac_reasonable(cls, v):
        """Valida que el BAC esté en un rango razonable."""
        if v is not None and v < 0:
            raise ValueError('El nivel de alcohol en sangre no puede ser negativo')
        if v is not None and v > 1.0:
            # Advertencia pero no error: valores > 1.0 son posibles pero muy raros
            pass
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "person_id": "Q0001234",
                    "driver_action": "PROCEEDING STRAIGHT AHEAD",
                    "driver_vision": "NOT OBSCURED",
                    "physical_condition": "NORMAL",
                    "bac_result_value": 0.0,
                    "cell_phone_use": False,
                    "drivers_license_class": "C"
                }
            ]
        }
    }


class ReadDriverInfo(BaseModel):
    """
    Schema para leer información de conductor existente.
    """
    person_id: str
    driver_action: Optional[str] = None
    driver_vision: Optional[str] = None
    physical_condition: Optional[str] = None
    bac_result_value: Optional[float] = None
    cell_phone_use: Optional[bool] = None
    drivers_license_class: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "person_id": "Q0001234",
                    "driver_action": "PROCEEDING STRAIGHT AHEAD",
                    "driver_vision": "NOT OBSCURED",
                    "physical_condition": "NORMAL",
                    "bac_result_value": 0.0,
                    "cell_phone_use": False,
                    "drivers_license_class": "C"
                }
            ]
        }
    }


class UpdateDriverInfo(BaseModel):
    """
    Schema para actualizar información de conductor existente.
    Todos los campos son opcionales excepto person_id (no se puede cambiar).
    """
    driver_action: Optional[str] = Field(
        None,
        max_length=50
    )
    driver_vision: Optional[str] = Field(
        None,
        max_length=50
    )
    physical_condition: Optional[str] = Field(
        None,
        max_length=50
    )
    bac_result_value: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0
    )
    cell_phone_use: Optional[bool] = None
    drivers_license_class: Optional[str] = Field(
        None,
        max_length=10
    )

    @field_validator('bac_result_value')
    @classmethod
    def validate_bac_reasonable(cls, v):
        """Valida que el BAC esté en un rango razonable."""
        if v is not None and v < 0:
            raise ValueError('El nivel de alcohol en sangre no puede ser negativo')
        return v