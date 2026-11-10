# OrbitaMQ · referencia de errores y de la herramienta orbitactl (documento ficticio para pruebas)

OrbitaMQ es un broker de mensajes ficticio. Este documento lista sus códigos de error y las opciones de la herramienta de administración `orbitactl`. Los códigos se parecen entre sí a propósito: sirve para comprobar que la búsqueda distingue identificadores exactos.

## Errores de mensajes (familia E-40xx)

### E-4012
Firma del mensaje inválida. El productor firmó el mensaje con una clave que el broker no conoce. Solución: registrar la clave con `orbitactl keys add`.

### E-4021
Cuota de la cola excedida. La cola alcanzó su `quota_messages` y rechaza nuevos mensajes hasta que se consuma alguno. Solución: aumentar la cuota o añadir consumidores.

### E-4030
Mensaje duplicado. Ya existe un mensaje con el mismo `dedup_id` dentro de la ventana de deduplicación (10 minutos).

## Errores de entrega (familia E-41xx)

### E-4102
Tiempo de espera del confirmador agotado. El consumidor recibió el mensaje pero no envió el acuse (`ack`) dentro de `ack_timeout`. El mensaje vuelve a la cola. Solución: aumentar `ack_timeout` o confirmar antes de procesar el trabajo largo.

### E-4120
Consumidor desconectado sin confirmar. La conexión se cerró con mensajes pendientes de acuse; el broker los reentrega a otro consumidor.

### E-4125
Reentrega agotada. El mensaje superó el máximo de reentregas y pasa a la cola de mensajes muertos (`dead_letter`).

## Opciones de orbitactl

La herramienta `orbitactl` apaga y reinicia nodos del clúster.

### --drain-timeout
Segundos que espera `orbitactl stop` a que los consumidores terminen sus mensajes en curso antes de cerrar la conexión. Valor por defecto: 30.

### --drain-limit
Número máximo de mensajes que se siguen entregando mientras el nodo se vacía. Valor por defecto: 100.

### --grace-timeout
Segundos que espera `orbitactl restart` antes de forzar el reinicio si el nodo no responde. Valor por defecto: 15.
