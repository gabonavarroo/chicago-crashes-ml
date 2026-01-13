"""
Router para la tabla vehicle_specs (especificaciones de vehículos).
Implementa endpoints CRUD con validación de foreign keys.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.vehicle_models import CreateVehicleModels, ReadVehicleModels, UpdateVehicleModels
from db.entities.vehicle_models import VehicleModels
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import validate_foreign_key_exists, validate_string_length


class VehicleModelsRouter:
    """
    Router para gestionar especificaciones de vehículos.
    
    Endpoints:
        GET /vehicle-specs - Lista todas las especificaciones
        GET /vehicle-specs/{vehicle_id} - Obtiene especificaciones de un vehículo
        POST /vehicle-specs - Crea especificaciones para un vehículo
        PUT /vehicle-specs/{vehicle_id} - Actualiza especificaciones
        DELETE /vehicle-specs/{vehicle_id} - Elimina especificaciones
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/vehicle-specs", tags=["Vehicle Specs"])

        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadVehicleModels],
            summary="Lista especificaciones de vehículos"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadVehicleModels,
            summary="Obtiene especificaciones de un vehículo"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadVehicleModels, 
            status_code=201,
            summary="Crea especificaciones para un vehículo"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadVehicleModels,
            summary="Actualiza especificaciones de un vehículo"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina especificaciones de un vehículo"
        )
    
    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """Lista todas las especificaciones de vehículos con paginación."""
        db: Session = request.state.db_session
        self.logger.info(f"Listing vehicle_specs: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400, 
                detail="El límite máximo es 1000 registros y el minimo es 0"
            )
        
        specs = db.query(VehicleModels).offset(skip).limit(limit).all()
        return specs

    def get(self, vehicle_id: int, request: Request):
        """Obtiene las especificaciones de un vehículo específico."""
        db: Session = request.state.db_session
        self.logger.info(f"Retrieving specs for vehicle_id: {vehicle_id}")
        
        specs = db.query(VehicleModels).filter(VehicleModels.vehicle_id == vehicle_id).first()
        if not specs:
            raise HTTPException(
                status_code=404,
                detail=f"Especificaciones para vehículo {vehicle_id} no encontradas"
            )
        
        return specs

    def create(self, data: CreateVehicleModels, request: Request):
        """
        Crea especificaciones para un vehículo.
        
        Validaciones:
        - vehicle_id debe existir en la tabla vehicle
        - No pueden existir especificaciones previas para este vehículo
        - Longitudes máximas de strings: 150 caracteres
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating specs for vehicle {data.vehicle_id}")
        
        try:
            # Validación CRÍTICA: El vehículo debe existir
            validate_foreign_key_exists(
                db=db,
                table_name="vehicle",
                column_name="vehicle_id",
                value=data.vehicle_id
            )
            
            # Verificar que no existan especificaciones previas
            existing = db.query(VehicleModels).filter(
                VehicleModels.vehicle_id == data.vehicle_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existen especificaciones para el vehículo {data.vehicle_id}"
                )
            
            # Validar longitudes de strings
            if data.vehicle_use:
                validate_string_length(data.vehicle_use, 150, "vehicle_use")
            if data.vehicle_config:
                validate_string_length(data.vehicle_config, 150, "vehicle_config")
            if data.cargo_body_type:
                validate_string_length(data.cargo_body_type, 150, "cargo_body_type")
            
            # Crear especificaciones
            new_specs = VehicleModels(**data.model_dump())
            db.add(new_specs)
            db.flush()
            
            self.logger.info(f"Created specs for vehicle {data.vehicle_id}")
            return new_specs
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating specs: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: el vehicle_id no existe"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating specs: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, vehicle_id: int, data: UpdateVehicleModels, request: Request):
        """Actualiza las especificaciones de un vehículo."""
        db: Session = request.state.db_session
        self.logger.info(f"Updating specs for vehicle {vehicle_id}")
        
        try:
            specs = db.query(VehicleModels).filter(
                VehicleModels.vehicle_id == vehicle_id
            ).first()
            if not specs:
                raise HTTPException(
                    status_code=404,
                    detail=f"Especificaciones para vehículo {vehicle_id} no encontradas"
                )
            
            update_data = data.model_dump(exclude_unset=True)
            
            # Validar longitudes
            if 'vehicle_use' in update_data and update_data['vehicle_use']:
                validate_string_length(update_data['vehicle_use'], 150, "vehicle_use")
            if 'vehicle_config' in update_data and update_data['vehicle_config']:
                validate_string_length(update_data['vehicle_config'], 150, "vehicle_config")
            if 'cargo_body_type' in update_data and update_data['cargo_body_type']:
                validate_string_length(update_data['cargo_body_type'], 150, "cargo_body_type")
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(specs, key, value)
            
            db.flush()
            self.logger.info(f"Updated specs for vehicle {vehicle_id}")
            return specs
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating specs: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating specs: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, vehicle_id: int, request: Request):
        """Elimina las especificaciones de un vehículo."""
        db: Session = request.state.db_session
        self.logger.info(f"Deleting specs for vehicle {vehicle_id}")
        
        try:
            specs = db.query(VehicleModels).filter(
                VehicleModels.vehicle_id == vehicle_id
            ).first()
            if not specs:
                raise HTTPException(
                    status_code=404,
                    detail=f"Especificaciones para vehículo {vehicle_id} no encontradas"
                )
            
            db.delete(specs)
            db.flush()
            
            self.logger.info(f"Deleted specs for vehicle {vehicle_id}")
            return {
                "message": f"Especificaciones del vehículo {vehicle_id} eliminadas exitosamente",
                "vehicle_id": vehicle_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting specs: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting specs: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )