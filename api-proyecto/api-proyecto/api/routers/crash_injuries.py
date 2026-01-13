"""
Router para la tabla crash_injuries.
Implementa endpoints CRUD con validaciones de lesiones.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.crash_injuries import CreateCrashInjuries, ReadCrashInjuries, UpdateCrashInjuries
from db.entities.crash_injuries import CrashInjuries
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import validate_foreign_key_exists


class CrashInjuriesRouter:
    """
    Router para gestionar información de lesiones en crashes.
    
    Endpoints:
        GET /crash_injuries - Lista información de lesiones (paginado)
        GET /crash_injuries/{crash_record_id} - Obtiene lesiones de un crash
        POST /crash_injuries - Crea información de lesiones de un crash
        PUT /crash_injuries/{crash_record_id} - Actualiza información de lesiones
        DELETE /crash_injuries/{crash_record_id} - Elimina información de lesiones
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/crash_injuries", tags=["Crash Injuries"])

        # Registrar endpoints
        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadCrashInjuries],
            summary="Lista información de lesiones",
            description="Obtiene una lista paginada de información de lesiones en crashes"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadCrashInjuries,
            summary="Obtiene lesiones de un crash",
            description="Obtiene la información de lesiones de un crash específico"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadCrashInjuries,
            status_code=201,
            summary="Crea información de lesiones",
            description="Crea un nuevo registro de lesiones para un crash existente"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadCrashInjuries,
            summary="Actualiza información de lesiones",
            description="Actualiza los datos de lesiones de un crash"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina información de lesiones",
            description="Elimina el registro de lesiones de un crash"
        )

    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """
        Lista información de lesiones con paginación.
        
        Args:
            skip: Número de registros a saltar (default: 0)
            limit: Número máximo de registros a devolver (default: 100, máx: 1000)
        
        Returns:
            Lista de información de lesiones
        
        Raises:
            HTTPException 400: Si el límite es inválido
        """
        db: Session = request.state.db_session
        self.logger.info(f"Listing crash_injuries: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400,
                detail="El límite máximo es 1000 registros y el mínimo es 0"
            )
        
        crash_injuries = db.query(CrashInjuries).offset(skip).limit(limit).all()
        return crash_injuries

    def get(self, crash_record_id: str, request: Request):
        """
        Obtiene información de lesiones de un crash específico.
        
        Args:
            crash_record_id: ID único del crash (hash SHA-512)
        
        Returns:
            Información de lesiones encontrada
        
        Raises:
            HTTPException 404: Si el registro no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Getting crash_injuries with id: {crash_record_id}")
        
        crash_injuries = db.query(CrashInjuries).get(crash_record_id)
        if not crash_injuries:
            raise HTTPException(
                status_code=404,
                detail=f"Información de lesiones del crash {crash_record_id} no encontrada"
            )
        
        return crash_injuries

    def create(self, data: CreateCrashInjuries, request: Request):
        """
        Crea información de lesiones para un crash.
        
        Args:
            data: Datos de lesiones a crear
        
        Returns:
            Información de lesiones creada
        
        Raises:
            HTTPException 400: Si los datos son inválidos
            HTTPException 404: Si el crash_record_id no existe
            HTTPException 409: Si ya existe información de lesiones para este crash
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating crash_injuries for crash {data.crash_record_id}")
        
        try:
            # Validación: crash_record_id debe existir
            validate_foreign_key_exists(
                db=db,
                table_name="crashes",
                column_name="crash_record_id",
                value=data.crash_record_id
            )
            
            # Validación: Verificar si ya existe
            existing = db.query(CrashInjuries).get(data.crash_record_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe información de lesiones para el crash {data.crash_record_id}"
                )
            
            # Crear nuevo registro
            new_crash_injuries = CrashInjuries(
                crash_record_id=data.crash_record_id,
                injuries_fatal=data.injuries_fatal,
                injuries_incapacitating=data.injuries_incapacitating,
                injuries_other=data.injuries_other
            )
            
            db.add(new_crash_injuries)
            db.flush()
            
            self.logger.info(f"Created crash_injuries for crash {data.crash_record_id}")
            return new_crash_injuries
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating crash_injuries: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: el crash_record_id no existe o ya tiene información de lesiones"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating crash_injuries: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, crash_record_id: str, data: UpdateCrashInjuries, request: Request):
        """
        Actualiza información de lesiones de un crash.
        
        Args:
            crash_record_id: ID del crash a actualizar
            data: Nuevos datos (solo se actualizan los campos proporcionados)
        
        Returns:
            Información de lesiones actualizada
        
        Raises:
            HTTPException 404: Si el registro no existe
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Updating crash_injuries {crash_record_id}")
        
        try:
            crash_injuries = db.query(CrashInjuries).get(crash_record_id)
            if not crash_injuries:
                raise HTTPException(
                    status_code=404,
                    detail=f"Información de lesiones del crash {crash_record_id} no encontrada"
                )
            
            # Obtener solo los campos que fueron proporcionados
            update_data = data.model_dump(exclude_unset=True)
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(crash_injuries, key, value)
            
            db.flush()
            self.logger.info(f"Updated crash_injuries {crash_record_id}")
            return crash_injuries
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating crash_injuries: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating crash_injuries: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, crash_record_id: str, request: Request):
        """
        Elimina información de lesiones de un crash.
        
        Args:
            crash_record_id: ID del crash cuya información de lesiones se eliminará
        
        Returns:
            Mensaje de confirmación
        
        Raises:
            HTTPException 404: Si el registro no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Deleting crash_injuries {crash_record_id}")
        
        try:
            crash_injuries = db.query(CrashInjuries).get(crash_record_id)
            if not crash_injuries:
                raise HTTPException(
                    status_code=404,
                    detail=f"Información de lesiones del crash {crash_record_id} no encontrada"
                )
            
            db.delete(crash_injuries)
            db.flush()
            
            self.logger.info(f"Deleted crash_injuries {crash_record_id}")
            return {
                "message": f"Información de lesiones del crash {crash_record_id} eliminada exitosamente",
                "crash_record_id": crash_record_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting crash_injuries: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting crash_injuries: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )
