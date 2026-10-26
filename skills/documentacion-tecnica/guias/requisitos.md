---
description: Cómo redactar requisitos verificables (RF/RNF, MoSCoW, criterios de aceptación) y llamar a generar_requisitos.
---

# Guía · Requisitos
1. Recupera el contenido fuente (funcionalidades, restricciones, comportamientos).
2. Redacta cada requisito de forma **verificable**:
   - Funcional: "El sistema debe <verbo> <objeto> <condición>".
   - No funcional: con **métrica** (tiempo, porcentaje, límite).
3. Asigna prioridad MoSCoW (`M`, `S`, `C`, `W`) y un **criterio de aceptación** concreto.
4. Identificadores: `RF-01`, `RF-02`… y `RNF-01`… sin repetir.
5. Indica en `fuente` el documento/fragmento del que deduces el requisito. Si es una suposición tuya, déjalo vacío y menciónalo.
6. Llama a `generar_requisitos`; si devuelve errores, corrígelos y vuelve a llamar; si devuelve advertencias, explícalas al usuario. Indica el **nombre del archivo guardado** y resume los requisitos.
7. No inventes requisitos que no se deduzcan de la información; pregunta o márcalos como "propuesto".
