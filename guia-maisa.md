# Guía del equipo · Track Maisa · 500 Sombras de Alberto

Equipo **hUMAnos** · HackSpain 2026 · actualizado 2026-09-18

> Esta guía resume el reto para decidir producto rápido. El enunciado literal está en [`reto-maisa.md`](reto-maisa.md). Lo que es **interpretación nuestra** va marcado como *(propuesta)* o *(hipótesis)*. Lo que no está confirmado, en la sección final.

---

## 1. Resumen en 30 segundos

Construimos un sistema que decide **PAGAR / NO_PAGAR / ESCALAR** para cada factura de una Caja de 500 PDFs (más 40 el sábado) y lo defendemos 10 minutos ante el tribunal de Maisa.

- **Apto / no apto:** un resultado correcto y único por archivo en los dos lotes. Sin eso no hay premio. No da puntos, no desempata y no hay ranking.
- **Los puntos salen de la defensa** y del PDF de arquitectura, no de los aciertos.
- **Formato libre** (CLI, backend, herramienta para agentes, web...). No puntúa el tamaño; hay que defender por qué el formato es el adecuado.
- **Premio:** viaje a las oficinas de Maisa en Valencia y un teclado para cada integrante.
- **Riesgos clave:** norma v4 y lote sorpresa el sábado, cambio de un dato de la Caja el domingo, y entrega el domingo por la mañana.

## 2. Reglas que no se pueden romper

| # | Regla | Consecuencia si se rompe |
|---|---|---|
| 1 | Un registro **único** por archivo, en **ambos** lotes | No aptos: sin premio |
| 2 | `file_id` = nombre **exacto** del PDF; `result` ∈ `PAGAR`, `NO_PAGAR`, `ESCALAR` | Registro no válido |
| 3 | El repo de entrega es **público y separado** de nuestra solución | Incumplimiento de reglas |
| 4 | La raíz del repo de entrega contiene **exactamente** 3 archivos: `outcomes.jsonl`, `outcomes_lote2.jsonl`, `albertitos_plan.pdf` | Entrega inválida |
| 5 | **No subir** solución, código, credenciales ni ejecutables al repo de entrega | Incumplimiento de reglas |
| 6 | Compartir el `teamId` y la URL del repo de entrega | La organización no puede clonarlo |
| 7 | Entrega **antes de la hora límite** (ver sección 5) | Se registra el commit a esa hora |

La organización **no ejecuta nuestro código ni pide credenciales**: solo corre su verificador sobre los dos JSONL.

## 3. Puntuación

Máximo 110 puntos (100 + 10 de bonus). Desempate: escalabilidad y coste, luego resiliencia, luego bonus, y por último decisión motivada del tribunal.

| Criterio | Pts | Qué tenemos que poder enseñar |
|---|---:|---|
| Producto, arquitectura y ADRs | 35 | Problema, formato elegido, arquitectura y 2-5 decisiones con alternativas |
| Escalabilidad y coste | 25 | Archivos/s, hardware, límites, **fórmula de coste** y plan para nuevos tipos de archivo |
| Trazabilidad y observabilidad | 20 | Seguir una decisión real: estado, evidencia, versiones, latencia, errores, reintentos, pendiente |
| Resiliencia y recuperación | 10 | Fallo del LLM: qué se conserva, cómo se evitan duplicados, cómo se degrada y recupera |
| Calidad de ejecución | 10 | Solución clara, proporcionada y agradable de operar |
| Bonus | +10 | Necesidad adicional de Alberto, implementada y **mostrada** |

**Lecturas útiles para producto:**
- Escalabilidad y coste (25) es el **primer desempate**: medir desde la primera ejecución.
- **Separar mediciones de estimaciones** en la defensa. Lo piden explícitamente.
- Bonus: no cuentan propuestas, maquetas, cambios cosméticos ni algo necesario para el flujo principal. Tampoco es el lote del sábado.
- Lo que **no** piden: un benchmark de OCR, una demo de un modelo aislado, una promesa abstracta de escala ni alta disponibilidad perfecta. Sí una estrategia honesta cuando el proveedor falla.

## 4. Entrega

```text
la-caja-outcomes/            # repo público, separado de nuestra solución
├── outcomes.jsonl           # lote inicial (500 facturas)
├── outcomes_lote2.jsonl     # lote del sábado (40 facturas)
└── albertitos_plan.pdf      # arquitectura + 2-5 ADRs
```

Contrato del JSONL (los campos de traza extra son opcionales):

```json
{"file_id":"factura_5518.pdf","result":"PAGAR"}
{"file_id":"FA-4475_informática.pdf","result":"ESCALAR"}
```

**`albertitos_plan.pdf`** tiene dos secciones:
- **Arquitectura:** componentes, flujo de datos y estado, reparto entre agentes, modelos y personas, y cómo se observan y recuperan los fallos.
- **ADRs / trade-offs:** de 2 a 5 decisiones, cada una con contexto, alternativas, decisión, consecuencias aceptadas y evidencia.

Si falta o es flojo no nos deja no aptos, pero puede dejarnos **sin los 35 puntos** de producto. El tribunal puede preguntar por cualquier decisión que aparezca en él.

## 5. Calendario

Horas de Madrid.

| Cuándo | Qué pasa |
|---|---|
| Vie 18 sep · 21:00 | Enunciado, rúbrica y Caja de Alberto v3.2 |
| Sáb 19 sep · 18:00 | **Lote 2** (40 facturas), ERP actualizado y **norma v4** |
| Dom 20 sep · mañana | **Cambio de un dato de la Caja** para comprobar que la demo es real (hay que reprocesar) |
| Dom 20 sep · **10:30 u 11:00** | Cierre de entrega: se clona el repo y se registra el commit |
| Dom 20 sep · por confirmar | Defensa de 10 minutos |

**Discrepancia de hora:** el `README` de la Caja dice **10:30** y la web del reto dice **11:00**. Hasta confirmarlo con los mentores, **trabajamos con 10:30**.

## 6. La defensa (10 minutos)

| Bloque | Min | Contenido |
|---|---:|---|
| Demo y contexto | 2 | Solución funcionando y problema concreto de Alberto; bonus si lo hay |
| Arquitectura y ADRs | 2 | Formato, arquitectura, agentes/modelos/personas y decisiones registradas |
| Trazabilidad, escala y coste | 4 | Seguir una decisión real, señales operativas, capacidad, hardware, fórmula de coste y supuestos, evolución ante emails/imágenes/Excel |
| Resiliencia y preguntas | 2 | Demostrar o explicar un timeout, rate limit, respuesta inválida o caída del proveedor |

El bloque de 4 minutos es el más pesado y necesita **números reales**.

## 7. Qué hay en la Caja (hallazgos)

Repo de la Caja: [ikurotime/500-sombras-de-alberto](https://github.com/ikurotime/500-sombras-de-alberto).

| Elemento | Detalle |
|---|---|
| `facturas/` | **500 PDFs** con nombres muy heterogéneos: `2026-01-08_P001.pdf`, `factura_5518.pdf`, `FA-4475_informática.pdf`, `F26-9300_ofimática.pdf`, `2026-14406_limpiezas.pdf`, `scan_001.pdf`, `fax_2026_0411.pdf`, `copia_2026_0518.pdf`, `reimpresion_0712.pdf` |
| Escaneados | 26 archivos `scan_*` (del 001 al 029, faltan 019, 020 y 024). Necesitan OCR o un modelo con visión |
| `FINAL_v7_DEFINITIVO_ahorasi.xlsx` | El "Excel caótico": proveedores, pedidos y normas de pago. **Aún sin analizar** |
| `alberto_erp.py` | El ERP de 2009 (ver sección 8) |
| `MANUAL_ERP_2009.md` | Endpoints, sesiones y códigos de error |
| `Makefile` | Atajos del ERP (`make` no está en Windows, ver sección 10) |

**Hipótesis sobre los datos (sin verificar):**
- Los prefijos `copia_`, `reimpresion_` y `fax_` y los sufijos `2` (`limpiezas2`, `mensajería2`) sugieren **facturas duplicadas o reimpresas**. Un duplicado puede pedir NO_PAGAR o ESCALAR, no un segundo PAGAR.
- La variedad de formatos de nombre sugiere plantillas de proveedor distintas: la extracción no puede depender de un solo formato.
- `file_id` es el nombre exacto del archivo, incluidos acentos (`informática`). Cuidado con la normalización Unicode en Windows.

## 8. El ERP de 2009

Corre en **nuestra máquina** (`http://127.0.0.1:8009`) y es deliberadamente hostil.

| Rareza | Qué hacer |
|---|---|
| Sesión caduca a los **15 min o 300 consultas** (`SES-401`) | Renovar el token en `/erp/login` |
| `ORA-00600` (HTTP 500) aleatorio | **Reintentar la misma consulta**; un cliente que no reintenta no llega a la página 26 |
| `ERP-429` con `Retry-After` | Esperar lo que indique |
| `ERP-400` / `ERP-404` | Página o identificador inválido |
| Respuestas en **XML ISO-8859-1** | Decodificar bien; no asumir UTF-8 |
| Fechas `DD/MM/AAAA` e importes `12.874,40` (punto de miles, coma decimal) | Parsear con formato español |
| Asientos: 20 por página, con `total` y `paginas` en `<meta>` | Paginar completo |
| Latencia artificial | `--rapido` la quita, **solo para tests locales** |
| Estados de asiento: `PENDIENTE` o `PAGADA` | Posible señal para no pagar dos veces *(hipótesis)* |

**Consejos del propio manual:** descargar los asientos **una vez** y trabajar en local. Los datos del ERP son la **referencia contable oficial para conciliar**. Cada asiento trae `id`, `fecha`, `proveedor`, `nif`, `pedido`, `importe` y `estado`.

Para el sábado: `python alberto_erp.py --lote2 ruta/erp_export_lote2.csv`.

## 9. Maisa y el KPU: qué les convence

Maisa vende "Digital Workers": agentes que ejecutan procesos de negocio completos, con decisiones trazables y resistentes a las alucinaciones ([maisa.ai](https://maisa.ai/)). Su **KPU** separa tres piezas ([The Decoder, 2024](https://the-decoder.com/maisas-knowledge-processing-unit-boosts-language-models-reasoning-capabilities/)):

| Pieza | Función |
|---|---|
| Reasoning Engine | El LLM planifica paso a paso |
| Execution Engine | El código ejecuta cada paso y devuelve el resultado |
| Virtual Context Window | Los datos viven fuera del LLM; el modelo razona sobre referencias |

**Patrón que podemos imitar sin usar su tecnología:**
- El LLM interpreta y planifica; el **código determinista aplica las reglas de pago**.
- Los datos no viajan en el prompt, se pasan por referencia.
- Cada paso queda registrado: esa es la traza de auditoría.
- Ante la duda, **ESCALAR** en lugar de adivinar.

*(Inferencia nuestra sobre lo que valoran: proceso de extremo a extremo, decisiones explicables, fiabilidad por diseño, humano en el bucle y coste por ejecución bajo.)*

## 10. Entorno de trabajo (Windows)

- **`make` no está instalado.** Usar `python alberto_erp.py` (o `--rapido`); el `Makefile` solo envuelve esos comandos.
- **`python3` no funciona** (es un acceso directo a la Microsoft Store); **`python`** es 3.11.
- Disponibles: `pdftotext` (Git Bash) y `pandas`.
- **No disponibles:** `tesseract` (OCR) y `openpyxl` (leer el `.xlsx`). Hay que instalarlos o usar un modelo con visión.
- Los datos de la Caja son **sintéticos**.

## 11. Decisiones de producto abiertas

La columna "Propuesta" es una **sugerencia inicial**, no un acuerdo. Cada decisión que tomemos es candidata a ADR; necesitamos entre 2 y 5 para el PDF.

| # | Decisión | Opciones | Propuesta | Decidir |
|---|---|---|---|---|
| 1 | Formato del producto | CLI / backend / herramienta para agentes / web | Pipeline por lotes en CLI con un visor mínimo de trazas para la demo | Hoy |
| 2 | Lenguaje y stack | Python / TypeScript / otro | Python (PDF, OCR, datos); confirmar con lo que domina el equipo | Hoy |
| 3 | Extracción de PDF | Texto directo + OCR / LLM con visión para todo | Texto directo, OCR para escaneadas y LLM solo donde falle | Con el análisis de datos |
| 4 | Dónde viven las reglas de pago | Código determinista / prompts | Código con reglas en **configuración versionada** (norma v4) | Con el análisis del Excel |
| 5 | Criterio de ESCALAR | Umbral de confianza / reglas explícitas / ambos | Reglas explícitas primero; confianza baja como red de seguridad | Con el análisis de datos |
| 6 | Traza y estado | SQLite / JSONL / Postgres | Registro de eventos por factura en SQLite, exportable a JSONL | Hoy |
| 7 | Ejecución y recuperación | Secuencial / concurrente con cola | Concurrente, idempotente por `file_id`, con reintentos y backoff | Tras el análisis |
| 8 | Modelo LLM y coste | Un modelo / barato + escalado a uno fuerte | Modelo barato por defecto y **coste por factura medido** | Tras el análisis |
| 9 | Reprocesado del domingo | Rehacer todo / recalcular solo lo afectado | Trazar dependencias dato → decisión para reprocesar solo lo afectado | Tras el análisis |
| 10 | Bonus (+10) | Necesidad extra de Alberto | Por definir tras ver Excel y ERP | Sábado |
| 11 | Reparto del equipo | Extracción / reglas y ERP / trazas y métricas / PDF y defensa | Por definir entre las 4 personas | Hoy |

**Cuatro cosas que condicionan lo demás:**
1. Las reglas deben poder cambiar el sábado sin reescribir código (**norma v4**).
2. Rendimiento y coste se **miden desde la primera ejecución**, no al final.
3. El pipeline debe **garantizar un registro por archivo**: un archivo sin resultado o con dos nos deja no aptos.
4. Debe poder **reprocesar** el domingo cuando cambie un dato de la Caja, y explicar qué decisiones se ven afectadas.

## 12. Riesgos

| Riesgo | Mitigación propuesta |
|---|---|
| La norma v4 del sábado rompe las reglas | Reglas en configuración y tests sobre casos conocidos |
| El domingo cambia un dato de la Caja | Trazabilidad dato → decisión y reprocesado selectivo |
| Facturas escaneadas mal leídas | OCR con fallback; ESCALAR si falta un dato clave |
| Facturas duplicadas o reimpresas | Detección de duplicados por proveedor, número e importe *(hipótesis)* |
| Archivo duplicado o sin resultado en el JSONL | Validador local: un registro por PDF en cada lote |
| El ERP falla (`ORA-00600`, `ERP-429`, sesión caducada) | Cliente con reintentos y renovación de token; caché local de asientos |
| Caída o límite de tasa del LLM | Reintentos con backoff, reanudación sin duplicados y degradación a ESCALAR |
| Se sube código o credenciales al repo de entrega | Repo aparte con solo tres archivos |
| Sin tiempo para el PDF | Redactar los ADRs a medida que se decide |
| Hora de entrega equivocada (10:30 vs 11:00) | Trabajar con 10:30 |

## 13. Checklist

- [x] Equipo creado y repo vinculado con `hackspain team repo`
- [x] Pista Maisa registrada en la CLI de HackSpain
- [x] Caja clonada (`ikurotime/500-sombras-de-alberto`)
- [ ] Confirmar hora de entrega (10:30 u 11:00) con los mentores
- [ ] Decidir las decisiones "Hoy" de la sección 11
- [ ] Analizar el Excel (`FINAL_v7_DEFINITIVO_ahorasi.xlsx`) y extraer las reglas de pago
- [ ] Arrancar el ERP y descargar los asientos una vez
- [ ] Extraer texto de los 500 PDFs y clasificar los escaneados
- [ ] Procesar el lote inicial y generar `outcomes.jsonl`
- [ ] Sábado 18:00: cargar lote 2, ERP actualizado y norma v4; generar `outcomes_lote2.jsonl`
- [ ] Validar en local: un registro único por `file_id` en los dos lotes
- [ ] Medir archivos/s, hardware y coste por factura
- [ ] Ensayar un fallo del LLM para la demo
- [ ] Escribir `albertitos_plan.pdf` (arquitectura + 2-5 ADRs)
- [ ] Crear el repo público de entrega con solo los 3 archivos en la raíz
- [ ] Compartir el `teamId` y la URL del repo de entrega
- [ ] Pedir un simulacro de defensa a los mentores de Maisa (camisetas verdes)

## 14. Sin confirmar

- **Hora de entrega:** 10:30 (README de la Caja) frente a 11:00 (web).
- **Hora de la defensa:** por confirmar por la organización.
- **Reglas de pago reales:** están en el Excel y en la norma v4; todavía no las hemos leído.
- **KPU:** la descripción técnica es de 2024; el producto actual (Vinci KPU) puede diferir.
- **Duplicados y reimpresiones:** son una hipótesis a partir de los nombres de archivo.

## 15. Fuentes

- Enunciado del reto: [hackathon.maisa.ai](https://hackathon.maisa.ai/#reto) (copia en [`reto-maisa.md`](reto-maisa.md))
- Caja de Alberto: [ikurotime/500-sombras-de-alberto](https://github.com/ikurotime/500-sombras-de-alberto) (`README.md`, `MANUAL_ERP_2009.md`, `Makefile`)
- Maisa: [maisa.ai](https://maisa.ai/) y [The Decoder](https://the-decoder.com/maisas-knowledge-processing-unit-boosts-language-models-reasoning-capabilities/)
