from fastapi import Request, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from util.logger import LoggerSessionManager
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

DATABASE_URL = "postgresql+psycopg2://user:password@localhost:5432/traffic_crashes"

class DBSessionManager:

    def __init__(
        self,
        logger_session_manager: LoggerSessionManager,
        db_url: str = DATABASE_URL,
        echo: bool = False,
    ):
        self.engine = create_engine(db_url, echo=echo, future=True)
        self.logger_session_manager = logger_session_manager
        self.logger = self.logger_session_manager.get_logger()
        self.SessionLocal = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, future=True
        )

    @contextmanager
    def get_managed_session(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


class DBSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db_session_manager: DBSessionManager):
        super().__init__(app)
        self.db_session_manager = db_session_manager

    async def dispatch(self, request: Request, call_next):
        with self.db_session_manager.get_managed_session() as db_session:
            request.state.db_session = db_session
            response: Response = await call_next(request)
            return response
