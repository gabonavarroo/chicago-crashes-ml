"""
Router para la tabla crash_date.
Implementa endpoints CRUD con validaciones de información temporal.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.crash_date import CreateCrashDate, ReadCrashDate, UpdateCrashDate
from db.entities.crash_date import CrashDate
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import validate_foreign_key_exists


class CrashDateRouter:
    """
    Router para gestionar información temporal de crashes.
    
    Endpoints:
        GET /crash_date - Lista información temporal de crashes (paginado)
        GET /crash_date/{crash_record_id} - Obtiene información temporal de un crash
        POST /crash_date - Crea información temporal de un crash
        PUT /crash_date/{crash_record_id} - Actualiza información temporal
        DELETE /crash_date/{crash_record_id} - Elimina información temporal
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/crash_date", tags=["Crash Date"])

        # Registrar endpoints
        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadCrashDate],
            summary="Lista información temporal de crashes",
            description="Obtiene una lista paginada de información temporal de crashes"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadCrashDate,
            summary="Obtiene información temporal de un crash",
            description="Obtiene la información temporal (día y mes) de un crash específico"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadCrashDate,
            status_code=201,
            summary="Crea información temporal de un crash",
            description="Crea un nuevo registro de información temporal para un crash existente"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadCrashDate,
            summary="Actualiza información temporal",
            description="Actualiza los datos temporales (día y mes) de un crash"
        )
        self.router.add_api_route(
            "/{crash_record_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina información temporal",
            description="Elimina el registro de información temporal de un crash"
        )

    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """
        Lista información temporal de crashes con paginación.
        
        Args:
            skip: Número de registros a saltar (default: 0)
            limit: Número máximo de registros a devolver (default: 100, máx: 1000)
        
        Returns:
            Lista de información temporal de crashes
        
        Raises:
            HTTPException 400: Si el límite es inválido
        """
        db: Session = request.state.db_session
        self.logger.info(f"Listing crash_date: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400,
                detail="El límite máximo es 1000 registros y el mínimo es 0"
            )
        
        crash_dates = db.query(CrashDate).offset(skip).limit(limit).all()
        return crash_dates

    def get(self, crash_record_id: str, request: Request):
        """
        Obtiene información temporal de un crash específico.
        
        Args:
            crash_record_id: ID único del crash (hash SHA-512)
        
        Returns:
            Información temporal encontrada
        
        Raises:
            HTTPException 404: Si el registro no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Getting crash_date with id: {crash_record_id}")
        
        crash_date = db.query(CrashDate).get(crash_record_id)
        if not crash_date:
            raise HTTPException(
                status_code=404,
                detail=f"Información temporal del crash {crash_record_id} no encontrada"
            )
        
        return crash_date

    def create(self, data: CreateCrashDate, request: Request):
        """
        Crea información temporal de un crash.
        
        Args:
            data: Datos de la información temporal a crear
        
        Returns:
            Información temporal creada
        
        Raises:
            HTTPException 400: Si los datos son inválidos
            HTTPException 404: Si el crash_record_id no existe
            HTTPException 409: Si ya existe información temporal para este crash
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating crash_date for crash {data.crash_record_id}")
        
        try:
            # Validación: crash_record_id debe existir
            validate_foreign_key_exists(
                db=db,
                table_name="crashes",
                column_name="crash_record_id",
                value=data.crash_record_id
            )
            
            # Validación: Verificar si ya existe
            existing = db.query(CrashDate).get(data.crash_record_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe información temporal para el crash {data.crash_record_id}"
                )
            
            # Crear nuevo registro
            new_crash_date = CrashDate(
                crash_record_id=data.crash_record_id,
                crash_day_of_week=data.crash_day_of_week,
                crash_month=data.crash_month
            )
            
            db.add(new_crash_date)
            db.flush()
            
            self.logger.info(f"Created crash_date for crash {data.crash_record_id}")
            return new_crash_date
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating crash_date: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: el crash_record_id no existe o ya tiene información temporal"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating crash_date: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, crash_record_id: str, data: UpdateCrashDate, request: Request):
        """
        Actualiza información temporal de un crash.
        
        Args:
            crash_record_id: ID del crash a actualizar
            data: Nuevos datos (solo se actualizan los campos proporcionados)
        
        Returns:
            Información temporal actualizada
        
        Raises:
            HTTPException 404: Si el registro no existe
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Updating crash_date {crash_record_id}")
        
        try:
            crash_date = db.query(CrashDate).get(crash_record_id)
            if not crash_date:
                raise HTTPException(
                    status_code=404,
                    detail=f"Información temporal del crash {crash_record_id} no encontrada"
                )
            
            # Obtener solo los campos que fueron proporcionados
            update_data = data.model_dump(exclude_unset=True)
            
            # Validaciones para campos actualizados
            if 'crash_day_of_week' in update_data and update_data['crash_day_of_week'] is not None:
                if not (1 <= update_data['crash_day_of_week'] <= 7):
                    raise HTTPException(
                        status_code=400,
                        detail="crash_day_of_week debe estar entre 1 y 7"
                    )
            
            if 'crash_month' in update_data and update_data['crash_month'] is not None:
                if not (1 <= update_data['crash_month'] <= 12):
                    raise HTTPException(
                        status_code=400,
                        detail="crash_month debe estar entre 1 y 12"
                    )
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(crash_date, key, value)
            
            db.flush()
            self.logger.info(f"Updated crash_date {crash_record_id}")
            return crash_date
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating crash_date: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating crash_date: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, crash_record_id: str, request: Request):
        """
        Elimina información temporal de un crash.
        
        Args:
            crash_record_id: ID del crash cuya información temporal se eliminará
        
        Returns:
            Mensaje de confirmación
        
        Raises:
            HTTPException 404: Si el registro no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Deleting crash_date {crash_record_id}")
        
        try:
            crash_date = db.query(CrashDate).get(crash_record_id)
            if not crash_date:
                raise HTTPException(
                    status_code=404,
                    detail=f"Información temporal del crash {crash_record_id} no encontrada"
                )
            
            db.delete(crash_date)
            db.flush()
            
            self.logger.info(f"Deleted crash_date {crash_record_id}")
            return {
                "message": f"Información temporal del crash {crash_record_id} eliminada exitosamente",
                "crash_record_id": crash_record_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting crash_date: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting crash_date: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )
