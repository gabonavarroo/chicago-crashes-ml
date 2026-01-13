"""
Modelos Pydantic para la tabla crash_circumstances.
Define los schemas de validación para CREATE, READ y UPDATE.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class CreateCrashCircumstances(BaseModel):
    """
    Schema para crear circunstancias de crash.
    
    Validaciones:
        - crash_record_id: Debe existir en crashes
        - lane_cnt: No negativo
        - num_units: No negativo
        - posted_speed_limit: No negativo
        - Longitudes máximas de strings
    """
    crash_record_id: str = Field(
        ..., 
        description="ID del crash (debe existir en crashes)"
    )
    traffic_control_device: Optional[str] = Field(
        None, 
        max_length=100,
        description="Dispositivo de control de tráfico"
    )
    device_condition: Optional[str] = Field(
        None, 
        max_length=100,
        description="Condición del dispositivo"
    )
    weather_condition: Optional[str] = Field(
        None, 
        max_length=100,
        description="Condición del clima (CLEAR, RAIN, SNOW, etc.)"
    )
    lighting_condition: Optional[str] = Field(
        None, 
        max_length=100,
        description="Condición de iluminación (DAYLIGHT, DARKNESS, etc.)"
    )
    lane_cnt: Optional[int] = Field(
        None, 
        ge=0,
        le=25,
        description="Número de carriles (no negativo)"
    )
    roadway_surface_cond: Optional[str] = Field(
        None, 
        max_length=100,
        description="Condición de la superficie de la carretera (DRY, WET, SNOW, etc.)"
    )
    road_defect: Optional[str] = Field(
        None, 
        max_length=100,
        description="Defecto de la carretera"
    )
    num_units: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Número de unidades/vehículos involucrados (no negativo)"
    )
    posted_speed_limit: Optional[int] = Field(
        None, 
        ge=0,
        le=500,
        description="Límite de velocidad publicado (no negativo, 0-500)"
    )
    intersection_related_i: Optional[bool] = Field(
        None,
        description="Indicador si el crash está relacionado con una intersección"
    )
    not_right_of_way_i: Optional[bool] = Field(
        None,
        description="Indicador si hay violación de derecho de paso"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "traffic_control_device": "TRAFFIC SIGNAL",
                    "device_condition": "FUNCTIONING PROPERLY",
                    "weather_condition": "CLEAR",
                    "lighting_condition": "DAYLIGHT",
                    "lane_cnt": 4,
                    "roadway_surface_cond": "DRY",
                    "road_defect": None,
                    "num_units": 2,
                    "posted_speed_limit": 30,
                    "intersection_related_i": True,
                    "not_right_of_way_i": False
                }
            ]
        }
    }


class ReadCrashCircumstances(BaseModel):
    """
    Schema para leer circunstancias de crash existentes.
    """
    crash_record_id: str = Field(
        ..., 
        description="ID del crash"
    )
    traffic_control_device: Optional[str] = Field(
        None, 
        description="Dispositivo de control de tráfico"
    )
    device_condition: Optional[str] = Field(
        None,
        description="Condición del dispositivo"
    )
    weather_condition: Optional[str] = Field(
        None,
        description="Condición del clima"
    )
    lighting_condition: Optional[str] = Field(
        None,
        description="Condición de iluminación"
    )
    lane_cnt: Optional[int] = Field(
        None,
        description="Número de carriles"
    )
    roadway_surface_cond: Optional[str] = Field(
        None,
        description="Condición de la superficie de la carretera"
    )
    road_defect: Optional[str] = Field(
        None,
        description="Defecto de la carretera"
    )
    num_units: Optional[int] = Field(
        None,
        description="Número de unidades/vehículos involucrados"
    )
    posted_speed_limit: Optional[int] = Field(
        None,
        description="Límite de velocidad publicado"
    )
    intersection_related_i: Optional[bool] = Field(
        None,
        description="Indicador si está relacionado con intersección"
    )
    not_right_of_way_i: Optional[bool] = Field(
        None,
        description="Indicador de violación de derecho de paso"
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "traffic_control_device": "TRAFFIC SIGNAL",
                    "device_condition": "FUNCTIONING PROPERLY",
                    "weather_condition": "CLEAR",
                    "lighting_condition": "DAYLIGHT",
                    "lane_cnt": 4,
                    "roadway_surface_cond": "DRY",
                    "road_defect": None,
                    "num_units": 2,
                    "posted_speed_limit": 30,
                    "intersection_related_i": True,
                    "not_right_of_way_i": False
                }
            ]
        }
    }


class UpdateCrashCircumstances(BaseModel):
    """
    Schema para actualizar circunstancias de crash.
    Todos los campos son opcionales.
    
    Nota: crash_record_id NO puede actualizarse (es PK)
    """
    traffic_control_device: Optional[str] = Field(
        None, 
        max_length=100,
        description="Nuevo dispositivo de control de tráfico"
    )
    device_condition: Optional[str] = Field(
        None, 
        max_length=100,
        description="Nueva condición del dispositivo"
    )
    weather_condition: Optional[str] = Field(
        None, 
        max_length=100,
        description="Nueva condición del clima"
    )
    lighting_condition: Optional[str] = Field(
        None, 
        max_length=100,
        description="Nueva condición de iluminación"
    )
    lane_cnt: Optional[int] = Field(
        None, 
        ge=0,
        le=25,
        description="Nuevo número de carriles"
    )
    roadway_surface_cond: Optional[str] = Field(
        None, 
        max_length=100,
        description="Nueva condición de la superficie"
    )
    road_defect: Optional[str] = Field(
        None, 
        max_length=100,
        description="Nuevo defecto de la carretera"
    )
    num_units: Optional[int] = Field(
        None, 
        ge=0,
        le=100,
        description="Nuevo número de unidades"
    )
    posted_speed_limit: Optional[int] = Field(
        None, 
        ge=0,
        le=500,
        description="Nuevo límite de velocidad"
    )
    intersection_related_i: Optional[bool] = Field(
        None,
        description="Nuevo indicador de intersección"
    )
    not_right_of_way_i: Optional[bool] = Field(
        None,
        description="Nuevo indicador de derecho de paso"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "crash_record_id": "000013b0123279411e0ec856dae95ab9f0851764350b7feaeb982c7707c6722066910e9391e60f45cec4b7a7a6643eeedb5de39e7245b03447a44c793680dc4b",
                    "traffic_control_device": "string",
                    "device_condition": "string",
                    "weather_condition": "string",
                    "lighting_condition": "string",
                    "lane_cnt": 1,
                    "roadway_surface_cond": "string",
                    "road_defect": None,
                    "num_units": 1,
                    "posted_speed_limit": 60,
                    "intersection_related_i": True,
                    "not_right_of_way_i": False
                }
            ]
        }
    }
