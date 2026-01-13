"""
Utilidades para generación de IDs únicos en el sistema
"""
import hashlib
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text


def generate_crash_record_id(
    incident_date: datetime,
    latitude: float,
    longitude: float,
    street_no: int,
    street_name: str
) -> str:
    """
    Genera un crash_record_id único usando SHA-512.
    
    Formato: Hash de 128 caracteres en minúsculas de la concatenación:
    incident_date + latitude(6 decimales) + longitude(6 decimales) + street_no + street_name
    
    Args:
        incident_date: Fecha y hora del incidente
        latitude: Latitud (será acotada a 6 decimales)
        longitude: Longitud (será acotada a 6 decimales)
        street_no: Número de calle
        street_name: Nombre de calle
        
    Returns:
        String de 128 caracteres hexadecimales en minúsculas
    """
    # Formatear incident_date como string ISO
    date_str = incident_date.strftime("%Y-%m-%d %H:%M:%S")
    
    # Acotar coordenadas a 6 decimales
    lat_str = f"{latitude:.6f}"
    lon_str = f"{longitude:.6f}"
    
    # Concatenar todos los componentes
    components = f"{date_str}{lat_str}{lon_str}{street_no}{street_name}"
    
    # Generar hash SHA-512 (produce 128 caracteres hex)
    crash_id = hashlib.sha512(components.encode('utf-8')).hexdigest()
    
    return crash_id


def generate_vehicle_id(db: Session) -> int:
    """
    Genera el siguiente vehicle_id usando la secuencia de PostgreSQL.
    
    Args:
        db: Sesión de base de datos SQLAlchemy
        
    Returns:
        Siguiente valor de la secuencia vehicle_id
    """
    # Obtener el máximo vehicle_id actual
    result = db.execute(text("SELECT COALESCE(MAX(vehicle_id), 0) + 1 FROM vehicle"))
    next_id = result.scalar()
    return next_id


def generate_crash_unit_id(db: Session) -> int:
    """
    Genera el siguiente crash_unit_id.
    
    Args:
        db: Sesión de base de datos SQLAlchemy
        
    Returns:
        Siguiente valor para crash_unit_id
    """
    # Obtener el máximo crash_unit_id actual
    result = db.execute(text("SELECT COALESCE(MAX(crash_unit_id), 0) + 1 FROM vehicle"))
    next_id = result.scalar()
    return next_id


def generate_person_id(db: Session) -> str:
    """
    Genera el siguiente person_id en formato "Q" + 7 dígitos.
    
    Formato: Q0000001, Q0000002, ..., Q9999999
    
    Args:
        db: Sesión de base de datos SQLAlchemy
        
    Returns:
        String en formato Q + 7 dígitos con ceros a la izquierda
    """
    # Obtener el máximo número actual (extrayendo la parte numérica)
    result = db.execute(text("""
        SELECT COALESCE(MAX(CAST(SUBSTRING(person_id FROM 2) AS INTEGER)), 0) + 1 
        FROM people 
        WHERE person_id ~ '^Q[0-9]{7}$'
    """))
    next_num = result.scalar()
    
    # Validar que no exceda el límite de 7 dígitos
    if next_num > 9999999:
        raise ValueError("Se ha alcanzado el límite máximo de person_id (Q9999999)")
    
    # Formatear con ceros a la izquierda
    person_id = f"Q{next_num:07d}"
    
    return person_id


def truncate_coordinates(latitude: float, longitude: float, decimals: int = 6) -> tuple[float, float]:
    """
    Trunca coordenadas a un número específico de decimales.
    
    Args:
        latitude: Latitud original
        longitude: Longitud original
        decimals: Número de decimales (default: 6)
        
    Returns:
        Tupla (latitude_truncated, longitude_truncated)
    """
    factor = 10 ** decimals
    lat_truncated = int(latitude * factor) / factor
    lon_truncated = int(longitude * factor) / factor
    
    return lat_truncated, lon_truncated