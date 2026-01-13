from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.models.crash_circumstances import (
    CreateCrashCircumstances, 
    ReadCrashCircumstances,
    UpdateCrashCircumstances
)
from db.entities.crash_circumstances import CrashCircumstances
from db.session import DBSessionManager
from util.logger import LoggerSessionManager
from util.validators import (
    validate_foreign_key_exists,
    validate_non_negative,
    validate_string_length,
    normalize_boolean
)


class CrashCircumstancesRouter:
    """Router para gestionar circunstancias de crashes."""

    def __init__(self, db_session_manager: DBSessionManager, logger_session_manager: LoggerSessionManager):
        self.db_session_manager = db_session_manager
        self.logger = logger_session_manager.get_logger(__name__)

        self.router = APIRouter(prefix="/crash-circumstances", tags=["Crash Circumstances"])

        self.router.add_api_route("/", self.list, methods=["GET"], response_model=list[ReadCrashCircumstances])
        self.router.add_api_route("/{crash_record_id}", self.get, methods=["GET"], response_model=ReadCrashCircumstances)
        self.router.add_api_route("/", self.create, methods=["POST"], response_model=ReadCrashCircumstances, status_code=201)
        self.router.add_api_route("/{crash_record_id}", self.update, methods=["PUT"], response_model=ReadCrashCircumstances)
        self.router.add_api_route("/{crash_record_id}", self.delete, methods=["DELETE"])
    
    def list(self, request: Request, skip: int = 0, limit: int = 100):
        db: Session = request.state.db_session
        self.logger.info(f"Listing crash_circumstances: skip={skip}, limit={limit}")
        
        if limit > 1000 or limit < 0:
            raise HTTPException(status_code=400, detail="El límite máximo es 1000 registros y el minimo es 0")
        
        return db.query(CrashCircumstances).offset(skip).limit(limit).all()

    def get(self, crash_record_id: str, request: Request):
        db: Session = request.state.db_session
        circ = db.query(CrashCircumstances).get(crash_record_id)
        if not circ:
            raise HTTPException(
                status_code=404,
                detail=f"Circunstancias para crash {crash_record_id} no encontradas"
            )
        return circ

    def create(self, data: CreateCrashCircumstances, request: Request):
        """Crea circunstancias para un crash."""
        db: Session = request.state.db_session
        self.logger.info(f"Creating circumstances for crash {data.crash_record_id}")
        
        try:
            # Validar que el crash exista
            validate_foreign_key_exists(
                db=db,
                table_name="crashes",
                column_name="crash_record_id",
                value=data.crash_record_id
            )
            
            # Verificar duplicado
            existing = db.query(CrashCircumstances).get(data.crash_record_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existen circunstancias para el crash {data.crash_record_id}"
                )
            
            # Validar campos no negativos
            if data.lane_cnt is not None:
                validate_non_negative(data.lane_cnt, "lane_cnt")
            if data.num_units is not None:
                validate_non_negative(data.num_units, "num_units")
            if data.posted_speed_limit is not None:
                validate_non_negative(data.posted_speed_limit, "posted_speed_limit")
            
            # Normalizar booleanos
            data_dict = data.model_dump()
            if data_dict['intersection_related_i'] is not None:
                data_dict['intersection_related_i'] = normalize_boolean(data_dict['intersection_related_i'])
            if data_dict['not_right_of_way_i'] is not None:
                data_dict['not_right_of_way_i'] = normalize_boolean(data_dict['not_right_of_way_i'])
            
            # Crear registro
            new_circ = CrashCircumstances(**data_dict)
            db.add(new_circ)
            db.flush()
            
            self.logger.info(f"Created circumstances for crash {data.crash_record_id}")
            return new_circ
            
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Error de integridad: crash_record_id no válido")
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error creating circumstances: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

    def update(self, crash_record_id: str, data: UpdateCrashCircumstances, request: Request):
        db: Session = request.state.db_session
        
        try:
            circ = db.query(CrashCircumstances).get(crash_record_id)
            if not circ:
                raise HTTPException(status_code=404, detail=f"Circunstancias para crash {crash_record_id} no encontradas")
            
            update_data = data.model_dump(exclude_unset=True)
            
            # Validar no negativos
            if 'lane_cnt' in update_data and update_data['lane_cnt'] is not None:
                validate_non_negative(update_data['lane_cnt'], "lane_cnt")
            if 'num_units' in update_data and update_data['num_units'] is not None:
                validate_non_negative(update_data['num_units'], "num_units")
            if 'posted_speed_limit' in update_data and update_data['posted_speed_limit'] is not None:
                validate_non_negative(update_data['posted_speed_limit'], "posted_speed_limit")
            
            # Aplicar actualizaciones
            for key, value in update_data.items():
                setattr(circ, key, value)
            
            db.flush()
            return circ
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

    def delete(self, crash_record_id: str, request: Request):
        db: Session = request.state.db_session
        
        try:
            circ = db.query(CrashCircumstances).get(crash_record_id)
            if not circ:
                raise HTTPException(status_code=404, detail=f"Circunstancias para crash {crash_record_id} no encontradas")
            
            db.delete(circ)
            db.flush()
            
            return {"message": f"Circunstancias del crash {crash_record_id} eliminadas"}
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")