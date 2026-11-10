# OrbitaMQ 1.x · guía de uso (documento ficticio para pruebas)

Esta es la guía de la versión 1.x de OrbitaMQ, un broker de mensajes ficticio. La versión 2.x tiene su propia guía con la misma estructura y valores distintos.

## Conexión

El broker escucha por defecto en el puerto 5670. La conexión usa TCP sin cifrado salvo que se active `tls=true`.

## Límites

El tamaño máximo de un mensaje es de 256 KB. Los mensajes mayores se rechazan con el error E-4001.

## Entrega

Un mensaje se reentrega hasta 3 veces antes de enviarse a la cola de mensajes muertos. La espera entre reentregas es fija: 5 segundos.
