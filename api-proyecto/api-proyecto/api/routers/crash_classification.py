"""
Router para la tabla crash_classification.
Implementa endpoints CRUD con validaciones de FK.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.crash_classification import (
    CreateCrashClassification,
    ReadCrashClassification,
    UpdateCrashClassification
)
from db.entities.crash_classification import CrashClassification
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import validate_foreign_key_exists


class CrashClassificationRouter:
    """
    Router para gestionar clasificaciones de crashes.
    
    Endpoints:
        GET /crash-classification - Lista todas las clasificaciones (paginado)
        GET /crash-classification/{crash_record_id} - Obtiene una clasificación específica
        POST /crash-classification - Crea una nueva clasificación
        PUT /crash-classification/{crash_record_id} - Actualiza una clasificación
        DELETE /crash-classification/{crash_record_id} - Elimina una clasificación
    """

    def __init__(
        self,
        db_session_manager: DBSessionManager,
        logger_session_manager: LoggerSessionManager
    ):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(
            prefix="/crash-classification",
            tags=["Crash Classification"]
        )

        # Registrar endpoints
        self.router.add_api_route(
            "/",
            self.list,
            methods=["GET"],
            response_model=list[ReadCrashClassification],
            summary="Lista clasificaciones de crashes",
            description="Obtiene una lista paginada de clasificaciones"
        )
        self.router.add_api_route(
            "/{crash_record_id}",
            self.get,
            methods=["GET"],
            response_model=ReadCrashClassification,
            summary="Obtiene una clasificación",
            description="Obtiene una clasificación específica por crash_record_id"
        )
        self.router.add_api_route(
            "/",
            self.create,
            methods=["POST"],
            response_model=ReadCrashClassification,
            status_code=201,
            summary="Crea una clasificación",
            description="Crea una nueva clasificación para un crash existente"
        )
        self.router.add_api_route(
            "/{crash_record_id}",
            self.update,
            methods=["PUT"],
            response_model=ReadCrashClassification,
            summary="Actualiza una clasificación",
            description="Actualiza los datos de una clasificación existente"
        )
        self.router.add_api_route(
            "/{crash_record_id}",
            self.delete,
            methods=["DELETE"],
            summary="Elimina una clasificación",
            description="Elimina una clasificación de crash"
        )

    def list(self, request: Request, skip: int = 0, limit: int = 100, ge=0, le=1000):
        """
        Lista todas las clasificaciones con paginación.
        
        Args:
            skip: Número de registros a saltar (default: 0)
            limit: Número máximo de registros a devolver (default: 100, máx: 1000)
        
        Returns:
            Lista de clasificaciones
        """
        db: Session = request.state.db_session
        self.logger.info(f"Listing crash_classification: skip={skip}, limit={limit}")

        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400,
                detail="El límite máximo es 1000 registros y el minimo es 0"
            )

        classifications = (
            db.query(CrashClassification)
            .offset(skip)
            .limit(limit)
            .all()
        )
        return classifications

    def get(self, crash_record_id: str, request: Request):
        """
        Obtiene una clasificación específica por su crash_record_id.
        
        Args:
            crash_record_id: ID del crash
        
        Returns:
            Clasificación encontrada
        
        Raises:
            HTTPException 404: Si la clasificación no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Fetching crash_classification for: {crash_record_id}")

        classification = db.query(CrashClassification).get(crash_record_id)
        if not classification:
            raise HTTPException(
                status_code=404,
                detail=f"Clasificación para crash {crash_record_id} no encontrada"
            )

        return classification

    def create(self, data: CreateCrashClassification, request: Request):
        """
        Crea una nueva clasificación de crash.
        
        Validaciones:
        - crash_record_id debe existir en la tabla crashes
        - No puede haber duplicados (crash_record_id es PK)
        
        Args:
            data: Datos de la clasificación a crear
        
        Returns:
            Clasificación creada
        
        Raises:
            HTTPException 404: Si el crash_record_id no existe
            HTTPException 409: Si ya existe una clasificación para este crash
            HTTPException 400: Si hay errores de validación
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating crash_classification for: {data.crash_record_id}")

        try:
            # Validación 1: Verificar que el crash existe
            validate_foreign_key_exists(
                db=db,
                table_name="crashes",
                column_name="crash_record_id",
                value=data.crash_record_id
            )

            # Validación 2: Verificar que no exista ya una clasificación
            existing = db.query(CrashClassification).get(data.crash_record_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe una clasificación para el crash {data.crash_record_id}"
                )

            # Crear la clasificación
            new_classification = CrashClassification(**data.model_dump())
            db.add(new_classification)
            db.flush()

            self.logger.info(f"Created crash_classification for: {data.crash_record_id}")
            return new_classification

        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating crash_classification: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: crash_record_id no válido o duplicado"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating crash_classification: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(
        self,
        crash_record_id: str,
        data: UpdateCrashClassification,
        request: Request
    ):
        """
        Actualiza una clasificación existente.
        
        Args:
            crash_record_id: ID del crash
            data: Nuevos datos (solo se actualizan los campos proporcionados)
        
        Returns:
            Clasificación actualizada
        
        Raises:
            HTTPException 404: Si la clasificación no existe
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Updating crash_classification: {crash_record_id}")

        try:
            classification = db.query(CrashClassification).get(crash_record_id)
            if not classification:
                raise HTTPException(
                    status_code=404,
                    detail=f"Clasificación para crash {crash_record_id} no encontrada"
                )

            # Obtener solo los campos proporcionados
            update_data = data.model_dump(exclude_unset=True)

            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(classification, key, value)

            db.flush()
            self.logger.info(f"Updated crash_classification: {crash_record_id}")
            return classification

        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating crash_classification: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating crash_classification: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, crash_record_id: str, request: Request):
        """
        Elimina una clasificación de crash.
        
        Args:
            crash_record_id: ID del crash
        
        Returns:
            Mensaje de confirmación
        
        Raises:
            HTTPException 404: Si la clasificación no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Deleting crash_classification: {crash_record_id}")

        try:
            classification = db.query(CrashClassification).get(crash_record_id)
            if not classification:
                raise HTTPException(
                    status_code=404,
                    detail=f"Clasificación para crash {crash_record_id} no encontrada"
                )

            db.delete(classification)
            db.flush()

            self.logger.info(f"Deleted crash_classification: {crash_record_id}")
            return {
                "message": f"Clasificación para crash {crash_record_id} eliminada exitosamente",
                "crash_record_id": crash_record_id
            }

        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting crash_classification: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar la clasificación debido a restricciones"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting crash_classification: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )