"""
Router para la tabla vehicle_violations.
Implementa endpoints CRUD con validación de foreign keys y normalización de booleanos.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.vehicle_violations import (
    CreateVehicleViolation, 
    ReadVehicleViolation, 
    UpdateVehicleViolation
)
from db.entities.vehicle_violations import VehicleViolations
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import (
    validate_foreign_key_exists, 
    normalize_boolean, 
    validate_string_length
)


class VehicleViolationsRouter:
    """
    Router para gestionar violaciones de vehículos.
    
    Endpoints:
        GET /vehicle-violations - Lista todas las violaciones (paginado)
        GET /vehicle-violations/{vehicle_id} - Obtiene violaciones de un vehículo
        POST /vehicle-violations - Crea violaciones para un vehículo
        PUT /vehicle-violations/{vehicle_id} - Actualiza violaciones
        DELETE /vehicle-violations/{vehicle_id} - Elimina violaciones
    
    Restricciones:
        - vehicle_id debe existir en la tabla vehicle
        - Solo puede existir UN registro de violaciones por vehículo
        - Los booleanos se normalizan automáticamente (True/1/"true" → True)
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/vehicle-violations", tags=["Vehicle Violations"])

        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadVehicleViolation],
            summary="Lista violaciones de vehículos",
            description="Obtiene una lista paginada de violaciones de vehículos"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadVehicleViolation,
            summary="Obtiene violaciones de un vehículo",
            description="Obtiene las violaciones de un vehículo específico"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadVehicleViolation, 
            status_code=201,
            summary="Crea violaciones para un vehículo",
            description="Crea un registro de violaciones para un vehículo (normaliza booleanos automáticamente)"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadVehicleViolation,
            summary="Actualiza violaciones de un vehículo",
            description="Actualiza las violaciones de un vehículo existente"
        )
        self.router.add_api_route(
            "/{vehicle_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina violaciones de un vehículo",
            description="Elimina el registro de violaciones de un vehículo"
        )
    
    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """
        Lista todas las violaciones de vehículos con paginación.
        
        Args:
            skip: Número de registros a saltar (default: 0)
            limit: Número máximo de registros a devolver (default: 100, máx: 1000)
        
        Returns:
            Lista de violaciones de vehículos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Listing vehicle violations: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400, 
                detail="El límite máximo es 1000 registros y el minimo es 0"
            )
        
        violations = db.query(VehicleViolations).offset(skip).limit(limit).all()
        return violations

    def get(self, vehicle_id: int, request: Request):
        """
        Obtiene las violaciones de un vehículo específico.
        
        Args:
            vehicle_id: ID del vehículo
        
        Returns:
            Violaciones del vehículo
        
        Raises:
            HTTPException 404: Si no existen violaciones para el vehículo
        """
        db: Session = request.state.db_session
        self.logger.info(f"Retrieving violations for vehicle_id: {vehicle_id}")
        
        violation = db.query(VehicleViolations).get(vehicle_id)
        if not violation:
            raise HTTPException(
                status_code=404,
                detail=f"Violaciones para vehículo {vehicle_id} no encontradas"
            )
        
        return violation

    def create(self, data: CreateVehicleViolation, request: Request):
        """
        Crea violaciones para un vehículo.
        
        Validaciones:
        - El vehicle_id debe existir en la tabla vehicle
        - No pueden existir violaciones previas para este vehículo
        - vehicle_defect no puede exceder 100 caracteres
        - Los booleanos se normalizan automáticamente (True/1/"true" → True)
        
        Args:
            data: Datos de las violaciones a crear
        
        Returns:
            Violaciones creadas
        
        Raises:
            HTTPException 404: Si el vehicle_id no existe
            HTTPException 409: Si ya existen violaciones para este vehículo
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating violations for vehicle {data.vehicle_id}")
        
        try:
            # Validación CRÍTICA: El vehículo debe existir
            validate_foreign_key_exists(
                db=db,
                table_name="vehicle",
                column_name="vehicle_id",
                value=data.vehicle_id
            )
            
            # Verificar que no existan violaciones previas
            existing = db.query(VehicleViolations).get(data.vehicle_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existen violaciones para el vehículo {data.vehicle_id}"
                )
            
            # Validar longitud de vehicle_defect
            if data.vehicle_defect:
                validate_string_length(data.vehicle_defect, 100, "vehicle_defect")
            
            # Normalizar booleanos (acepta True/False, 1/0, "true"/"false", etc.)
            data_dict = data.model_dump()
            for key in ['cmrc_veh_i', 'exceed_speed_limit_i', 'hazmat_present_i']:
                if data_dict[key] is not None:
                    data_dict[key] = normalize_boolean(data_dict[key])
            
            # Crear registro
            new_violation = VehicleViolations(**data_dict)
            db.add(new_violation)
            db.flush()
            
            self.logger.info(f"Created violations for vehicle {data.vehicle_id}")
            return new_violation
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating violations: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: el vehicle_id no existe"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating violations: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, vehicle_id: int, data: UpdateVehicleViolation, request: Request):
        """
        Actualiza las violaciones de un vehículo.
        
        Args:
            vehicle_id: ID del vehículo
            data: Nuevos datos (solo se actualizan los campos proporcionados)
        
        Returns:
            Violaciones actualizadas
        
        Raises:
            HTTPException 404: Si no existen violaciones para el vehículo
            HTTPException 400: Si los datos son inválidos
        """
        db: Session = request.state.db_session
        self.logger.info(f"Updating violations for vehicle {vehicle_id}")
        
        try:
            violation = db.query(VehicleViolations).get(vehicle_id)
            if not violation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Violaciones para vehículo {vehicle_id} no encontradas"
                )
            
            update_data = data.model_dump(exclude_unset=True)
            
            # Validar vehicle_defect si se actualiza
            if 'vehicle_defect' in update_data and update_data['vehicle_defect']:
                validate_string_length(
                    update_data['vehicle_defect'], 
                    100, 
                    "vehicle_defect"
                )
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(violation, key, value)
            
            db.flush()
            self.logger.info(f"Updated violations for vehicle {vehicle_id}")
            return violation
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating violations: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating violations: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, vehicle_id: int, request: Request):
        """
        Elimina las violaciones de un vehículo.
        
        Args:
            vehicle_id: ID del vehículo
        
        Returns:
            Mensaje de confirmación
        
        Raises:
            HTTPException 404: Si no existen violaciones para el vehículo
        """
        db: Session = request.state.db_session
        self.logger.info(f"Deleting violations for vehicle {vehicle_id}")
        
        try:
            violation = db.query(VehicleViolations).get(vehicle_id)
            if not violation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Violaciones para vehículo {vehicle_id} no encontradas"
                )
            
            db.delete(violation)
            db.flush()
            
            self.logger.info(f"Deleted violations for vehicle {vehicle_id}")
            return {
                "message": f"Violaciones del vehículo {vehicle_id} eliminadas exitosamente",
                "vehicle_id": vehicle_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting violations: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting violations: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )