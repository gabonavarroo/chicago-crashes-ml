"""
Router para la tabla driver_info.
Implementa endpoints CRUD con validaciones de FK.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.driver_info import (
    CreateDriverInfo,
    ReadDriverInfo,
    UpdateDriverInfo
)
from db.entities.driver_info import DriverInfo
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import validate_foreign_key_exists


class DriverInfoRouter:
    """
    Router para gestionar información de conductores.
    
    Endpoints:
        GET /driver-info - Lista toda la información de conductores (paginado)
        GET /driver-info/{person_id} - Obtiene información de un conductor específico
        POST /driver-info - Crea nueva información de conductor
        PUT /driver-info/{person_id} - Actualiza información de conductor
        DELETE /driver-info/{person_id} - Elimina información de conductor
    """

    def __init__(
        self,
        db_session_manager: DBSessionManager,
        logger_session_manager: LoggerSessionManager
    ):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(
            prefix="/driver-info",
            tags=["Driver Info"]
        )

        # Registrar endpoints
        self.router.add_api_route(
            "/",
            self.list,
            methods=["GET"],
            response_model=list[ReadDriverInfo],
            summary="Lista información de conductores",
            description="Obtiene una lista paginada de información de conductores"
        )
        self.router.add_api_route(
            "/{person_id}",
            self.get,
            methods=["GET"],
            response_model=ReadDriverInfo,
            summary="Obtiene información de un conductor",
            description="Obtiene información específica de un conductor por person_id"
        )
        self.router.add_api_route(
            "/",
            self.create,
            methods=["POST"],
            response_model=ReadDriverInfo,
            status_code=201,
            summary="Crea información de conductor",
            description="Crea nueva información para un conductor existente en people"
        )
        self.router.add_api_route(
            "/{person_id}",
            self.update,
            methods=["PUT"],
            response_model=ReadDriverInfo,
            summary="Actualiza información de conductor",
            description="Actualiza los datos de un conductor existente"
        )
        self.router.add_api_route(
            "/{person_id}",
            self.delete,
            methods=["DELETE"],
            summary="Elimina información de conductor",
            description="Elimina información de conductor"
        )

    def list(self, request: Request, skip: int = 0, limit: int = 100, le= 1000, ge = 0):
        """
        Lista toda la información de conductores con paginación.
        
        Args:
            skip: Número de registros a saltar (default: 0)
            limit: Número máximo de registros a devolver (default: 100, máx: 1000)
        
        Returns:
            Lista de información de conductores
        """
        db: Session = request.state.db_session
        self.logger.info(f"Listing driver_info: skip={skip}, limit={limit}")

        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400,
                detail="El límite máximo es 1000 registros y el minimo es 0"
            )

        driver_infos = (
            db.query(DriverInfo)
            .offset(skip)
            .limit(limit)
            .all()
        )
        return driver_infos

    def get(self, person_id: str, request: Request):
        """
        Obtiene información de un conductor específico por su person_id.
        
        Args:
            person_id: ID de la persona (formato Q0000001)
        
        Returns:
            Información del conductor encontrada
        
        Raises:
            HTTPException 404: Si la información no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Fetching driver_info for: {person_id}")

        driver_info = db.query(DriverInfo).get(person_id)
        if not driver_info:
            raise HTTPException(
                status_code=404,
                detail=f"Información de conductor para person_id {person_id} no encontrada"
            )

        return driver_info

    def create(self, data: CreateDriverInfo, request: Request):
        """
        Crea nueva información de conductor.
        
        Validaciones:
        - person_id debe existir en la tabla people
        - No puede haber duplicados (person_id es PK)
        - bac_result_value no puede ser negativo
        
        Args:
            data: Datos de información del conductor a crear
        
        Returns:
            Información del conductor creada
        
        Raises:
            HTTPException 404: Si el person_id no existe
            HTTPException 409: Si ya existe información para este conductor
            HTTPException 400: Si hay errores de validación
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating driver_info for: {data.person_id}")

        try:
            # Validación 1: Verificar que la persona existe
            validate_foreign_key_exists(
                db=db,
                table_name="people",
                column_name="person_id",
                value=data.person_id
            )

            # Validación 2: Verificar que no exista ya información para este conductor
            existing = db.query(DriverInfo).get(data.person_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe información de conductor para person_id {data.person_id}"
                )

            # Validación 3: BAC no negativo (ya validado en Pydantic, pero doble check)
            if data.bac_result_value is not None and data.bac_result_value < 0:
                raise HTTPException(
                    status_code=400,
                    detail="El nivel de alcohol en sangre no puede ser negativo"
                )

            # Crear la información del conductor
            new_driver_info = DriverInfo(**data.model_dump())
            db.add(new_driver_info)
            db.flush()

            self.logger.info(f"Created driver_info for: {data.person_id}")
            return new_driver_info

        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating driver_info: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: person_id no válido o duplicado"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating driver_info: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(
        self,
        person_id: str,
        data: UpdateDriverInfo,
        request: Request
    ):
        """
        Actualiza información de conductor existente.
        
        Args:
            person_id: ID de la persona
            data: Nuevos datos (solo se actualizan los campos proporcionados)
        
        Returns:
            Información del conductor actualizada
        
        Raises:
            HTTPException 404: Si la información no existe
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Updating driver_info: {person_id}")

        try:
            driver_info = db.query(DriverInfo).get(person_id)
            if not driver_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Información de conductor para person_id {person_id} no encontrada"
                )

            # Obtener solo los campos proporcionados
            update_data = data.model_dump(exclude_unset=True)

            # Validación: BAC no negativo
            if 'bac_result_value' in update_data and update_data['bac_result_value'] is not None:
                if update_data['bac_result_value'] < 0:
                    raise HTTPException(
                        status_code=400,
                        detail="El nivel de alcohol en sangre no puede ser negativo"
                    )

            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(driver_info, key, value)

            db.flush()
            self.logger.info(f"Updated driver_info: {person_id}")
            return driver_info

        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating driver_info: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating driver_info: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, person_id: str, request: Request):
        """
        Elimina información de conductor.
        
        Args:
            person_id: ID de la persona
        
        Returns:
            Mensaje de confirmación
        
        Raises:
            HTTPException 404: Si la información no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Deleting driver_info: {person_id}")

        try:
            driver_info = db.query(DriverInfo).get(person_id)
            if not driver_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Información de conductor para person_id {person_id} no encontrada"
                )

            db.delete(driver_info)
            db.flush()

            self.logger.info(f"Deleted driver_info: {person_id}")
            return {
                "message": f"Información de conductor para person_id {person_id} eliminada exitosamente",
                "person_id": person_id
            }

        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting driver_info: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar la información debido a restricciones"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting driver_info: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )