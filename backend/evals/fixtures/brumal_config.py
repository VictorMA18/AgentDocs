"""Configuración de BrumalClient (librería ficticia para pruebas)."""


class PoolConfig:
    def __init__(self, max_connections: int | None = None, idle_seconds: float = 30.0) -> None:
        self.max_connections = max_connections
        self.idle_seconds = idle_seconds


# Valores que usa BrumalClient cuando el usuario no pasa un PoolConfig propio.
DEFAULT_POOL = PoolConfig(max_connections=40, idle_seconds=30.0)
DEFAULT_READ_TIMEOUT = 8.0
