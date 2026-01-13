from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from db.session import DBSessionManager, DBSessionMiddleware
from db.entities.base import Base

from api.routers.crash_circumstances import CrashCircumstancesRouter
from api.routers.crash_classification import CrashClassificationRouter
from api.routers.crash_date import CrashDateRouter
from api.routers.crash_injuries import CrashInjuriesRouter
from api.routers.crashes import CrashesRouter
from api.routers.driver_info import DriverInfoRouter
from api.routers.people import PeopleRouter
from api.routers.vehicle_maneuvers import VehicleManeuversRouter
from api.routers.vehicle_models import VehicleModelsRouter
from api.routers.vehicle_violations import VehicleViolationsRouter
from api.routers.vehicle import VehicleRouter

from util.logger import LoggerSessionManager

logger_session_manager = LoggerSessionManager()
db_session_manager = DBSessionManager(logger_session_manager)

# Create DB tables
Base.metadata.create_all(bind=db_session_manager.engine)

# Instantiate all routers
crash_circumstances_router = CrashCircumstancesRouter(db_session_manager, logger_session_manager)
crash_classification_router = CrashClassificationRouter(db_session_manager, logger_session_manager)
crash_date_router = CrashDateRouter(db_session_manager, logger_session_manager)
crash_injuries_router = CrashInjuriesRouter(db_session_manager, logger_session_manager)
crashes_router = CrashesRouter(db_session_manager, logger_session_manager)
driver_info_router = DriverInfoRouter(db_session_manager, logger_session_manager)
people_router = PeopleRouter(db_session_manager, logger_session_manager)
vehicle_maneuvers_router = VehicleManeuversRouter(db_session_manager, logger_session_manager)
vehicle_models_router = VehicleModelsRouter(db_session_manager, logger_session_manager)
vehicle_violations_router = VehicleViolationsRouter(db_session_manager, logger_session_manager)
vehicle_router = VehicleRouter(db_session_manager, logger_session_manager)

# Create app
app = FastAPI(
    title="Traffic Crashes API",
    description="API CRUD para gestión de datos de accidentes de tráfico de Chicago",
    version="1.0.0"
)

# ==========================================
# HANDLER DE ERRORES 422 -> 400
# ==========================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Convierte errores de validación de Pydantic (422) a 400 Bad Request.
    
    Formatea los errores para que sean más legibles:
    - Muestra el campo que falló
    - Muestra el mensaje de error
    - Devuelve status 400 en lugar de 422
    """
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"][1:])  # Omite 'body'
        message = error["msg"]
        error_type = error["type"]
        
        # Formatear mensaje más amigable
        if error_type == "value_error":
            # Extraer el mensaje personalizado del ValueError
            if "Value error," in message:
                message = message.replace("Value error, ", "")
        elif error_type == "greater_than_equal":
            message = f"Debe ser mayor o igual a {error.get('ctx', {}).get('ge', '?')}"
        elif error_type == "less_than_equal":
            message = f"Debe ser menor o igual a {error.get('ctx', {}).get('le', '?')}"
        
        errors.append({
            "field": field,
            "message": message,
            "type": error_type
        })
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Error de validación en los datos proporcionados",
            "errors": errors
        }
    )


# Register routers
app.include_router(crash_circumstances_router.router)
app.include_router(crash_classification_router.router)
app.include_router(crash_date_router.router)
app.include_router(crash_injuries_router.router)
app.include_router(crashes_router.router)
app.include_router(driver_info_router.router)
app.include_router(people_router.router)
app.include_router(vehicle_maneuvers_router.router)
app.include_router(vehicle_models_router.router)
app.include_router(vehicle_violations_router.router)
app.include_router(vehicle_router.router)

# Register DB middleware
app.add_middleware(DBSessionMiddleware, db_session_manager=db_session_manager)

@app.get("/")
def root():
    return {
        "message": "Traffic Crashes API - FastAPI + SQLAlchemy",
        "docs": "/docs",
        "endpoints": 11
    }

#MONTAR LA API CON:
#uvicorn main:app --host 0.0.0.0 --port 8000 --reload

#Abrir puerto en firewall de Windows con PowerShell:
#New-NetFirewallRule -DisplayName "Permitir Puerto 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

#Cerrar puerto en firewall de Windows con PowerShell:
#Remove-NetFirewallRule -DisplayName "Permitir Puerto 8000"

