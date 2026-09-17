# Mercado Pago Account Money POC

Este POC ejecuta el flujo real contra Mercado Pago sin guardar credenciales ni fixtures personales.

```powershell
$env:PYTHONPATH = "backend"
$env:MERCADOPAGO_ACCESS_TOKEN = "APP_USR-..."
python -m app.scripts.mercadopago_poc `
  --begin "2026-08-01T00:00:00Z" `
  --end "2026-08-03T23:59:59Z" `
  --out ".tmp/mercadopago-report.csv" `
  --debug-http
```

Flujo implementado:

- valida el token con `GET https://api.mercadolibre.com/users/me`;
- consulta/crea/actualiza la configuracion con `/v1/account/settlement_report/config`;
- solicita un reporte con `POST /v1/account/settlement_report`;
- consulta `GET /v1/account/settlement_report/list` hasta encontrar el reporte creado por su ID; si el POST no devuelve ID, usa solo una coincidencia exacta del rango solicitado;
- descarga `GET /v1/account/settlement_report/{file_name}`;
- para movimientos enriquecibles, consulta `GET /v1/payments/{id}` usando `SOURCE_ID` y `ORDER_ID` como respaldo para reemplazar referencias tecnicas por nombres legibles;
- inspecciona columnas y muestra una vista normalizada de los primeros movimientos.

Campos esperados por la integración actual:

- `SOURCE_ID` o `EXTERNAL_REFERENCE` para idempotencia;
- `TRANSACTION_DATE` para fecha;
- `TRANSACTION_TYPE` para tipo;
- `TRANSACTION_AMOUNT`, `REAL_AMOUNT` o `SETTLEMENT_NET_AMOUNT` para importe;
- `TRANSACTION_CURRENCY` o `SETTLEMENT_CURRENCY` para moneda;
- `PAYMENT_METHOD_TYPE`/`PAYMENT_METHOD` para distinguir `account_money` de tarjetas vinculadas.

Estado de validacion real (2026-09-17): el flujo fue probado correctamente con una cuenta real, incluyendo conexion, creacion/descarga del settlement report, importacion historica, enriquecimiento de nombres y resincronizacion idempotente. Hay una ultima prueba manual planificada antes de mergear la rama. Los tests permanentes siguen usando fixtures sinteticos; no se deben guardar tokens, CSVs ni respuestas reales en git.

Nota de implementacion: antes de crear un reporte manual con `POST /v1/account/settlement_report`, la sincronizacion consulta `GET /v1/account/settlement_report/config` y crea/actualiza esa configuracion si falta o si no contiene las columnas requeridas. Sin esa configuracion previa, Mercado Pago puede responder `404` al crear el reporte.

Nota de nombres: el CSV de settlement puede traer referencias tecnicas como `INSTORE-...`, `ABU-...` o `PAYOUTS`. Para compras, la importacion intenta enriquecer el nombre con la API de Payments usando primero `SOURCE_ID` y luego `ORDER_ID` como respaldo. Si el movimiento ya habia sido importado con un nombre generico/tecnico, una nueva sincronizacion puede actualizar esa descripcion sin duplicar el gasto.

Nota de sincronizacion en la app: `POST .../sync` responde `202 Accepted` despues de reclamar atomicamente la integracion. La creacion, espera, descarga e importacion del reporte siguen en una tarea de fondo sin mantener una sesion de base de datos abierta. `GET .../integrations` expone estado, rango, timestamps y conteos persistidos para que la UI haga polling. Los intentos superpuestos responden `409`; al arrancar, un estado `running` abandonado se recupera como error de interrupcion.

Nota de aprendizaje: las lineas enriquecidas guardan una identidad estable basada primero en `collector.id` y, si falta, en `store_id`. Al editar un gasto de Mercado Pago se puede aprender para futuras importaciones su descripcion, categoria, subcategoria y recurrencia a nivel hogar. No se usan IDs de pago, orden ni referencia externa como identidad de comercio; no se modifican gastos historicos y una resincronizacion respeta descripciones editadas manualmente. Los nuevos gastos de Mercado Pago dejan `notes` vacio.

Nota de eliminacion y reimportacion: al eliminar un gasto de Mercado Pago se elimina tambien su `ImportLine` si ya no esta referenciada. Para datos creados antes de esa regla, una resincronizacion detecta fingerprints comprometidos que quedaron huerfanos y vuelve a importar el movimiento. Una linea todavia asociada a un gasto o ingreso sigue contando como duplicado valido.

## Debug HTTP local

El `docker-compose.yml` local activa por defecto `SPENT_MERCADOPAGO_DEBUG_HTTP_ENABLED=true`. El script demo `scripts/start-demo-compose.ps1` tambien lo activa por defecto en el compose temporal que genera. Con eso el contenedor `api` escribe en logs cada request/response saliente a Mercado Pago, incluyendo bodies truncados a `SPENT_MERCADOPAGO_DEBUG_HTTP_MAX_CHARS`.

El header `Authorization` se imprime como `Bearer ***REDACTED***`. Aun así, los responses pueden contener datos personales de movimientos, por eso `docker-compose.prod.yml` fuerza este flag a `false` y la app rechaza arrancar en producción si se intenta activar.

Para apagarlo localmente:

```powershell
$env:SPENT_MERCADOPAGO_DEBUG_HTTP_ENABLED = "false"
docker compose up --build
```

Si se usa el script demo, se puede apagar con:

```powershell
.\scripts\start-demo-compose.ps1 -NoMercadoPagoHttpDebug
```
