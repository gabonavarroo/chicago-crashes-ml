"""
Router para la tabla vehicle_maneuvers.
Implementa endpoints CRUD con validaciones de maniobras de vehículos.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.vehicle_maneuvers import CreateVehicleManeuver, ReadVehicleManeuver, UpdateVehicleManeuver
from db.entities.vehicle_maneuvers import VehicleManeuvers
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import validate_foreign_key_exists


class VehicleManeuversRouter:
    """
    Router para gestionar maniobras de vehículos.
    
    Endpoints:
        GET /vehicle-maneuvers - Lista maniobras de vehículos (paginado)
        GET /vehicle-maneuvers/{vehicle_id} - Obtiene maniobra de un vehículo
        POST /vehicle-maneuvers - Crea maniobra de un vehículo
        PUT /vehicle-maneuvers/{vehicle_id} - Actualiza maniobra de un vehículo
        DELETE /vehicle-maneuvers/{vehicle_id} - Elimina maniobra de un vehículo
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/vehicle-maneuvers", tags=["Vehicle Maneuvers"])

        # Registrar endpoints
        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadVehicleManeuver],
            summary="Lista maniobras de vehículos",
            description="Obtiene una lista paginada de maniobras de vehículos"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadVehicleManeuver,
            summary="Obtiene maniobra de un vehículo",
            description="Obtiene la maniobra realizada por un vehículo específico"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadVehicleManeuver,
            status_code=201,
            summary="Crea maniobra de un vehículo",
            description="Crea un nuevo registro de maniobra para un vehículo existente"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadVehicleManeuver,
            summary="Actualiza maniobra de un vehículo",
            description="Actualiza la maniobra de un vehículo existente"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina maniobra de un vehículo",
            description="Elimina el registro de maniobra de un vehículo"
        )

    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """
        Lista maniobras de vehículos con paginación.
        
        Args:
            skip: Número de registros a saltar (default: 0)
            limit: Número máximo de registros a devolver (default: 100, máx: 1000)
        
        Returns:
            Lista de maniobras de vehículos
        
        Raises:
            HTTPException 400: Si el límite es inválido
        """
        db: Session = request.state.db_session
        self.logger.info(f"Listing vehicle_maneuvers: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400,
                detail="El límite máximo es 1000 registros y el mínimo es 0"
            )
        
        maneuvers = db.query(VehicleManeuvers).offset(skip).limit(limit).all()
        return maneuvers

    def get(self, vehicle_id: int, request: Request):
        """
        Obtiene maniobra de un vehículo específico.
        
        Args:
            vehicle_id: ID único del vehículo
        
        Returns:
            Maniobra encontrada
        
        Raises:
            HTTPException 404: Si la maniobra no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Getting maneuver for vehicle_id: {vehicle_id}")
        
        maneuver = db.query(VehicleManeuvers).get(vehicle_id)
        if not maneuver:
            raise HTTPException(
                status_code=404,
                detail=f"Maniobra del vehículo {vehicle_id} no encontrada"
            )
        
        return maneuver

    def create(self, data: CreateVehicleManeuver, request: Request):
        """
        Crea maniobra de un vehículo.
        
        Args:
            data: Datos de la maniobra a crear
        
        Returns:
            Maniobra creada
        
        Raises:
            HTTPException 400: Si los datos son inválidos
            HTTPException 404: Si el vehicle_id no existe
            HTTPException 409: Si ya existe maniobra para este vehículo
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating maneuver for vehicle {data.vehicle_id}")
        
        try:
            # Validación: vehicle_id debe existir
            validate_foreign_key_exists(
                db=db,
                table_name="vehicle",
                column_name="vehicle_id",
                value=data.vehicle_id
            )
            
            # Validación: Verificar si ya existe
            existing = db.query(VehicleManeuvers).get(data.vehicle_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe maniobra registrada para el vehículo {data.vehicle_id}"
                )
            
            # Crear nueva maniobra
            new_maneuver = VehicleManeuvers(
                vehicle_id=data.vehicle_id,
                maneuver=data.maneuver
            )
            
            db.add(new_maneuver)
            db.flush()
            
            self.logger.info(f"Created maneuver for vehicle {data.vehicle_id}")
            return new_maneuver
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating maneuver: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: el vehicle_id no existe o ya tiene maniobra registrada"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating maneuver: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, vehicle_id: int, data: UpdateVehicleManeuver, request: Request):
        """
        Actualiza maniobra de un vehículo.
        
        Args:
            vehicle_id: ID del vehículo a actualizar
            data: Nuevos datos (solo se actualizan los campos proporcionados)
        
        Returns:
            Maniobra actualizada
        
        Raises:
            HTTPException 404: Si la maniobra no existe
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Updating maneuver for vehicle {vehicle_id}")
        
        try:
            maneuver = db.query(VehicleManeuvers).get(vehicle_id)
            if not maneuver:
                raise HTTPException(
                    status_code=404,
                    detail=f"Maniobra del vehículo {vehicle_id} no encontrada"
                )
            
            # Obtener solo los campos que fueron proporcionados
            update_data = data.model_dump(exclude_unset=True)
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(maneuver, key, value)
            
            db.flush()
            self.logger.info(f"Updated maneuver for vehicle {vehicle_id}")
            return maneuver
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating maneuver: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating maneuver: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, vehicle_id: int, request: Request):
        """
        Elimina maniobra de un vehículo.
        
        Args:
            vehicle_id: ID del vehículo cuya maniobra se eliminará
        
        Returns:
            Mensaje de confirmación
        
        Raises:
            HTTPException 404: Si la maniobra no existe
        """
        db: Session = request.state.db_session
        self.logger.info(f"Deleting maneuver for vehicle {vehicle_id}")
        
        try:
            maneuver = db.query(VehicleManeuvers).get(vehicle_id)
            if not maneuver:
                raise HTTPException(
                    status_code=404,
                    detail=f"Maniobra del vehículo {vehicle_id} no encontrada"
                )
            
            db.delete(maneuver)
            db.flush()
            
            self.logger.info(f"Deleted maneuver for vehicle {vehicle_id}")
            return {
                "message": f"Maniobra del vehículo {vehicle_id} eliminada exitosamente",
                "vehicle_id": vehicle_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting maneuver: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting maneuver: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )
