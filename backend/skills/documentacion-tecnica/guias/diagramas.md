---
description: Cómo elegir el tipo de diagrama Mermaid, llamar a generar_diagrama, corregir errores y presentar el resultado.
---

# Guía · Diagramas
1. Recupera primero la información que sustenta el diagrama (componentes, flujos, entidades).
2. Elige el tipo adecuado:
   | Necesidad | Tipo (`tipo`) | Mermaid |
   |---|---|---|
   | Estructura de clases/módulos | `clases` | `classDiagram` |
   | Interacción en el tiempo | `secuencia` | `sequenceDiagram` |
   | Proceso o arquitectura simple | `flujo` / `componentes` | `flowchart TD` o `LR` |
   | Datos y relaciones | `entidad_relacion` | `erDiagram` |
   | Ciclo de vida | `estados` | `stateDiagram-v2` |
3. Llama a `generar_diagrama` con el código Mermaid **sin** delimitadores ```.
4. Si la herramienta devuelve errores, corrígelos y vuelve a llamarla (máximo 3 intentos).
   - **Excepción:** si el usuario te dio el código ya escrito y pidió guardarlo *tal cual*, no lo modifiques por tu cuenta. Muestra los errores que devolvió la herramienta, propón la versión corregida y pregunta si la guardas.
5. En tu respuesta, indica el **nombre del archivo guardado**, incluye el código Mermaid en un bloque ```mermaid y resume qué muestra el diagrama y qué partes provienen de la documentación y cuáles son supuestos.
6. **Un solo diagrama por petición**, en un único archivo (una llamada a `generar_diagrama`), salvo que el usuario pida varios. Si pasa de ~15 nodos, **simplifica en lugar de dividir**: agrupa o resume las hojas en un nodo (p. ej. "+ 6 subclases"), indica qué dejaste fuera y ofrece ampliar el detalle en otra petición.
7. Buenas prácticas: etiquetas cortas; identificadores sin espacios ni acentos; texto con caracteres especiales entre comillas.
