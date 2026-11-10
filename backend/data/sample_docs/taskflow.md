# TaskFlow (librería ficticia para pruebas)

TaskFlow es una librería de Python para ejecutar trabajos en segundo plano mediante una cola en memoria y un conjunto de workers. Este documento es **ficticio** y se usa solo para probar el agente.

## Instalación

Requiere Python 3.10 o superior.

```bash
pip install taskflow-lib
```

## Primeros pasos

Se crea una cola, se registra una función como tarea y se encolan trabajos:

```python
from taskflow import Queue, Worker

cola = Queue(maxsize=100)

@cola.task(name="enviar_correo")
def enviar_correo(destino: str, asunto: str) -> None:
    print(f"Enviando '{asunto}' a {destino}")

cola.enqueue("enviar_correo", destino="ana@example.com", asunto="Hola")

worker = Worker(cola)
worker.run()
```

## Cola (`Queue`)

`Queue(maxsize=100)` crea una cola en memoria. El parámetro `maxsize` limita cuántos trabajos pueden estar pendientes. Si se intenta encolar con la cola llena, se lanza la excepción `QueueFullError`.

El método `enqueue(nombre, **kwargs)` devuelve un `job_id` (cadena). Con `cola.status(job_id)` se consulta el estado, que puede ser `pending`, `running`, `done` o `failed`.

## Workers

`Worker(cola, concurrency=4)` procesa trabajos en paralelo. El valor por defecto de `concurrency` es 4. Cada worker toma el siguiente trabajo `pending`, cambia su estado a `running` y ejecuta la función registrada; al terminar lo marca `done`, o `failed` si agotó los reintentos.

El método `worker.run()` bloquea hasta recibir una señal de parada. Para detenerlo de forma ordenada se usa `worker.stop(timeout=30)`, que espera hasta 30 segundos a que terminen los trabajos en curso.

## Reintentos

Cada tarea admite reintentos automáticos cuando lanza una excepción:

```python
@cola.task(name="sincronizar", max_retries=3, backoff_base=2)
def sincronizar(recurso_id: int) -> None:
    ...
```

- `max_retries` indica el número de reintentos. El valor por defecto es **3**.
- `backoff_base` define la espera exponencial entre reintentos: la espera es `backoff_base ** intento` segundos. El valor por defecto es 2 segundos.
- Si se agotan los reintentos, el trabajo pasa a `failed` y se invoca el callback `on_failure` si existe.

```python
def avisar(job_id: str, error: Exception) -> None:
    print(f"Falló {job_id}: {error}")

cola.on_failure(avisar)
```

## Errores comunes

| Excepción | Cuándo ocurre |
|---|---|
| `QueueFullError` | La cola alcanzó `maxsize` al encolar |
| `UnknownTaskError` | Se encola un nombre de tarea no registrado |
| `JobNotFoundError` | Se consulta un `job_id` inexistente |

## Limitaciones

TaskFlow guarda la cola solo en memoria: si el proceso se reinicia, los trabajos pendientes se pierden. No incluye persistencia ni integración con orquestadores de contenedores.
