# LumenCache (librería ficticia para pruebas)

LumenCache es una librería de Python para guardar en caché el resultado de funciones costosas. Ofrece un decorador, expiración por tiempo (TTL), un límite de entradas y varios almacenamientos (backends). Este documento es **ficticio** y se usa solo para probar el agente.

## Instalación

Requiere Python 3.11 o superior.

```bash
pip install lumen-cache
pip install "lumen-cache[redis]"   # añade el backend de Redis
```

## Primeros pasos

Se crea una caché y se decora la función cuyo resultado se quiere reutilizar:

```python
from lumencache import Cache

cache = Cache(namespace="catalogo", ttl=120)

@cache.cached(ttl=60)
def precio_producto(producto_id: int) -> float:
    return consultar_base_de_datos(producto_id)

precio_producto(7)   # calcula y guarda
precio_producto(7)   # responde desde la caché
```

La clave de cada entrada se construye con el nombre de la función y sus argumentos. Los argumentos deben poder convertirse a texto estable; si no, se lanza `UnhashableKeyError`.

## Configuración de `Cache`

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `ttl` | 300 | Segundos de vida de una entrada. `None` la mantiene hasta que se expulse |
| `max_entries` | 1000 | Máximo de entradas guardadas |
| `policy` | `"lru"` | Política de expulsión: `"lru"` o `"fifo"` |
| `backend` | `"memory"` | Almacenamiento: `"memory"`, `"disk"` o `"redis"` |
| `namespace` | `"default"` | Prefijo que separa las claves de varias cachés |
| `max_value_mb` | 5 | Tamaño máximo de un valor; uno mayor lanza `ValueTooLargeError` |

Un `ttl` indicado en `@cache.cached(ttl=60)` tiene prioridad sobre el de `Cache(...)`.

## Backends

- **`memory`**: el más rápido. Los datos se pierden al terminar el proceso.
- **`disk`**: guarda en la carpeta `.lumen/` del directorio actual. Se cambia con `Cache(backend="disk", path="/tmp/cache")`. Sobrevive a reinicios.
- **`redis`**: requiere la opción `[redis]` y el parámetro `url`, por ejemplo `Cache(backend="redis", url="redis://localhost:6379/0")`. Si Redis no responde en 2 segundos se lanza `BackendUnavailableError`.

## Expulsión de entradas

Cuando la caché llega a `max_entries`, se elimina una entrada antes de guardar la nueva. Con `policy="lru"` se expulsa la usada hace más tiempo; con `"fifo"`, la más antigua. Las entradas vencidas por `ttl` se borran al consultarlas, no en segundo plano.

## Invalidación

```python
cache.invalidate("precio_producto:7")     # una clave exacta
cache.invalidate_prefix("precio_")        # todas las que empiezan así
cache.clear()                             # todo el namespace
```

`invalidate` devuelve `True` si la clave existía y `False` si no. `clear()` solo borra el namespace de esa caché, no las demás.

## Estadísticas

`cache.stats()` devuelve un objeto con `hits`, `misses`, `evictions` y `hit_ratio` (aciertos entre consultas totales, de 0 a 1). Las estadísticas se reinician con `cache.reset_stats()`.

## Serialización

Los valores se guardan como JSON por defecto. Para objetos que JSON no admite se indica `serializer="pickle"`; no debe usarse con el backend `redis` compartido con otros servicios, porque `pickle` ejecuta código al leer.

## Errores comunes

| Excepción | Cuándo ocurre |
|---|---|
| `UnhashableKeyError` | Los argumentos de la función no producen una clave estable |
| `ValueTooLargeError` | El valor supera `max_value_mb` |
| `BackendUnavailableError` | El backend `redis` no responde en 2 segundos |
| `NamespaceError` | El namespace contiene espacios o más de 40 caracteres |

## Cambios de versión

- **1.4**: `invalidate_prefix` sustituye a `invalidate_all(prefix)`, que queda obsoleto y se eliminará en la 2.0.
- **1.3**: el valor por defecto de `ttl` pasó de 600 a 300 segundos.

## Limitaciones

LumenCache no es seguro entre procesos con el backend `memory`: cada proceso tiene su propia caché. No admite funciones `async` (previsto para la 2.0) ni bloqueos distribuidos, por lo que dos procesos pueden calcular a la vez el mismo valor.
