"""
Router para la tabla people.
Implementa endpoints CRUD con generación automática de person_id y validaciones.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.people import CreatePeople, ReadPeople, UpdatePeople
from db.entities.people import People
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.id_generators import generate_person_id
from util.validators import (
    validate_foreign_key_exists,
    validate_age,
)


class PeopleRouter:
    """
    Router para gestionar personas involucradas en crashes.
    
    Endpoints:
        GET /people - Lista todas las personas (paginado)
        GET /people/{person_id} - Obtiene una persona específica
        POST /people - Crea un nuevo registro (person_id autogenerado)
        PUT /people/{person_id} - Actualiza una persona
        DELETE /people/{person_id} - Elimina una persona
    """

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/people", tags=["People"])

        self.router.add_api_route(
            "/", 
            self.list, 
            methods=["GET"], 
            response_model=list[ReadPeople],
            summary="Lista personas",
            description="Obtiene una lista paginada de personas"
        )
        self.router.add_api_route(
            "/{person_id}", 
            self.get, 
            methods=["GET"], 
            response_model=ReadPeople,
            summary="Obtiene una persona",
            description="Obtiene una persona específica por su ID"
        )
        self.router.add_api_route(
            "/", 
            self.create, 
            methods=["POST"], 
            response_model=ReadPeople, 
            status_code=201,
            summary="Crea una persona",
            description="Crea un nuevo registro de persona con person_id autogenerado (formato Q0000001)"
        )
        self.router.add_api_route(
            "/{person_id}", 
            self.update, 
            methods=["PUT"], 
            response_model=ReadPeople,
            summary="Actualiza una persona",
            description="Actualiza los datos de una persona existente"
        )
        self.router.add_api_route(
            "/{person_id}", 
            self.delete, 
            methods=["DELETE"],
            summary="Elimina una persona",
            description="Elimina un registro de persona"
        )
    
    def list(self, request: Request, skip: int = 0, limit: int = 100):
        """Lista todas las personas con paginación."""
        db: Session = request.state.db_session
        self.logger.info(f"Listing people: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(
                status_code=400, 
                detail="El límite máximo es 1000 registros y el minimo es 0"
            )
        
        people = db.query(People).offset(skip).limit(limit).all()
        return people

    def get(self, person_id: str, request: Request):
        """Obtiene una persona específica por su ID."""
        db: Session = request.state.db_session
        self.logger.info(f"Getting person with id: {person_id}")
        
        person = db.query(People).get(person_id)
        if not person:
            raise HTTPException(
                status_code=404,
                detail=f"Persona {person_id} no encontrada"
            )
        
        return person

    def create(self, data: CreatePeople, request: Request):
        """
        Crea un nuevo registro de persona con person_id autogenerado.
        
        Genera automáticamente:
        - person_id: Formato Q0000001, Q0000002, etc.
        
        Validaciones:
        - crash_record_id debe existir en crashes (si se proporciona)
        - vehicle_id debe existir en vehicle (si se proporciona)
        - age debe estar entre 0 y 120
        """
        db: Session = request.state.db_session
        self.logger.info(f"Creating new person")
        
        try:
            # Validación: crash_record_id debe existir (si se proporciona)
            if data.crash_record_id:
                validate_foreign_key_exists(
                    db=db,
                    table_name="crashes",
                    column_name="crash_record_id",
                    value=data.crash_record_id
                )
            
            # Validación: vehicle_id debe existir (si se proporciona)
            if data.vehicle_id:
                validate_foreign_key_exists(
                    db=db,
                    table_name="vehicle",
                    column_name="vehicle_id",
                    value=data.vehicle_id
                )
            
            # Validación: Edad en rango válido
            if data.age is not None:
                validate_age(data.age)
            
            # Generar person_id automáticamente
            person_id = generate_person_id(db)
            
            self.logger.info(f"Generated person_id: {person_id}")
            
            # Crear la persona
            new_person = People(
                person_id=person_id,
                person_type=data.person_type,
                crash_record_id=data.crash_record_id,
                vehicle_id=data.vehicle_id,
                sex=data.sex,
                age=data.age,
                safety_equipment=data.safety_equipment,
                airbag_deployed=data.airbag_deployed,
                injury_classification=data.injury_classification
            )
            
            db.add(new_person)
            db.flush()
            
            self.logger.info(f"Created person with ID: {person_id}")
            return new_person
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error creating person: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad: crash_record_id o vehicle_id no válidos"
            )
        except ValueError as e:
            # Puede ocurrir si se alcanza el límite de Q9999999
            db.rollback()
            self.logger.error(f"Error generating person_id: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating person: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update(self, person_id: str, data: UpdatePeople, request: Request):
        """Actualiza un registro de persona existente."""
        db: Session = request.state.db_session
        self.logger.info(f"Updating person {person_id}")
        
        try:
            person = db.query(People).get(person_id)
            if not person:
                raise HTTPException(
                    status_code=404,
                    detail=f"Persona {person_id} no encontrada"
                )
            
            update_data = data.model_dump(exclude_unset=True)
            
            # Validar crash_record_id si se actualiza
            if 'crash_record_id' in update_data and update_data['crash_record_id']:
                validate_foreign_key_exists(
                    db=db,
                    table_name="crashes",
                    column_name="crash_record_id",
                    value=update_data['crash_record_id']
                )
            
            # Validar vehicle_id si se actualiza
            if 'vehicle_id' in update_data and update_data['vehicle_id']:
                validate_foreign_key_exists(
                    db=db,
                    table_name="vehicle",
                    column_name="vehicle_id",
                    value=update_data['vehicle_id']
                )
            
            # Validar edad si se actualiza
            if 'age' in update_data and update_data['age'] is not None:
                validate_age(update_data['age'])
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(person, key, value)
            
            db.flush()
            self.logger.info(f"Updated person {person_id}")
            return person
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error updating person: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad en la base de datos"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating person: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete(self, person_id: str, request: Request):
        """Elimina un registro de persona."""
        db: Session = request.state.db_session
        self.logger.info(f"Deleting person {person_id}")
        
        try:
            person = db.query(People).get(person_id)
            if not person:
                raise HTTPException(
                    status_code=404,
                    detail=f"Persona {person_id} no encontrada"
                )
            
            db.delete(person)
            db.flush()
            
            self.logger.info(f"Deleted person {person_id}")
            return {
                "message": f"Persona {person_id} eliminada exitosamente",
                "person_id": person_id
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error deleting person: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se puede eliminar la persona porque tiene registros "
                    "relacionados (por ejemplo, driver_info)"
                )
            )
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error deleting person: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )