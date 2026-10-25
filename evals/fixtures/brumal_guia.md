# BrumalClient · guía de uso (librería ficticia para pruebas)

BrumalClient es un cliente HTTP ficticio. Esta guía describe su configuración básica.

## Instalación

Requiere Python 3.11 o superior: `pip install brumal`.

## Pool de conexiones

BrumalClient mantiene un pool de conexiones reutilizables. Se configura con `PoolConfig` y se pasa al crear el cliente:

```python
from brumal import BrumalClient, PoolConfig

client = BrumalClient(pool=PoolConfig(max_connections=10, idle_seconds=60))
```

- `max_connections`: número máximo de conexiones simultáneas, o `None` para no limitarlo.
- `idle_seconds`: segundos que una conexión inactiva se conserva en el pool.

## Tiempos de espera

El tiempo de espera de lectura es de 8 segundos salvo que se indique otro con `timeout=`.
