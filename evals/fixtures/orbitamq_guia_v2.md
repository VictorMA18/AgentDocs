# OrbitaMQ 2.x · guía de uso (documento ficticio para pruebas)

Esta es la guía de la versión 2.x de OrbitaMQ, un broker de mensajes ficticio. La versión 1.x tiene su propia guía con la misma estructura y valores distintos.

## Conexión

El broker escucha por defecto en el puerto 5671. La conexión usa TLS siempre; ya no existe la opción `tls`.

## Límites

El tamaño máximo de un mensaje es de 1 MB. Los mensajes mayores se rechazan con el error E-4001.

## Entrega

Un mensaje se reentrega hasta 5 veces antes de enviarse a la cola de mensajes muertos. La espera entre reentregas crece de forma exponencial desde 2 segundos.

## Confirmaciones por lotes

Para reducir el tráfico, el consumidor puede agrupar acuses:

- `ack_batch_size`: número de mensajes que se agrupan en un solo acuse. Por defecto 50.
- `ack_batch_window`: milisegundos máximos que se espera para completar un lote antes de enviarlo. Por defecto 200.
- `ack_window_ms`: tiempo máximo que el broker espera el acuse de un mensaje suelto. Por defecto 5000.
