"""
Router para la tabla crashes.
Implementa endpoints CRUD con generación automática de IDs y validaciones.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.crashes import CreateCrash, ReadCrash, UpdateCrash
from db.entities.crashes import Crash
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.id_generators import generate_crash_record_id, truncate_coordinates
from util.validators import (
    validate_coordinates, 
    validate_date_not_future, 
    validate_string_length,
    validate_non_negative
)


class CrashesRouter:
    """
    Router para gestionar crashes (accidentes de tráfico).
    
    Endpoints:
        GET /crashes - Lista todos los crashes (paginado)
        GET /crashes/{crash_record_id} - Obtiene un crash específico
        POST /crashes - Crea un nuevo crash (ID autogenerado)
        PUT /crashes/{crash_record_id} - Actualiza un crash
        DELETE /crashes/{crash_record_id} - Elimina un crash
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/crashes", tags=["Crashes"])

        # Registrar endpoints
        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadCrash],
            summary="Lista crashes",
            description="Obtiene una lista paginada de crashes"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadCrash,
            summary="Obtiene un crash",
            description="Obtiene un crash específico por su ID"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadCrash, 
            status_code=201,
            summary="Crea un crash",
            description="Crea un nuevo crash con ID autogenerado (hash SHA-512)"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadCrash,
            summary="Actualiza un crash",
            description="Actualiza los datos de un crash existente"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina un crash",
            description="Elimina un crash y todos sus registros relacionados (cascade)"
        )
    
    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """
        Lista todos los crashes con paginación.
        
        Args:
            skip: Número de registros a saltar (default: 0)
            limit: Número máximo de registros a devolver (default: 100, máx: 1000)
        
        Returns:
            Lista de crashes
        """
        db: Session = request.state.db_session
        self.logger.info(f"Listing crashes: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400, 
                detail="El límite máximo es 1000 registros y el minimo es 0"
            )
        
        crashes = db.query(Crash).offset(skip).limit(limit).all()
        return crashes

    def get(self, crash_record_id: str, request: Request):
        """
        Obtiene un crash específico por su ID.
        
        Args:
            crash_record_id: ID único del crash (hash SHA-512)
        
        Returns:
            Crash encontrado
        
        Raises:
            HTTPException 404: Si el crash no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Fetching crash with ID: {crash_record_id}")
        
        crash = db.query(Crash).get(crash_record_id)
        if not crash:
            raise HTTPException(
                status_code=404, 
                detail=f"Crash {crash_record_id} no encontrado"
            )
        
        return crash

    def create(self, data: CreateCrash, request: Request):
        """
        Crea un nuevo crash con ID autogenerado.
        
        El crash_record_id se genera automáticamente como hash SHA-512 de:
        incident_date + latitude (6 dec) + longitude (6 dec) + street_no + street_name
        
        Args:
            data: Datos del crash a crear
        
        Returns:
            Crash creado con su crash_record_id generado
        
        Raises:
            HTTPException 400: Si los datos son inválidos
            HTTPException 409: Si ya existe un crash con los mismos atributos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating new crash")
        
        try:
            # Validación 1: Coordenadas en rango válido
            validate_coordinates(data.latitude, data.longitude)
            
            # Validación 2: Fecha no futura
            validate_date_not_future(data.incident_date, "incident_date")
            
            # Validación 3: Longitud de strings
            if data.street_name:
                validate_string_length(data.street_name, 255, "street_name")
            
            # Validación 4: street_no no negativo
            if data.street_no is not None:
                validate_non_negative(data.street_no, "street_no")

            # Truncar coordenadas a 6 decimales para consistencia
            lat_truncated, lon_truncated = truncate_coordinates(
                data.latitude, 
                data.longitude
            )
            
            # Generar crash_record_id automáticamente
            crash_record_id = generate_crash_record_id(
                incident_date=data.incident_date,
                latitude=lat_truncated,
                longitude=lon_truncated,
                street_no=data.street_no if data.street_no is not None else 0,
                street_name=data.street_name or ""
            )
            
            self.logger.info(f"Generated crash_record_id: {crash_record_id}")
            
            # Verificar si ya existe (duplicado)
            existing = db.query(Crash).get(crash_record_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Ya existe un crash con estos atributos. "
                        f"ID: {crash_record_id}"
                    )
                )
            
            # Crear el nuevo crash
            new_crash = Crash(
                crash_record_id=crash_record_id,
                incident_date=data.incident_date,
                latitude=lat_truncated,
                longitude=lon_truncated,
                street_no=data.street_no,
                street_name=data.street_name
            )
            
            db.add(new_crash)
            db.flush()
            
            self.logger.info(f"Created crash with ID: {crash_record_id}")
            return new_crash
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating crash: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating crash: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, crash_record_id: str, data: UpdateCrash, request: Request):
        """
        Actualiza un crash existente.
        
        Args:
            crash_record_id: ID del crash a actualizar
            data: Nuevos datos (solo se actualizan los campos proporcionados)
        
        Returns:
            Crash actualizado
        
        Raises:
            HTTPException 404: Si el crash no existe
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Updating crash {crash_record_id}")
        
        try:
            crash = db.query(Crash).get(crash_record_id)
            if not crash:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Crash {crash_record_id} no encontrado"
                )
            
            # Obtener solo los campos que fueron proporcionados
            update_data = data.model_dump(exclude_unset=True)
            
            # Validaciones para campos actualizados
            if 'latitude' in update_data or 'longitude' in update_data:
                lat = update_data.get('latitude', crash.latitude)
                lon = update_data.get('longitude', crash.longitude)
                validate_coordinates(lat, lon)
            
            if 'incident_date' in update_data:
                validate_date_not_future(
                    update_data['incident_date'], 
                    "incident_date"
                )
            
            if 'street_no' in update_data and update_data['street_no'] is not None:
                validate_non_negative(update_data['street_no'], "street_no")
            
            if 'street_name' in update_data and update_data['street_name']:
                validate_string_length(
                    update_data['street_name'], 
                    255, 
                    "street_name"
                )
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(crash, key, value)
            
            db.flush()
            self.logger.info(f"Updated crash {crash_record_id}")
            return crash
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating crash: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating crash: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, crash_record_id: str, request: Request):
        """
        Elimina un crash.
        
        Nota: Esto eliminará en cascada todos los registros relacionados:
        - crash_circumstances
        - crash_injuries
        - crash_classification
        - vehicles asociados
        
        Args:
            crash_record_id: ID del crash a eliminar
        
        Returns:
            Mensaje de confirmación
        
        Raises:
            HTTPException 404: Si el crash no existe
            HTTPException 400: Si hay restricciones de integridad
        """
        db: Session = request.state.db_session
        self.logger.info(f"Deleting crash {crash_record_id}")
        
        try:
            crash = db.query(Crash).get(crash_record_id)
            if not crash:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Crash {crash_record_id} no encontrado"
                )
            
            db.delete(crash)
            db.flush()
            
            self.logger.info(f"Deleted crash {crash_record_id}")
            return {
                "message": f"Crash {crash_record_id} eliminado exitosamente",
                "crash_record_id": crash_record_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting crash: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se puede eliminar el crash porque tiene registros "
                    "relacionados que no permiten eliminación en cascada"
                )
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting crash: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )