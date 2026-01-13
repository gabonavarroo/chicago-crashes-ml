"""
Validadores de datos para la API
"""
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from fastapi import HTTPException


def validate_coordinates(latitude: float, longitude: float) -> None:
    """
    Valida que las coordenadas estén en rangos válidos.
    
    Args:
        latitude: Latitud a validar
        longitude: Longitud a validar
        
    Raises:
        HTTPException: Si las coordenadas están fuera de rango
    """
    if not (-90 <= latitude <= 90):
        raise HTTPException(
            status_code=400,
            detail=f"Latitud inválida: {latitude}. Debe estar entre -90 y 90"
        )
    
    if not (-180 <= longitude <= 180):
        raise HTTPException(
            status_code=400,
            detail=f"Longitud inválida: {longitude}. Debe estar entre -180 y 180"
        )


def validate_non_negative(value: int | float, field_name: str) -> None:
    """
    Valida que un valor no sea negativo.
    
    Args:
        value: Valor a validar
        field_name: Nombre del campo (para el mensaje de error)
        
    Raises:
        HTTPException: Si el valor es negativo
    """
    if value is not None and value < 0:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} no puede ser negativo: {value}"
        )


def validate_date_not_future(date: datetime, field_name: str = "fecha") -> None:
    """
    Valida que una fecha no sea futura.
    
    Args:
        date: Fecha a validar
        field_name: Nombre del campo (para el mensaje de error)
        
    Raises:
        HTTPException: Si la fecha es futura
    """
    if date and date > datetime.now():
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} no puede ser futura: {date}"
        )


def validate_age(age: int) -> None:
    """
    Valida que la edad esté en un rango razonable.
    
    Args:
        age: Edad a validar
        
    Raises:
        HTTPException: Si la edad está fuera de rango
    """
    if age is not None:
        if age < 0:
            raise HTTPException(status_code=400, detail=f"Edad no puede ser negativa: {age}")
        if age > 120:
            raise HTTPException(status_code=400, detail=f"Edad fuera de rango razonable: {age}")


def validate_vehicle_year(year: int) -> None:
    """
    Valida que el año del vehículo esté en un rango razonable.
    
    Args:
        year: Año a validar
        
    Raises:
        HTTPException: Si el año está fuera de rango
    """
    if year is not None:
        current_year = datetime.now().year
        if year < 1900:
            raise HTTPException(
                status_code=400,
                detail=f"Año del vehículo no puede ser menor a 1900: {year}"
            )
        if year > current_year + 1:
            raise HTTPException(
                status_code=400,
                detail=f"Año del vehículo no puede ser mayor a {current_year + 1}: {year}"
            )


def validate_string_length(value: str, max_length: int, field_name: str) -> None:
    """
    Valida la longitud máxima de un string.
    
    Args:
        value: String a validar
        max_length: Longitud máxima permitida
        field_name: Nombre del campo (para el mensaje de error)
        
    Raises:
        HTTPException: Si el string excede la longitud máxima
    """
    if value and len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} excede la longitud máxima de {max_length} caracteres: {len(value)}"
        )


def validate_foreign_key_exists(
    db: Session,
    table_name: str,
    column_name: str,
    value: Any
) -> None:
    """
    Valida que una foreign key exista en la tabla referenciada.
    
    Args:
        db: Sesión de base de datos
        table_name: Nombre de la tabla a verificar
        column_name: Nombre de la columna
        value: Valor a buscar
        
    Raises:
        HTTPException: Si el valor no existe en la tabla
    """
    from sqlalchemy import text
    
    if value is None:
        return  # Permitir NULL si el campo lo permite
    
    query = text(f"SELECT 1 FROM {table_name} WHERE {column_name} = :value LIMIT 1")
    result = db.execute(query, {"value": value}).fetchone()
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"{column_name} '{value}' no existe en la tabla {table_name}"
        )


def normalize_boolean(value: Any) -> bool | None:
    """
    Normaliza diferentes representaciones de booleanos.
    
    Acepta: True/False, 1/0, "true"/"false", "TRUE"/"FALSE", "1"/"0"
    
    Args:
        value: Valor a normalizar
        
    Returns:
        Booleano normalizado o None si el valor es None
        
    Raises:
        HTTPException: Si el valor no puede ser convertido a booleano
    """
    if value is None:
        return None
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        if value in (0, 1):
            return bool(value)
        raise HTTPException(
            status_code=400,
            detail=f"Valor numérico inválido para booleano: {value}. Use 0 o 1"
        )
    
    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ("true", "1", "yes"):
            return True
        if value_lower in ("false", "0", "no"):
            return False
        raise HTTPException(
            status_code=400,
            detail=f"Valor de string inválido para booleano: {value}. Use 'true'/'false' o '1'/'0'"
        )
    
    raise HTTPException(
        status_code=400,
        detail=f"Tipo de dato inválido para booleano: {type(value)}"
    )