# ADR · Capa de integración con el ERP

Registro de decisiones de arquitectura del componente **"conexión con el ERP"**.
Ámbito: solo la capa de acceso a datos del ERP. **No cubre el motor de reglas ni la extracción de PDFs.**

Formato: cada decisión tiene contexto, decisión, alternativas descartadas y consecuencias.
Estado: `Aceptada` · `Propuesta` · `Sustituida por ADR-NNN`

| # | Decisión | Estado |
|---|---|---|
| [001](#adr-001) | Spike aislado del repositorio del reto | Aceptada |
| [002](#adr-002) | No modificar `alberto_erp.py` bajo ningún concepto | Aceptada |
| [003](#adr-003) | Cliente solo con biblioteca estándar | Aceptada |
| [004](#adr-004) | Reintentar según el **código de error**, no según el status HTTP | Aceptada |
| [005](#adr-005) | Autolimitación proactiva a 8 req/s | Aceptada |
| [006](#adr-006) | Un solo worker secuencial | Aceptada |
| [007](#adr-007) | Renovación proactiva de la sesión | Aceptada |
| [008](#adr-008) | Parseo tolerante: marcar, nunca reventar | Aceptada |
| [009](#adr-009) | `Decimal` para el dinero, nunca `float` | Aceptada |
| [010](#adr-010) | Parsear **bytes**, no `str` | Aceptada |
| [011](#adr-011) | **La capa ERP observa; no decide** | Aceptada |
| [012](#adr-012) | Formato de intercambio: JSONL normalizado con `avisos` | Aceptada |
| [013](#adr-013) | ~~Resolver el `127.0.0.1` con `socat`~~ | Sustituida por ADR-015 |
| [014](#adr-014) | Snapshot inmutable por ejecución en vez de consultas bajo demanda | Propuesta |
| [015](#adr-015) | Reenviador TCP en Python puro en lugar de `socat` | Propuesta |
| [016](#adr-016) | Un único motor de reintentos para **todas** las peticiones | Aceptada |
| [017](#adr-017) | Detectar el formato del importe en vez de asumirlo | Aceptada |
| [018](#adr-018) | Blindaje de red: cabecera, sin proxy, sin redirecciones, tope de tamaño | Aceptada |
| [019](#adr-019) | Escritura atómica del snapshot | Aceptada |
| [020](#adr-020) | El código de salida bloquea el resto del pipeline | Aceptada |
| [021](#adr-021) | Código e identificadores en inglés | Aceptada |
| [022](#adr-022) | Parámetros de temporización inyectables, no constantes globales | Aceptada |
| [023](#adr-023) | Obedecer `Retry-After` con suelo y techo propios | Aceptada |

---

<a id="adr-001"></a>
## ADR-001 · Spike aislado del repositorio del reto

**Estado:** Aceptada · 18/09/2026

**Contexto.** Hay más gente del equipo trabajando en la aplicación final. Todavía no sabemos qué forma tendrá la integración. Mezclar código exploratorio con el repo definitivo genera conflictos y ruido.

**Decisión.** El trabajo de integración con el ERP vive en `~/Desktop/Hackspain/erp-spike/`, una carpeta independiente del repo del reto (`~/Desktop/500-sombras-de-alberto`) y del repo de la aplicación final.

**Alternativas descartadas.**
- Trabajar directamente en el repo de la aplicación → conflictos con el resto del equipo antes de tener un contrato claro.
- Trabajar dentro del repo del reto → riesgo de ensuciar código que la organización va a clonar.

**Consecuencias.**
- ✅ Podemos iterar rápido y romper cosas sin molestar a nadie.
- ✅ Cuando el contrato esté claro, se mueve como un módulo limpio.
- ⚠️ Hay que acordar el contrato **pronto** o el resto del equipo se bloquea. Es deuda que vence.

---

<a id="adr-002"></a>
## ADR-002 · No modificar `alberto_erp.py` bajo ningún concepto

**Estado:** Aceptada · 18/09/2026

**Contexto.** El ERP simulado inyecta fallos a propósito: `ORA-00600` cada 10 consultas autenticadas, rate limit de 10 req/s, sesiones que caducan, latencia de 120 ms. Es tentador tocarlos para ir más rápido.

**Decisión.** El fichero es de **solo lectura**. Se puede leer, ejecutar y estudiar; nunca editar. Todo lo que necesitemos se resuelve **en nuestro lado**.

**Alternativas descartadas.**
- Parchear `FALLO_CADA` o `RATE_MAX_POR_SEGUNDO` → invalida cualquier comparación con otros equipos y es indefendible el domingo.
- Leer el blob de datos embebido y saltarse el HTTP → elimina precisamente el trabajo que se evalúa.

**Consecuencias.**
- ✅ Los números que midamos son comparables y defendibles.
- ✅ Si la organización cambia el ERP el sábado, nuestro cliente sigue valiendo.
- ⚠️ Resolver el binding a `127.0.0.1` cuesta trabajo extra. Ver [ADR-013](#adr-013).

---

<a id="adr-003"></a>
## ADR-003 · Cliente solo con biblioteca estándar

**Estado:** Aceptada · 18/09/2026

**Contexto.** El entorno no tiene `requests`, ni `httpx`, ni `lxml`. Un hackathon de 38 horas no es momento para pelearse con entornos virtuales.

**Decisión.** El cliente usa exclusivamente `urllib`, `xml.etree.ElementTree`, `decimal`, `datetime`, `json`, `dataclasses`. Cero dependencias.

**Alternativas descartadas.**
- `requests` + `tenacity` → más cómodo, pero añade instalación y la lógica de reintentos aquí es lo bastante específica como para que `tenacity` no encaje bien.

**Consecuencias.**
- ✅ `python3 erp_client.py` funciona en cualquier máquina del equipo sin preparar nada.
- ✅ La imagen Docker será minúscula.
- ⚠️ `urllib` es más verboso. Ya está encapsulado en `_peticion()`.

---

<a id="adr-004"></a>
## ADR-004 · Reintentar según el código de error, no según el status HTTP

**Estado:** Aceptada · 18/09/2026

**Contexto.** El ERP devuelve cuatro errores que exigen reacciones **opuestas**:

| Código | HTTP | Qué significa | Reacción correcta |
|---|---|---|---|
| `ORA-00600` | 500 | Fallo inyectado, determinista | Reintentar **ya** |
| `ERP-429` | 429 | Has ido demasiado rápido | Esperar 1,1 s |
| `SES-401` | 401 | Token muerto | Volver a hacer login |
| `ERP-400` / `ERP-404` | 400/404 | Has pedido algo que no existe | **No reintentar nunca** |

**Decisión.** El cliente parsea `<error><codigo>` del cuerpo XML y despacha sobre ese código. El status HTTP solo se usa para saber que algo ha ido mal.

**Alternativas descartadas.**
- Reintentar cualquier 5xx con backoff exponencial → lento y no distingue el 429 del 500.
- Hardcodear "falla la petición 10, 20, 30…" → funcionaría hoy y se rompería el sábado. **Conocer el fuente no debe filtrarse al código.**

**Consecuencias.**
- ✅ Un `ERP-404` falla rápido en vez de reintentarse 8 veces.
- ✅ Si el sábado añaden un código nuevo, cae en el `else` y aborta con un mensaje claro en vez de colgarse.
- ⚠️ Hay que leer el cuerpo de las respuestas de error. `urllib` lanza `HTTPError`; se captura y se lee de ahí.

---

<a id="adr-005"></a>
## ADR-005 · Autolimitación proactiva a 8 req/s

**Estado:** Aceptada · 18/09/2026

**Contexto.** El servidor rechaza cuando entran **más de 10 peticiones en una ventana de 1 s**, y —detalle crítico— **apunta también las peticiones rechazadas en su ventana**. Reintentar inmediatamente tras un 429 te mantiene bloqueado.

**Decisión.** El cliente espacia sus peticiones con un intervalo mínimo de `1/8 = 125 ms`. Trata el 429 como una anomalía que no debería ocurrir; si ocurre, duerme 1,1 s (ventana completa).

**Alternativas descartadas.**
- No limitar y reaccionar al 429 → entras en un ciclo de rechazo que se autoalimenta.
- Ventana deslizante idéntica a la del servidor → innecesariamente compleja; con un cliente secuencial, espaciar es equivalente.

**Consecuencias.**
- ✅ **0 errores 429 en todas las pruebas.**
- ✅ Sigue funcionando con `--rapido`, donde desaparece la latencia de 120 ms que protegía implícitamente.
- ⚠️ Techo de 8 req/s. El volcado completo tarda 3,7 s. Irrelevante.

---

<a id="adr-006"></a>
## ADR-006 · Un solo worker secuencial

**Estado:** Aceptada · 18/09/2026

**Contexto.** El contador de `ORA-00600` es **global al proceso del servidor**: `consultas_autenticadas % 10 == 0`. Con un solo cliente en serie, dos fallos nunca pueden ser consecutivos, así que **el reintento inmediato está garantizado matemáticamente**. Con N workers en paralelo, dos peticiones pueden coger turnos consecutivos y fallar ambas.

**Decisión.** El cliente es secuencial. Sin hilos, sin `asyncio`.

**Alternativas descartadas.**
- Descargar las 26 páginas en paralelo → ahorraría ~3 s y rompería la garantía de un reintento. No compensa.

**Consecuencias.**
- ✅ `MAX_INTENTOS_POR_PETICION = 8` es un cinturón de seguridad que nunca se usa.
- ✅ Razonamiento simple y demostrable en la defensa.
- ⚠️ Si el volumen creciera mucho habría que revisarlo. Con 516 asientos no es un problema.
- ⚠️ **Un compañero navegando la web del ERP en `/erp/consulta` también mueve el contador.** No es un fallo nuestro, pero contamina las mediciones. Avisar al equipo.

---

<a id="adr-007"></a>
## ADR-007 · Renovación proactiva de la sesión

**Estado:** Aceptada · 18/09/2026

**Contexto.** El token caduca a los **900 s** o a los **300 usos**, lo que llegue antes. Un `SES-401` no consume uso, pero sí cuesta un viaje de ida y vuelta.

**Decisión.** El cliente lleva su propia contabilidad y renueva **antes** de agotarse: a los 250 usos o a los 780 s. El `SES-401` se sigue manejando como red de seguridad.

**Alternativas descartadas.**
- Esperar al `SES-401` y reaccionar → funciona, pero desperdicia peticiones y complica las métricas.

**Consecuencias.**
- ✅ **0 errores `SES-401` en todas las pruebas.** Un solo login para el volcado entero.
- ✅ Los colchones (50 usos, 120 s) absorben desajustes de contabilidad.
- ⚠️ El cliente debe contar bien los usos. Ojo: **un `ORA-00600` sí consume uso** (el fallo se evalúa después de validar la sesión); un `SES-401` no.

---

<a id="adr-008"></a>
## ADR-008 · Parseo tolerante: marcar, nunca reventar

**Estado:** Aceptada · 18/09/2026

**Contexto.** El serializador del ERP devuelve el valor **crudo sin tocar** cuando no consigue formatear una fecha o un importe. Es decir: los datos corruptos llegan tal cual al cliente. En el lote 1 no hay ninguno, pero el sábado llega un lote nuevo.

**Decisión.** Cada asiento conserva el valor crudo (`fecha_cruda`, `importe_crudo`) **y** el valor parseado (que puede ser `None`). Los problemas se acumulan en una lista `avisos`. Nada lanza excepción.

Avisos implementados: `fecha_no_parseable`, `importe_no_parseable`, `estado_desconocido`, `campo_vacio:<campo>`, `posible_perdida_de_caracteres`.

**Alternativas descartadas.**
- Lanzar excepción ante un dato malo → un solo asiento corrupto tumba el volcado de los 516.
- Descartar silenciosamente los asientos malos → pierdes datos sin enterarte. Inaceptable cuando hablamos de dinero.

**Consecuencias.**
- ✅ Detectó los 20 asientos con NIF vacío sin que nadie los buscara.
- ✅ El motor de reglas recibe información honesta y decide con ella.
- ⚠️ Consumir `avisos` es responsabilidad del motor de reglas. Hay que documentarlo en el contrato.

---

<a id="adr-009"></a>
## ADR-009 · `Decimal` para el dinero, nunca `float`

**Estado:** Aceptada · 18/09/2026

**Contexto.** La Regla 2 compara importes con tolerancia de **±0,01 €**. En `float`, `0.1 + 0.2 != 0.3`. Un error de redondeo puede cambiar un PAGAR por un ESCALAR.

**Decisión.** Los importes se parsean a `decimal.Decimal` desde el string original (`"12.874,40"` → quitar puntos, coma a punto). Se serializan a JSON como **string**, no como número, para no perder precisión al volver a leerlos.

**Alternativas descartadas.**
- `float` → riesgo de error de redondeo en comparaciones de dinero.
- Enteros en céntimos → correcto pero más incómodo de leer en los volcados.

**Consecuencias.**
- ✅ Las comparaciones de ±0,01 € son exactas.
- ⚠️ Quien consuma el JSONL debe hacer `Decimal(d["importe"])`, no `float(...)`. Documentado en el contrato.

---

<a id="adr-010"></a>
## ADR-010 · Parsear bytes, no `str`

**Estado:** Aceptada · 18/09/2026

**Contexto.** El ERP responde XML con `<?xml version="1.0" encoding="ISO-8859-1"?>`. Si decodificas a `str` y se lo pasas a `ET.fromstring()`, Python lanza `ValueError: Unicode strings with encoding declaration are not supported`.

**Decisión.** `_peticion()` devuelve siempre `bytes` crudos. El parser recibe bytes y deja que `ElementTree` respete la declaración de encoding.

**Consecuencias.**
- ✅ Los acentos llegan bien.
- ⚠️ El servidor codifica con `errors="replace"`: lo que no cabe en Latin-1 se convierte en `?` **en origen** y es irrecuperable. Por eso existe el aviso `posible_perdida_de_caracteres`.

---

<a id="adr-011"></a>
## ADR-011 · La capa ERP observa; no decide

**Estado:** Aceptada · 18/09/2026

**Contexto.** Es la decisión que define el reparto de trabajo del equipo. Existe la tentación de que la capa de integración "ya que está" devuelva si una factura se paga o no.

**Decisión.** La capa de integración con el ERP **no emite decisiones de negocio**. No conoce las palabras `PAGAR`, `NO_PAGAR` ni `ESCALAR`. Devuelve exclusivamente:

1. **Hechos** — lo que el ERP dice de cada asiento, normalizado.
2. **Observaciones** — anomalías de **calidad del dato** (`avisos`): campos vacíos, formatos ilegibles, duplicados, ausencias.
3. **Metadatos de fiabilidad** — si el volcado está completo, cuántos reintentos hicieron falta, si el lote 2 está cargado.

Quien cruza esos hechos con el PDF y el Excel y aplica las 6 reglas es **el motor de reglas**, que es otro componente.

**Alternativas descartadas.**
- Que el cliente del ERP aplique la Regla 5 (estado `PENDIENTE`) por su cuenta → mezcla capas, y si el sábado añaden una regla nueva hay que tocar la integración.

**Consecuencias.**
- ✅ Se puede cambiar la norma sin tocar una línea de esta capa. Seguro barato contra la "norma v4".
- ✅ Los dos componentes se desarrollan y se testean por separado.
- ⚠️ Obliga a acordar un contrato explícito con el equipo de reglas. Ver [ADR-012](#adr-012).

---

<a id="adr-012"></a>
## ADR-012 · Formato de intercambio: JSONL normalizado con `avisos`

**Estado:** Aceptada · 18/09/2026

**Contexto.** El motor de reglas necesita consultar el ERP por pedido, muchas veces, sin que le importe el XML, el Latin-1 ni los reintentos.

**Decisión.** La frontera entre las dos capas es un registro JSON por asiento, una línea por registro:

```json
{
  "id": "AS-00084",
  "proveedor": "P002",
  "nif": "A41220987",
  "pedido": "PO-2026-0084",
  "estado": "PENDIENTE",
  "fecha_cruda": "21/03/2026",
  "importe_crudo": "6.199,54",
  "fecha": "2026-03-21",
  "importe": "6199.54",
  "avisos": []
}
```

Reglas del formato:
- `fecha` en **ISO 8601** o `null`.
- `importe` como **string decimal** con punto, o `null`.
- Los campos `*_crudo` **siempre** se conservan, para poder auditar y para que el motor de reglas pueda decidir sobre el original si lo necesita.
- `avisos` es una lista, posiblemente vacía. Nunca `null`.

**Consecuencias.**
- ✅ Legible, diffeable, greppeable. Se puede inspeccionar con `head` durante la defensa.
- ✅ Sirve igual como fichero o como cuerpo de una respuesta HTTP.
- ⚠️ Hay que versionar el contrato si cambia. Añadir campos es seguro; quitarlos no.

---

<a id="adr-013"></a>
## ADR-013 · ~~Resolver el `127.0.0.1` con `socat`~~

**Estado:** ❌ **Sustituida por [ADR-015](#adr-015)** · 19/09/2026

> **Por qué decayó.** `socat` **no está instalado** y esta es una máquina corporativa gestionada: `/Applications` sólo contiene 15 aplicaciones, entre ellas Santa (control de binarios de Google), Falcon y Warden. No hay Homebrew. Dar por hecho que se puede instalar `socat` el sábado por la mañana es exactamente el tipo de suposición que revienta una demo. La idea sigue siendo correcta; lo que cambia es la herramienta.

**Contexto.** El ERP hace `ThreadingHTTPServer(("127.0.0.1", puerto), ...)`: escucha **solo en loopback**. Un contenedor Docker no puede alcanzarlo, y `network_mode: host` no funciona en macOS. [ADR-002](#adr-002) prohíbe editar el fichero.

**Decisión propuesta.** Poner un reenviador delante:

```bash
socat TCP-LISTEN:8010,fork,reuseaddr TCP:127.0.0.1:8009
```

Los contenedores apuntan a `host.docker.internal:8010`. El ERP no se entera de nada.

**Alternativas descartadas.**
- Editar el binding a `0.0.0.0` → viola [ADR-002](#adr-002).
- Ejecutar toda la aplicación fuera de Docker → pierdes la reproducibilidad que se puntúa.
- `ssh -L` → funciona, pero es más frágil y menos explicable.

**Consecuencias.**
- ✅ Cero modificaciones al código del reto.
- ✅ Se puede meter el propio `socat` en un contenedor junto al ERP y documentarlo en el `docker-compose.yml`.
- ⚠️ Una pieza móvil más que puede no estar arrancada. El cliente debe dar un mensaje de error claro cuando no responda.
- ⚠️ Comprobar que `socat` está instalado en las máquinas del equipo.

---

<a id="adr-014"></a>
## ADR-014 · Snapshot inmutable por ejecución

**Estado:** Propuesta · 18/09/2026

**Contexto.** El motor de reglas hará ~500 consultas por pedido. Ir al ERP en cada una serían 500 peticiones, ~50 fallos que absorber y un minuto largo. Además, si alguien reinicia el ERP a mitad, el pipeline vería datos inconsistentes.

**Decisión propuesta.** La capa de integración descarga **todos** los asientos **una vez** al arrancar (3,7 s, 30 peticiones), valida que el volcado está completo, y sirve un índice en memoria inmutable. Las consultas posteriores no tocan la red.

**Alternativas descartadas.**
- Consulta bajo demanda con caché → complejidad de invalidación sin ninguna ventaja real aquí.
- Consulta bajo demanda sin caché → lento y frágil.

**Consecuencias.**
- ✅ El pipeline entero trabaja sobre una foto coherente.
- ✅ Reproducible: mismo snapshot, mismo resultado. Ya demostrado con tres volcados de md5 idéntico.
- ✅ El snapshot se guarda en disco como evidencia de la ejecución.
- ⚠️ Si el ERP cambia durante la ejecución (sábado: carga del lote 2) hay que **relanzar**, no refrescar. `/erp/estado` expone `actualizacion_cargada`, que sirve para detectarlo.
- ⚠️ El pipeline debe **abortar** si el snapshot llega incompleto. Nunca decidir sobre datos parciales.

---

<a id="adr-015"></a>
## ADR-015 · Reenviador TCP en Python puro en lugar de `socat`

**Estado:** Propuesta · 19/09/2026 · *sustituye a [ADR-013](#adr-013)*

**Contexto.** Sigue en pie el problema de [ADR-013](#adr-013): el ERP escucha en `127.0.0.1` y nadie más lo alcanza. Lo que ha cambiado es que `socat` no está disponible en esta máquina y no se puede dar por hecho que lo esté en las de los compañeros.

**Decisión propuesta.** Si finalmente hace falta exponer el ERP, hacerlo con un reenviador TCP de ~150 líneas en biblioteca estándar (`erp_bridge.py`), coherente con [ADR-003](#adr-003). Escucha en la interfaz que se le diga y reenvía a `127.0.0.1:8009`.

**Alternativas descartadas.**
- `socat` → no instalado, y Santa puede bloquear la instalación.
- `ssh -L` hacia uno mismo → funciona, pero depende de que "Sesión remota" esté activada, y en un Mac gestionado eso es política de empresa, no una casilla.
- Editar el binding a `0.0.0.0` → viola [ADR-002](#adr-002).

**Consecuencias.**
- ✅ Cero dependencias y cero instalaciones. Funciona en cualquier máquina con Python 3.
- ✅ Se puede leer entero en dos minutos, que es lo que se le pide a una pieza de infraestructura improvisada.
- ⚠️ **Nada lo usa todavía.** El fichero está en el spike como reserva. La decisión real de cómo se conecta el equipo está pendiente y se toma con el equipo delante, no aquí.
- ⚠️ Exponer el ERP fuera de loopback es una decisión de seguridad, por pequeña que sea. Si se activa, que sea con el puerto atado a la IP concreta y sólo mientras dure la sesión de trabajo.

---

<a id="adr-016"></a>
## ADR-016 · Un único motor de reintentos para **todas** las peticiones

**Estado:** Aceptada · 19/09/2026

**Contexto.** La v1 tenía tres caminos distintos hacia la red: el login, el health check y las consultas de datos. Sólo el último reintentaba. La auditoría lo recogió como hallazgos C-2 y C-3.

El problema es que el limitador de caudal del ERP se evalúa **antes** del enrutado ([`alberto_erp.py:327`](file:///Users/hernandezpalma/.gemini/jetski/scratch/500-sombras-de-alberto/alberto_erp.py)): `POST /erp/login` y `GET /erp/estado` pueden recibir un ERP-429 exactamente igual que cualquier otra ruta. Un 429 en el login abortaba el volcado entero.

**Decisión.** Todo pasa por `_get()` / `ensure_session()`, y ambos comparten la misma tabla de decisiones: ORA-00600 → reintento inmediato; ERP-429 → enfriar y reintentar; SES-401 → re-autenticar; cualquier otro → error permanente.

Además, **el parseo ocurre dentro del bucle de reintentos**. En la v1 estaba fuera, así que un cuerpo truncado mataba un volcado de 26 páginas. Un XML ilegible es un síntoma de transporte, no un error de datos.

**Alternativas descartadas.**
- Reintentar sólo lo que había fallado alguna vez en pruebas → programar para el pasado.
- Una librería de reintentos (`tenacity`) → viola [ADR-003](#adr-003).

**Consecuencias.**
- ✅ Una sola tabla de decisiones que auditar, en vez de tres.
- ✅ Dos pruebas de regresión dedicadas: `test_rate_limited_login_is_retried` y `test_rate_limited_status_is_retried`.
- ⚠️ Hay que vigilar que el reintento no sea infinito: lo acotan `max_attempts` y el presupuesto de tiempo.

---

<a id="adr-017"></a>
## ADR-017 · Detectar el formato del importe en vez de asumirlo

**Estado:** Aceptada · 19/09/2026

**Contexto.** El bug más caro encontrado. `_importe_legacy` del ERP ([`alberto_erp.py:176-186`](file:///Users/hernandezpalma/.gemini/jetski/scratch/500-sombras-de-alberto/alberto_erp.py)) **devuelve el valor original sin tocar cuando no consigue formatearlo**. Es decir: casi todo llega como `"12.874,40"` (español), pero un importe corrupto en origen puede llegar como `"1234.56"` (inglés). Quitar los puntos sin mirar convierte 1.234,56 € en 123.456 €: **multiplica el dinero por cien**.

**Decisión.** No asumir el idioma del número. Decidir mirando la cadena: cuál es el último separador, si hay agrupaciones bien formadas, si hay ambos separadores. Y validar que las agrupaciones son grupos de exactamente tres dígitos.

**Alternativas descartadas.**
- `locale.atof` → estado global del proceso, y no arregla el caso mixto.
- Asumir español siempre → el bug de ×100.
- Asumir inglés siempre → el mismo bug al revés.

**Consecuencias.**
- ✅ `"12.874,40"`, `"1234.56"`, `"1,234.56"`, `"12.874"` y `"1234,5"` se interpretan todos correctamente.
- ✅ Las pruebas encontraron dos casos que la auditoría estática **no** vio: `"12,34,56"` se leía como `123456`, y `"1..2"` como `12`. Los dos venían de no validar los grupos de tres.
- ⚠️ Lo ambiguo de verdad (`"1.234"`: ¿mil doscientos treinta y cuatro, o uno coma doscientos treinta y cuatro?) se resuelve por la regla de agrupación y se **marca con un aviso**. No se inventa nada en silencio.

---

<a id="adr-018"></a>
## ADR-018 · Blindaje de red: cabecera, sin proxy, sin redirecciones, tope de tamaño

**Estado:** Aceptada · 19/09/2026

**Contexto.** Cuatro hallazgos de la auditoría, todos de la misma familia: el cliente confiaba demasiado en su entorno.

**Decisión.** Cuatro medidas, todas en `_send` y `_build_opener`:

| Medida | Qué evita |
|---|---|
| Token en cabecera `X-ERP-Token`, nunca en `?token=` | El ERP escribe la línea de petición en su log. El token no debe acabar ahí. |
| `ProxyHandler({})` explícito | `urllib` lee `http_proxy` / `ALL_PROXY` del entorno **por su cuenta**. En un Mac corporativo con proxy, las credenciales del login podrían salir hacia un tercero. Esto es tráfico a loopback: no debe salir de la máquina jamás. |
| Redirecciones rechazadas | Un 302 haría que `urllib` reenviara el token a otro host. |
| Tope de 8 MiB por respuesta | La página legítima más grande son 20 asientos, muy por debajo de 8 KiB. Acota la memoria y mitiga expansión XML. |

**Consecuencias.**
- ✅ El token no aparece en ningún log, ni en el del ERP ni en el nuestro (probado en `test_credentials_are_not_logged`).
- ✅ Funciona igual con o sin proxy configurado. *Comprobado en esta máquina: no hay ninguno (`scutil --proxy`), así que hoy el riesgo era teórico — pero el código ya no depende de eso.*
- ⚠️ Si algún día el ERP se sirviera detrás de un proxy legítimo, habría que revisar esta decisión conscientemente.

---

<a id="adr-019"></a>
## ADR-019 · Escritura atómica del snapshot

**Estado:** Aceptada · 19/09/2026

**Contexto.** Un JSONL escrito a medias **sigue siendo sintácticamente válido**. Si el proceso muere por la mitad, el siguiente consumidor procesa un subconjunto sin enterarse de nada. En un reto donde se puntúa la trazabilidad, eso es peor que fallar.

**Decisión.** Escribir en un fichero temporal en el **mismo directorio** y hacer `os.replace()`. En POSIX el renombrado es atómico: los lectores ven el fichero viejo completo o el nuevo completo, nunca un estado intermedio.

**Alternativas descartadas.**
- Escribir directamente → el fallo silencioso descrito arriba.
- Temporal en `/tmp` y mover → `/tmp` puede estar en otro sistema de ficheros, y entonces el renombrado deja de ser atómico.

**Consecuencias.**
- ✅ Nadie lee nunca un volcado parcial.
- ⚠️ Hace falta permiso de escritura en el directorio de destino, no sólo sobre el fichero.

---

<a id="adr-020"></a>
## ADR-020 · El código de salida bloquea el resto del pipeline

**Estado:** Aceptada · 19/09/2026

**Contexto.** [ADR-014](#adr-014) dice que el pipeline debe abortar con datos parciales. Eso hay que poder comprobarlo desde fuera, sin parsear la salida.

**Decisión.** Códigos de salida explícitos:

| Código | Significado |
|---|---|
| `0` | Volcado completo y coherente |
| `1` | Los diagnósticos han fallado (volcado incompleto, ids duplicados, deriva a mitad) |
| `2` | ERP inalcanzable |
| `3` | Error permanente del ERP (credenciales, ruta desconocida) |
| `4` | Uso incorrecto de la línea de comandos |
| `130` | Interrumpido por el usuario |

**Consecuencias.**
- ✅ `make` o un script del pipeline paran solos. Nadie tiene que acordarse de comprobar nada.
- ✅ El `1` distingue "he hablado con el ERP pero los datos no cuadran" de "no he podido hablar con el ERP", que son problemas muy distintos a las 9 de la mañana.
- ⚠️ El equipo tiene que saber que un `1` **no** significa "error genérico". Va documentado en la cabecera del módulo.

---

<a id="adr-021"></a>
## ADR-021 · Código e identificadores en inglés

**Estado:** Aceptada · 19/09/2026

**Contexto.** La v1 mezclaba: `asiento`, `importe`, `fecha` junto a `snapshot`, `client`, `retry`. El ERP habla español; nuestro código no tiene por qué.

**Decisión.** Todo lo nuestro en inglés: identificadores, comentarios, docstrings, nombres de pruebas, claves del JSONL de salida. En español se queda **sólo** lo que es literalmente del ERP: los códigos de error (`ORA-00600`, `SES-401`, `ERP-429`), los nombres de las etiquetas XML que parseamos y los valores de estado (`PENDIENTE`, `PAGADA`).

La conversación, el ADR y la documentación siguen en español.

**Consecuencias.**
- ✅ `entry`, `supplier_id`, `order_id`, `amount`, `status` en vez de `asiento`, `proveedor`, `pedido`, `importe`, `estado`.
- ✅ La frontera entre "lo que dice el ERP" y "lo que decimos nosotros" queda visible a simple vista.
- ⚠️ Cambia el esquema del JSONL. Verificado que el contenido es idéntico al de la v1: mismos 516 ids, **cero** diferencias de valor.
- ⚠️ Hay que avisar al compañero de backend antes de que escriba contra las claves antiguas.

---

<a id="adr-022"></a>
## ADR-022 · Parámetros de temporización inyectables, no constantes globales

**Estado:** Aceptada · 19/09/2026

**Contexto.** Los límites del ERP son de minutos: la sesión caduca a los **900 s o 300 usos**. Con constantes globales y `time.monotonic()` cableado, probar la renovación de sesión exigía esperar trece minutos o hacer 250 peticiones. Resultado: no se probaba. La lógica estaba cubierta "indirectamente", que es una forma elegante de decir que no estaba cubierta.

**Decisión.** Todo lo que mide tiempo o cuenta usos es argumento del constructor, con las constantes como valor por defecto: `requests_per_second`, `rate_limit_cooldown_seconds`, `backoff_*`, `time_budget_seconds`, `session_max_uses`, `session_max_age_seconds`, y además el propio **reloj** (`clock`) y la **función de espera** (`sleeper`).

Las pruebas inyectan un `FakeClock` que sólo avanza cuando se le dice, y cuyo `sleep()` adelanta el reloj en vez de bloquear.

**Alternativas descartadas.**
- `unittest.mock.patch("time.monotonic")` → parchea el módulo entero, afecta a `http.server` del stub, y acopla las pruebas a la implementación.
- Dejarlo sin probar → es justo el mecanismo del que depende que el volcado del sábado no se corte a mitad.

**Consecuencias.**
- ✅ Las dos formas de caducidad ya tienen prueba **directa**: `test_session_is_renewed_before_the_use_limit_is_reached` y `test_session_is_renewed_once_it_gets_old`.
- ✅ Cada una tiene su prueba de guarda (`test_a_young_session_is_reused`, `test_one_login_is_enough_when_the_budget_is_generous`) para que no pasen de forma vacua. Esto no es paranoia: una prueba de determinismo anterior **ya resultó ser vacua** porque el conjunto de datos era demasiado pequeño para que saltara ningún fallo.
- ✅ `TestFakeClockIsHonest` comprueba que el reloj falso está realmente conectado, y que una espera de 25 s no cuesta 25 s de reloj de pared.
- ✅ Efecto colateral: la suite entera puede colapsar sus tiempos y correr en segundos.
- ⚠️ Un argumento más en el constructor. Documentado, y todos tienen valor por defecto sensato.

---

<a id="adr-023"></a>
## ADR-023 · Obedecer `Retry-After` con suelo y techo propios

**Estado:** Aceptada · 19/09/2026

**Contexto.** El ERP responde a los ERP-429 con una cabecera `Retry-After` ([`alberto_erp.py:316`](file:///Users/hernandezpalma/.gemini/jetski/scratch/500-sombras-de-alberto/alberto_erp.py)). Verificado contra el servidor real: siempre manda `Retry-After: 1`.

Hasta la v2.1 la ignorábamos y esperábamos nuestro 1,1 s fijo. Hoy da igual, porque 1,1 > 1. Pero el sábado se carga una versión distinta del ERP, y si sube esa penalización, estaríamos volviendo a la red antes de tiempo y comiéndonos otro 429.

**Decisión.** Interpretar la cabecera y aplicar **suelo y techo**:

```
espera = min( max(Retry-After, 1.1 s), 30 s )
```

- **Suelo (1,1 s).** El servidor dice 1 s, pero su ventana es un `>` estricto sobre un segundo deslizante, y las peticiones **rechazadas también entran en la ventana** ([`alberto_erp.py:251`](file:///Users/hernandezpalma/.gemini/jetski/scratch/500-sombras-de-alberto/alberto_erp.py)). Obedecer el 1 al pie de la letra es pedir otro 429. Nunca esperamos menos que nuestro propio margen.
- **Techo (30 s).** Un servidor mal configurado u hostil no puede aparcarnos indefinidamente. Con presupuesto de 300 s, una espera de una hora sería un cuelgue.
- **Cabecera ausente, vacía o basura** → `None` → se usa nuestro valor. Nunca se interpreta como "no esperes".

Se soportan las dos formas del RFC 9110 (segundos y fecha HTTP) porque cuesta cuatro líneas.

**Alternativas descartadas.**
- Ignorarla, como hasta ahora → funciona hoy por casualidad.
- Obedecerla tal cual → nos expone a la ventana deslizante y a un techo infinito.

**Consecuencias.**
- ✅ Si el sábado suben la penalización, la respetamos sin tocar código.
- ✅ Probado contra el ERP real: forzando 429 con `--rps 50` contra el modo `--rapido`, el cliente registra `ERP-429 ... cooling down 1.10s` tres veces, se recupera y produce un volcado **byte a byte idéntico** (md5 `6f0e4a90…`) al de una ejecución sin ningún 429.
- ✅ 11 pruebas nuevas, incluida una que comprueba que un `Retry-After: 86400` se recorta a 30 s.
- ⚠️ El techo de 30 s es un juicio, no una verdad. Si algún día el ERP pidiera legítimamente más, habría que revisarlo.
