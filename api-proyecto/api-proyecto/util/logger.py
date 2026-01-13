import logging
from colorlog import ColoredFormatter
from typing import Optional

RESET = "\033[0m"
GRAY = "\033[90m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[97m"

LOG_FORMAT = (
    f"{RESET}{GRAY}%(asctime)s.%(msecs)03d{RESET} | "
    f"%(log_color)s%(levelname)-8s{RESET} | "
    f"{CYAN}%(name)s{RESET} | "
    f"{WHITE}%(message)s{RESET}"
)

class LoggerSessionManager:

    _instance: Optional["LoggerSessionManager"] = None

    def __new__(cls, *args, **kwargs):
        # Singleton pattern to ensure a single shared configuration
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str = "app", log_level: int = logging.INFO):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.log_level = log_level
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.logger.propagate = False

        console_format = ColoredFormatter(
            fmt=LOG_FORMAT,
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "blue",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            reset=True,
            style="%",
        )

        # --- Console Handler ---
        self.console_handler = logging.StreamHandler()
        self.console_handler.setLevel(log_level)
        self.console_handler.setFormatter(console_format)

        # --- Attach handler if none exist ---
        if not self.logger.handlers:
            self.logger.addHandler(self.console_handler)

        # --- Set frameworks logger handler ---
        for framework_logger in [
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
            "fastapi",
            "starlette",
            "sqlalchemy.engine",
            # "sqlalchemy.pool",
            # "sqlalchemy.orm",
        ]:
            framework_logger = logging.getLogger(framework_logger)
            framework_logger.handlers.clear()
            framework_logger.addHandler(self.console_handler)
            framework_logger.setLevel(self.log_level)
            framework_logger.propagate = False

        self._initialized = True

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        if name:
            return self.logger.getChild(name)
        return self.logger
