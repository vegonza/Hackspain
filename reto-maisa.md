Fuente: [web oficial del reto](https://hackathon.maisa.ai/#reto)

Revisado contra la web el 19 de septiembre de 2026. Texto del reto conservado sin resumir; se omiten navegación y bloques promocionales.

[ MAISA HACKSPAIN · 2026 ]

# 500 Sombras de Alberto

Construid una solución para el mundo de Alberto: 500 facturas, un Excel y un ERP legado. Elegid el formato que el problema merezca y defended por qué.

500 Sombras de Alberto

## Qué hay que construir

Una solución para que Alberto pueda confiaros una operación real. El formato lo elegís vosotros.

Documento → decisión → evidencia

EL CASO COMÚN

Recibís 500 facturas PDF —algunas escaneadas—, un Excel de proveedores, pedidos y normas de pago, y un ERP local de 2009. Decidid para cada factura: PAGAR, NO_PAGAR o ESCALAR. Todos los datos son sintéticos.

VALIDACIÓN OBLIGATORIA

Un resultado correcto y único por cada archivo de ambos lotes. La organización comprueba los resultados con una referencia privada: apto o no apto, sin puntos.

FORMATO LIBRE

Backend, herramienta para agentes, CLI, aplicación web u otra propuesta. Elegid el formato que resuelva mejor el problema y defended por qué.

18–20 SEPTIEMBRE · ETSIT UPM, MADRID

Equipos de 2 a 5 personas, hasta 15 equipos. No se exige un stack, una interfaz ni un formato de trazabilidad concretos.

ANTES DE CONSTRUIR

## Decidid cómo resolverlo

El tamaño de la aplicación no puntúa. Importa que el producto y sus decisiones de ingeniería respondan al trabajo de Alberto.

Reservad tiempo para validar los dos lotes y preparar la defensa.

El formato al servicio del problema

PRODUCTO Y DECISIONES

### Elegid con criterio

Definid quién lo usa y qué trabajo le ahorra. Recoged la arquitectura y de 2 a 5 ADRs en albertitos_plan.pdf: contexto, alternativas, decisión, consecuencias y evidencia.

Conectar cada decisión con su origen

OPERACIÓN AUDITABLE

### Seguid una decisión

Conectad input, estado, evidencia, reglas o modelo y resultado. Mostrad cómo detectar errores, reintentos, trabajo pendiente y coste.

Capacidad, coste y límites del sistema

ESCALA Y FALLOS

### Probad los límites

Medid o estimad archivos por segundo, hardware y coste por archivo o lote. Ensayad un fallo del proveedor y explicad cómo añadiríais nuevos tipos de archivo.

SÁBADO · 18:00

## Parte adicional del reto

Alberto añade otro lote y una regla nueva. El domingo también podrá cambiar un dato de la Caja para comprobar la demo.

Incorporar el cambio y revisar su impacto

+40 FACTURAS ERP ACTUALIZADO

Integrad el cambio, conservad el trabajo y explicad qué decisiones debéis reprocesar.

DEBÉIS MOSTRAR

Qué cambia, cómo seguís su impacto y cuáles son los límites del sistema. No se puntúa un conteo de aciertos: se evalúan arquitectura, observabilidad y recuperación.

TRIBUNAL · 100 PUNTOS + 10 DE BONUS

## Criterios de evaluación

La validación decide la elegibilidad. Un mismo tribunal evalúa todos los proyectos: 100 puntos base y hasta 10 extra por una mejora adicional para Alberto.

VALIDACIÓN FUNCIONAL

**APTO** O NO APTO

UN REGISTRO ÚNICO POR ARCHIVO · AMBOS LOTES · RESULTADO ACEPTADO

Solo se validan file_id y result. No suma puntos, no genera un ranking ni desempata. Si no sois aptos, podéis defender el proyecto y recibir feedback, pero no optar al premio. El PDF se evalúa en Producto, arquitectura y ADRs; no forma parte de esta validación.

RÚBRICA DEL TRIBUNAL 100 + 10 PTS

**Producto, arquitectura y ADRs**

Defended el problema, el formato, la arquitectura y las decisiones, alternativas y trade-offs recogidos en albertitos_plan.pdf.

**35** pts

**Trazabilidad y observabilidad**

Seguid una decisión real y mostrad estado, evidencia, versiones, latencia, errores, reintentos y trabajo pendiente.

**20** pts

**Escalabilidad y coste**

Aportad capacidad, hardware, límites, fórmula de coste y un plan para incorporar más volumen y nuevos tipos de archivo.

**25** pts

**Resiliencia y recuperación**

Explicad cómo conserváis el estado, evitáis duplicados, degradáis el servicio y recuperáis el trabajo ante fallos del proveedor de LLM.

**10** pts

**Calidad de ejecución**

Una solución clara, proporcionada y agradable de operar, con decisiones útiles para Alberto.

**10** pts

**Bonus: mejora adicional para Alberto**

Hasta 10 puntos por resolver una necesidad concreta con una mejora original, implementada y mostrada en la defensa. No cuentan propuestas, maquetas, cambios cosméticos ni partes necesarias del flujo principal. Es opcional y distinto del lote adicional del sábado.

**+10** máx.

Desempates: primero escalabilidad y coste; después resiliencia; después el bonus de mejora adicional; finalmente, decisión motivada del tribunal.

ENTREGA PARA VALIDACIÓN Y DEFENSA

## Tres archivos. Un repositorio.

Compartid vuestro teamId y la URL de un repositorio público de GitHub separado de vuestra solución. Su raíz debe contener exactamente los dos JSONL y albertitos_plan.pdf.

FECHA LÍMITE **DOM 20 · 11:00** Hora de Madrid. La organización clonará el repositorio y registrará el commit a esa hora.

### 01 · Identificad al equipo

Compartid el teamId y la URL pública de GitHub para que la organización pueda clonar la entrega.

### 02 · outcomes.jsonl

Los resultados del lote inicial: un objeto JSON por cada factura, en una línea independiente.

### 03 · outcomes_lote2.jsonl

Los resultados del lote adicional del sábado, con un registro único por archivo.

### 04 · albertitos_plan.pdf

La única documentación requerida. Incluid dos secciones: Arquitectura y ADRs / trade-offs, con entre 2 y 5 decisiones relevantes.

```
outcomes.jsonl
outcomes_lote2.jsonl
albertitos_plan.pdf
```

### El contrato de los JSONL

file_id es el nombre exacto del PDF. result debe ser PAGAR, NO_PAGAR o ESCALAR. Incluid un objeto por factura; los campos de traza son opcionales.

```
{"file_id":"factura_123.pdf","result":"PAGAR"}
```

### Qué debe explicar el plan

**Arquitectura:** componentes, flujo de datos y estado, reparto entre agentes, modelos y personas, trazabilidad y recuperación de fallos.

**ADRs / trade-offs:** de 2 a 5 decisiones con contexto, alternativas consideradas, decisión, consecuencias aceptadas y evidencia. Un documento breve es suficiente si permite defender vuestro criterio.

**Importante:** la ausencia o mala calidad del PDF no elimina la elegibilidad si los dos JSONL son correctos, pero puede dejar sin puntos el criterio de Producto, arquitectura y ADRs (35 puntos). El tribunal podrá preguntar por cualquier decisión, alternativa o trade-off registrado.

No subáis vuestra solución, código, credenciales ni una aplicación ejecutable. La organización solo ejecutará su verificador sobre los dos JSONL: no ejecutará vuestro código ni pedirá credenciales.

18–20 SEPTIEMBRE

## Fechas y materiales

Todos los horarios son de Madrid. Los paquetes y sus hashes se distribuyen en el canal del track cuando corresponda.

Dos JSONL y un plan de arquitectura

Hitos de entrega y defensa

| DÍA | HORA | ACTIVIDAD |
| --- | --- | --- |
| VIE 18 | 19:00 | Comienza la hackathon |
| SÁB 19 | 18:00 | Lote 2: 40 facturas, ERP actualizado |
| DOM 20 | 11:00 | Cierre de entrega y registro del commit |
| DOM 20 | Por confirmar | Defensa · 10 minutos por equipo |

10 MINUTOS · UN MISMO TRIBUNAL

## Preparad la defensa

La validación funcional ya estará resuelta. Usad la defensa para demostrar el producto y sostener vuestras decisiones.

### Demo y contexto · 2 min

Mostrad la solución funcionando y el problema concreto que resuelve para Alberto. Si optáis al bonus, enseñad también la mejora adicional implementada.

### Arquitectura y ADRs · 2 min

Apoyaos en albertitos_plan.pdf para defender el formato y la arquitectura, el reparto entre agentes, modelos y personas, y las decisiones, alternativas y trade-offs registrados.

### Trazabilidad, escala y coste · 4 min

Seguid una decisión real y mostrad las señales operativas. Explicad capacidad, hardware, fórmula de coste y supuestos. Separad mediciones de estimaciones y contad qué cambiaría con emails, imágenes o Excel.

### Resiliencia y preguntas · 2 min

Explicad o demostrad un timeout, rate limit, respuesta inválida o caída del proveedor. Mostrad qué se conserva, cómo evitáis duplicados y cómo se recupera el trabajo.

### Dudas antes de construir

#### ¿Tenemos que construir una web o usar un stack concreto?

No. Podéis construir una CLI, backend, herramienta para agentes, web u otra solución. Defended por qué ese formato es adecuado; no se puntúa el tamaño.

#### ¿Hay un formato obligatorio para la traza?

No. Solo file_id y result son obligatorios para validar los JSONL. Podéis demostrar auditabilidad mediante logs, una base de datos, una interfaz, campos adicionales o cualquier mecanismo que permita seguir una decisión real.

#### ¿Qué pasa si no superamos la validación?

Podéis defender el proyecto y recibir feedback, pero no optar al premio. Para ser aptos hace falta un registro único por cada archivo de ambos lotes, con un result aceptado por la referencia privada.

#### ¿Tenemos que publicar nuestra solución?

No. El repositorio de entrega es separado y debe contener exactamente outcomes.jsonl, outcomes_lote2.jsonl y albertitos_plan.pdf en la raíz. No subáis la solución, credenciales ni ejecutables. Enseñad vuestra solución durante la defensa.

#### ¿Qué pasa si falta albertitos_plan.pdf?

Es la única documentación requerida: Arquitectura y de 2 a 5 ADRs / trade-offs. Su ausencia o mala calidad no os excluye si los JSONL son correctos, pero puede dejar sin puntos Producto, arquitectura y ADRs, que vale 35 puntos.

#### ¿Cómo conseguimos los 10 puntos de bonus?

Detectad una necesidad adicional de Alberto, implementad una mejora útil y mostradla durante la defensa. El bonus es opcional: no cuentan una propuesta, una maqueta, un cambio cosmético ni algo ya necesario para el flujo principal. No es el lote adicional del sábado. La puntuación máxima total es de 110 puntos.

#### ¿Dónde conseguimos los materiales?

En el canal del track: el viernes a las 19:00 se comparte el repo con los archivos iniciales. El sábado a las 18:00 se publica lote-2-sorpresa-v3.2.zip. Comprobad los hashes publicados en el canal.

#### ¿Cómo arrancamos el ERP local?

Dentro de caja-de-alberto, ejecutad make help y make erp. Dejad esa terminal abierta: el ERP escucha en http://127.0.0.1:8009. Desde otra terminal podéis usar make erp-status y make erp-login. make erp-fast elimina la latencia artificial para tests locales. Consultad MANUAL_ERP_2009.md para los endpoints, las sesiones y los reintentos.

#### ¿Cuántas personas forman un equipo?

De 2 a 5 personas, con un máximo de 15 equipos.

#### ¿Podemos consultar a Maisa antes de la defensa?

Sí. Los mentores estarán en el espacio del track. Podéis pedir una consulta de diseño o un simulacro breve de defensa.

Estamos para ayudaros

## Si tenéis dudas, buscad las camisetas verdes.

Somos el equipo de Maisa. Acercaos al espacio del track para resolver dudas, consultar una decisión de diseño o hacer un simulacro breve de defensa.

No hace falta tenerlo todo resuelto para preguntar.

MAISA · PREMIOS

Primer premio

## Viaje a nuestras oficinas en Valencia

Para vivir la experiencia Maisa.

## Empezad el reto.

Clonad el repositorio de participantes y abrid el README para empezar con la Caja de Alberto.

Pegad este comando en vuestra terminal

$ `git clone https://github.com/ikurotime/500-sombras-de-alberto.git`

[github.com/ikurotime/500-sombras-de-alberto ↗](https://github.com/ikurotime/500-sombras-de-alberto)
