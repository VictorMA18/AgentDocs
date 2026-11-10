# OrbitaMQ · jerarquía de excepciones (documento ficticio para pruebas)

Todas las excepciones de OrbitaMQ heredan de `OrbitaError`. Esta página lista la jerarquía completa.

## Raíz y familias

- `OrbitaError` (hereda de `Exception`): base de todo.
- `ConnectionFailure` (hereda de `OrbitaError`): problemas de red.
- `BrokerError` (hereda de `OrbitaError`): el broker rechaza o falla.
- `ClientError` (hereda de `OrbitaError`): uso incorrecto desde el cliente.

## Familia ConnectionFailure

- `DnsFailure` (hereda de `ConnectionFailure`): no se resuelve el nombre del broker.
- `ConnectRefused` (hereda de `ConnectionFailure`): el broker rechaza la conexión.
- `ConnectTimeoutError` (hereda de `ConnectionFailure`): la conexión no se establece a tiempo.
- `TlsHandshakeError` (hereda de `ConnectionFailure`): falla el acuerdo TLS.
- `ConnectionLost` (hereda de `ConnectionFailure`): la conexión se cae con la sesión abierta.

## Familia BrokerError

- `QuotaExceeded` (hereda de `BrokerError`): la cola alcanzó su cuota (código E-4021).
- `MessageTooLarge` (hereda de `BrokerError`): el mensaje supera el tamaño máximo.
- `DuplicateMessage` (hereda de `BrokerError`): `dedup_id` repetido (código E-4030).
- `QueueNotFound` (hereda de `BrokerError`): la cola no existe.
- `AckTimeout` (hereda de `BrokerError`): no llegó el acuse a tiempo (código E-4102).
- `RedeliveryExhausted` (hereda de `BrokerError`): se agotaron las reentregas (código E-4125).

## Familia ClientError

- `InvalidMessage` (hereda de `ClientError`): el mensaje no cumple el esquema.
- `SignatureError` (hereda de `ClientError`): firma inválida (código E-4012).
- `ConsumerClosed` (hereda de `ClientError`): se usa un consumidor ya cerrado.
- `ProducerClosed` (hereda de `ClientError`): se usa un productor ya cerrado.
- `ConfigurationError` (hereda de `ClientError`): parámetros de configuración incompatibles.
- `UnsupportedVersion` (hereda de `ClientError`): versión del protocolo no soportada.
