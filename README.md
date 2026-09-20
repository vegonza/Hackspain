# Procesamiento de facturas · HackSpain 2026

Aplicación web para procesar facturas, contrastarlas con proveedores, pedidos y un ERP legado, y decidir si deben pagarse, rechazarse o revisarse. La aplicación conserva el documento original, la extracción, las métricas de cada etapa, el consumo de IA y la justificación de la decisión.

## Arquitectura

- **Frontend:** React, TypeScript, Vite y Recharts.
- **API:** FastAPI.
- **Procesamiento:** workers paralelos coordinados mediante Redis.
- **Persistencia:** PostgreSQL y Storage de Supabase. Los archivos se sirven mediante URL firmadas.
- **ERP:** el submódulo `500-sombras-de-alberto`, expuesto al backend mediante el bridge incluido en `infra/erp`.
- **IA:** OpenRouter para extracción y clasificación, y TypeSafe/Jev para categorizar conceptos.

El sistema acepta PDF y documentos de Office (`doc`, `docx`, `odt`, `rtf`, `ppt`, `pptx`, `odp`, `xls`, `xlsx` y `ods`). Los documentos de Office se convierten a PDF con LibreOffice antes de entrar en el mismo flujo de procesamiento.

## Requisitos

- Git
- Docker con Docker Compose
- Un proyecto de Supabase
- Credenciales de OpenRouter y TypeSafe
- Credenciales del ERP incluidas en el reto

Para trabajar sin Docker también se usan [uv](https://docs.astral.sh/uv/) y [Bun](https://bun.sh/).

## Configuración

Clona el repositorio con su submódulo:

```bash
git clone --recurse-submodules <URL_DEL_REPOSITORIO>
cd Hackspain
```

Si el repositorio ya estaba clonado:

```bash
git submodule update --init --recursive
```

Crea el archivo de entorno y completa las credenciales:

```bash
cp backend/.env.example backend/.env
```

Las variables principales son:

| Variable | Uso |
| --- | --- |
| `ENV` | `development` en local y `production` en despliegue. |
| `APP_PASSWORD` | Contraseña de acceso a la aplicación. |
| `SUPABASE_URL` | URL del proyecto de Supabase. |
| `SUPABASE_PUBLIC_KEY` | Clave pública de Supabase. |
| `SUPABASE_SECRET_KEY` | Clave de servicio usada únicamente por el backend. |
| `SUPABASE_STORAGE_BUCKET` | Bucket privado para los documentos; por defecto, `documents`. |
| `OPENROUTER_API_KEY` | Extracción y clasificación con IA. |
| `TYPESAFE_API_KEY` | Categorización de conceptos con Jev. |
| `ERP_USERNAME` / `ERP_PASSWORD` | Acceso al ERP del reto. |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | Envío opcional de documentación a la gestoría. |
| `VERIFACTU_*` | Integración de prueba para facturas emitidas. |
| `APP_HOST` | Dominio público; solo se usa en producción. |

No subas `backend/.env` al repositorio.

### Supabase

Crea un bucket privado con el nombre indicado en `SUPABASE_STORAGE_BUCKET`. En una base de datos nueva, ejecuta los esquemas canónicos de `database/` en este orden:

1. `erp.sql`
2. `suppliers.sql`
3. `documents.sql`
4. `orders.sql`
5. `usage.sql`
6. `issued_invoices.sql`
7. `gestoria.sql`
8. `get_erp_snapshot.sql`
9. `get_erp_entry.sql`
10. `get_documents.sql`
11. `get_invoices.sql`
12. `get_document_detail.sql`
13. `get_rule_references.sql`
14. `document_decisions.sql`
15. `analytics.sql`

Los archivos `migration_*.sql` reflejan cambios aplicados durante el desarrollo y no forman parte de una instalación nueva.

## Desarrollo local

Con `backend/.env` configurado, levanta toda la aplicación:

```bash
./start.sh
```

El comando arranca el ERP, Redis, la API, el worker y el frontend. También activa la recarga automática del backend, del worker y del frontend.

Abre [http://localhost:5173](http://localhost:5173) e inicia sesión con `APP_PASSWORD`.

Para detener el entorno:

```bash
docker compose -f docker-compose.dev.yml down
```

## Uso

1. Entra en **Facturas** y pulsa **Subir factura**.
2. Selecciona uno o varios documentos compatibles.
3. El worker convierte los archivos de Office, extrae el contenido, categoriza los conceptos y aplica las reglas de negocio.
4. Abre una factura para revisar el PDF, el Markdown combinado, las etapas, costes, tiempos, datos extraídos, referencias del ERP y la decisión.
5. Usa **Proveedores**, **Pedidos** y **ERP** para revisar los datos de contraste.
6. Consulta **Análisis** y **Consumo** para ver gasto, IVA, rendimiento y uso de IA.

Las facturas en estado **A revisar** se pueden resolver manualmente desde su detalle. Los errores de procesamiento se pueden reintentar sin volver a subir el archivo.

## Comprobaciones

Backend:

```bash
cd backend
uv venv
uv pip install -r requirements.txt
set -a && source .env && set +a
uv run python -m unittest discover -s tests
```

Frontend:

```bash
cd frontend
bun install --frozen-lockfile
bun run typecheck
bun test
bun run build
```

## Generar los resultados del reto

Cuando las 540 facturas hayan terminado y tengan una decisión, genera ambos JSONL desde las decisiones guardadas:

```bash
set -a && source backend/.env && set +a
uv run python backend/export_outcomes.py --output-dir ./la-caja-outcomes
```

La CLI identifica cada factura por el SHA-256 del archivo, comprueba que existan exactamente 500 resultados del lote principal y 40 del lote adicional, y crea:

```text
la-caja-outcomes/
├── outcomes.jsonl
└── outcomes_lote2.jsonl
```

Cada línea cumple el contrato del reto:

```json
{"file_id":"factura_5518.pdf","result":"PAGAR"}
```

## Producción

El despliegue incluido asume un proxy Traefik conectado a una red Docker externa llamada `edge`. Configura `ENV=production` y `APP_HOST` en `backend/.env`, crea la red si aún no existe y despliega:

```bash
docker network create edge
./deploy.sh
```

Para reconstruir solo servicios concretos:

```bash
./deploy.sh --no-deps frontend
./deploy.sh --no-deps backend worker
```

La API expone su comprobación pública en `/api/health`. El resto de `/api` requiere la sesión creada con `APP_PASSWORD`.
