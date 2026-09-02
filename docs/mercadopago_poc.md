# Mercado Pago Account Money POC

Este POC ejecuta el flujo real contra Mercado Pago sin guardar credenciales ni fixtures personales.

```powershell
$env:PYTHONPATH = "backend"
python -m app.scripts.mercadopago_poc `
  --access-token "APP_USR-..." `
  --begin "2026-08-01T00:00:00Z" `
  --end "2026-08-03T23:59:59Z" `
  --out ".tmp/mercadopago-report.csv"
```

Flujo implementado:

- valida el token con `GET https://api.mercadolibre.com/users/me`;
- solicita un reporte con `POST /v1/account/settlement_report`;
- consulta `GET /v1/account/settlement_report/list` hasta encontrar un archivo;
- descarga `GET /v1/account/settlement_report/{file_name}`;
- inspecciona columnas y muestra una vista normalizada de los primeros movimientos.

Campos esperados por la integración actual:

- `SOURCE_ID` o `EXTERNAL_REFERENCE` para idempotencia;
- `TRANSACTION_DATE` para fecha;
- `TRANSACTION_TYPE` para tipo;
- `TRANSACTION_AMOUNT`, `REAL_AMOUNT` o `SETTLEMENT_NET_AMOUNT` para importe;
- `TRANSACTION_CURRENCY` o `SETTLEMENT_CURRENCY` para moneda;
- `PAYMENT_METHOD_TYPE`/`PAYMENT_METHOD` para distinguir `account_money` de tarjetas vinculadas.

Estado de validación real: pendiente de ejecutar contra una cuenta real con movimientos representativos. Hasta tener ese CSV, las reglas quedan conservadoras y testeadas con fixtures sintéticos, no con datos de producción.
