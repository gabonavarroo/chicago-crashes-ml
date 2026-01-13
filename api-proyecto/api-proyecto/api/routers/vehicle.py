"""
Router para la tabla vehicle.
Implementa endpoints CRUD con generación automática de IDs y validaciones.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.vehicle import CreateVehicle, ReadVehicle, UpdateVehicle
from db.entities.vehicle import Vehicle
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.id_generators import generate_vehicle_id, generate_crash_unit_id
from util.validators import (
    validate_foreign_key_exists,
    validate_non_negative,
    validate_vehicle_year
)


class VehicleRouter:
    """
    Router para gestionar vehículos involucrados en crashes.
    
    Endpoints:
        GET /vehicles - Lista todos los vehículos (paginado)
        GET /vehicles/{vehicle_id} - Obtiene un vehículo específico
        POST /vehicles - Crea un nuevo vehículo (IDs autogenerados)
        PUT /vehicles/{vehicle_id} - Actualiza un vehículo
        DELETE /vehicles/{vehicle_id} - Elimina un vehículo
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/vehicles", tags=["Vehicles"])

        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadVehicle],
            summary="Lista vehículos",
            description="Obtiene una lista paginada de vehículos"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadVehicle,
            summary="Obtiene un vehículo",
            description="Obtiene un vehículo específico por su ID"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadVehicle, 
            status_code=201,
            summary="Crea un vehículo",
            description="Crea un nuevo vehículo con vehicle_id y crash_unit_id autogenerados"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadVehicle,
            summary="Actualiza un vehículo",
            description="Actualiza los datos de un vehículo existente"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina un vehículo",
            description="Elimina un vehículo y sus registros relacionados"
        )
    
    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """Lista todos los vehículos con paginación."""
        db: Session = request.state.db_session
        self.logger.info(f"Listing vehicles: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400, 
                detail="El límite máximo es 1000 registros y el minimo es 0"
            )
        
        vehicles = db.query(Vehicle).offset(skip).limit(limit).all()
        return vehicles

    def get(self, vehicle_id: int, request: Request):
        """Obtiene un vehículo específico por su ID."""
        db: Session = request.state.db_session
        self.logger.info(f"Retrieving vehicle with id: {vehicle_id}")
        
        vehicle = db.query(Vehicle).get(vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=404, 
                detail=f"Vehículo {vehicle_id} no encontrado"
            )
        
        return vehicle

    def create(self, data: CreateVehicle, request: Request):
        """
        Crea un nuevo vehículo con IDs autogenerados.
        
        Genera automáticamente:
        - vehicle_id: Autoincremental (BIGSERIAL)
        - crash_unit_id: Autoincremental
        
        Validaciones:
        - crash_record_id debe existir en crashes
        - num_passengers no puede ser negativo
        - vehicle_year debe estar en rango 1900 a año_actual+1
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating new vehicle for crash {data.crash_record_id}")
        
        try:
            # Validación CRÍTICA: El crash debe existir
            validate_foreign_key_exists(
                db=db,
                table_name="crashes",
                column_name="crash_record_id",
                value=data.crash_record_id
            )
            
            # Validación: Campos no negativos
            if data.unit_no is not None:
                validate_non_negative(data.unit_no, "unit_no")
            if data.num_passengers is not None:
                validate_non_negative(data.num_passengers, "num_passengers")
            
            # Validación: Año del vehículo
            if data.vehicle_year is not None:
                validate_vehicle_year(data.vehicle_year)
            
            # Generar IDs automáticamente
            vehicle_id = generate_vehicle_id(db)
            crash_unit_id = generate_crash_unit_id(db)
            
            self.logger.info(
                f"Generated IDs - vehicle_id: {vehicle_id}, "
                f"crash_unit_id: {crash_unit_id}"
            )
            
            # Crear el vehículo
            new_vehicle = Vehicle(
                vehicle_id=vehicle_id,
                crash_unit_id=crash_unit_id,
                crash_record_id=data.crash_record_id,
                unit_no=data.unit_no,
                unit_type=data.unit_type,
                num_passengers=data.num_passengers,
                vehicle_year=data.vehicle_year,
                make=data.make,
                model=data.model,
                vehicle_type=data.vehicle_type
            )
            
            db.add(new_vehicle)
            db.flush()
            
            self.logger.info(f"Created vehicle with ID: {vehicle_id}")
            return new_vehicle
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating vehicle: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: el crash_record_id no existe"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating vehicle: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, vehicle_id: int, data: UpdateVehicle, request: Request):
        """Actualiza un vehículo existente."""
        db: Session = request.state.db_session
        self.logger.info(f"Updating vehicle {vehicle_id}")
        
        try:
            vehicle = db.query(Vehicle).get(vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=404,
                    detail=f"Vehículo {vehicle_id} no encontrado"
                )
            
            update_data = data.model_dump(exclude_unset=True)
            
            # Validar crash_record_id si se actualiza
            if 'crash_record_id' in update_data:
                validate_foreign_key_exists(
                    db=db,
                    table_name="crashes",
                    column_name="crash_record_id",
                    value=update_data['crash_record_id']
                )
            
            # Validar campos no negativos
            if 'unit_no' in update_data and update_data['unit_no'] is not None:
                validate_non_negative(update_data['unit_no'], "unit_no")
            
            if 'num_passengers' in update_data and update_data['num_passengers'] is not None:
                validate_non_negative(update_data['num_passengers'], "num_passengers")
            
            # Validar año del vehículo
            if 'vehicle_year' in update_data and update_data['vehicle_year'] is not None:
                validate_vehicle_year(update_data['vehicle_year'])
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(vehicle, key, value)
            
            db.flush()
            self.logger.info(f"Updated vehicle {vehicle_id}")
            return vehicle
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating vehicle: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating vehicle: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, vehicle_id: int, request: Request):
        """Elimina un vehículo y sus registros relacionados (cascade)."""
        db: Session = request.state.db_session
        self.logger.info(f"Deleting vehicle {vehicle_id}")
        
        try:
            vehicle = db.query(Vehicle).get(vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=404,
                    detail=f"Vehículo {vehicle_id} no encontrado"
                )
            
            db.delete(vehicle)
            db.flush()
            
            self.logger.info(f"Deleted vehicle {vehicle_id}")
            return {
                "message": f"Vehículo {vehicle_id} eliminado exitosamente",
                "vehicle_id": vehicle_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting vehicle: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se puede eliminar el vehículo porque tiene registros "
                    "relacionados"
                )
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting vehicle: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )