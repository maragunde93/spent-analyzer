# Plan de implementación: Fondo común del hogar

## Objetivo

Agregar una sección mensual que permita organizar un fondo común sin modificar ni duplicar los consumos existentes. La pantalla debe separar claramente:

- gastos compartidos;
- aporte económico de cada persona;
- reintegros entre integrantes;
- dinero acumulado en el fondo;
- saldo acordado y saldo verificado.

La configuración inicial del hogar será un fondo mensual de ARS 4.000.000, con Mauro aportando el 76% y Mica el 24%. El diseño debe admitir otros miembros y porcentajes en el futuro.

## Decisiones funcionales

### Configuración mensual

- El monto y los porcentajes se configuran por mes.
- Si un mes no tiene una configuración propia, hereda la última configuración anterior.
- Una modificación afecta el mes seleccionado y los meses posteriores hasta encontrar otra configuración explícita; nunca cambia meses anteriores.
- Los porcentajes activos deben sumar exactamente 100%.
- El cálculo se realiza en ARS; los consumos en otras monedas usan `amount_ars`.
- Al activar la funcionalidad se solicita una fecha de inicio y un saldo inicial real. No se reconstruye automáticamente todo el historial.

### Gastos incluidos y período

- Solo entran al fondo los consumos existentes con `is_shared = true`.
- Los consumos de tarjeta se asignan al `statement_period` del resumen, no al mes de la fecha de compra.
- Si un resumen no tiene `statement_period`, se usa temporalmente el mes de la fecha y se muestra una advertencia.
- Los consumos manuales, bancarios y de Mercado Pago usan el mes calendario de su fecha.
- Las filas derivadas de consumos, tarjetas o Mercado Pago son de solo lectura en esta pantalla. Cualquier corrección del dato original se hace desde Consumos o Importaciones.

### Cálculo mensual

Para cada mes:

1. `gasto compartido` es la suma de los consumos incluidos.
2. `base a financiar = max(fondo configurado, gasto compartido)`.
3. `cuota de la persona = base a financiar × porcentaje`.
4. Los gastos compartidos pagados directamente por una persona cuentan como dinero adelantado por ella.
5. Los depósitos al fondo cuentan como aporte de quien originó el dinero.
6. Los reintegros enviados aumentan el aporte económico del emisor y reducen el importe adelantado por quien los recibe, sin aumentar el saldo del fondo.

Si el gasto supera el fondo configurado, el exceso se distribuye con los mismos porcentajes y se muestra una alerta visual roja.

El motor de conciliación debe emparejar primero a quienes deben aportar con quienes adelantaron dinero de más. El remanente necesario se dirige al fondo común.

Ejemplo con fondo de ARS 4.000.000:

- Mauro pagó ARS 3.500.000 de gastos compartidos.
- Mauro debe soportar finalmente ARS 3.040.000.
- Mica debe soportar ARS 960.000.
- La propuesta automática es Mica → Mauro por ARS 460.000 y Mica → Fondo por ARS 500.000.
- El sobrante acordado del mes es ARS 500.000.

Si Mauro pagó los ARS 4.000.000 completos, la propuesta es Mica → Mauro por ARS 960.000 y el sobrante del mes es cero. Ese reintegro no convierte el fondo en ARS 4.960.000.

## Experiencia de cierre mensual

La aplicación calcula todo el cierre. La persona que debe aportar no ingresa manualmente cómo dividir su obligación.

Ejemplo para Mica:

```text
Para cerrar junio te corresponde aportar ARS 960.000

Transferir a Mauro                    ARS 460.000
Dejar en el fondo común               ARS 500.000

Después del cierre:
- Mauro habrá aportado el 76%
- Mica habrá aportado el 24%
- El fondo acumulado aumentará ARS 500.000

[ Aceptar y cerrar junio ]
```

El botón acepta el cálculo y cierra el mes. No ejecuta transferencias ni afirma que fueron verificadas.

- El cierre guarda una fotografía del fondo, gastos, porcentajes, posiciones e instrucciones.
- El saldo acordado se arrastra como base principal del mes siguiente.
- El saldo verificado se alimenta con el saldo inicial, Mercado Pago y movimientos reales registrados manualmente.
- La diferencia entre ambos se muestra como pendiente de conciliación, pero no bloquea el mes siguiente.
- Si después del cierre cambia un consumo, una asignación MP o la configuración utilizada, el mes queda marcado como `Cierre desactualizado`. No debe recalcularse silenciosamente.
- El usuario puede reabrir, recalcular y volver a aceptar el cierre, conservando auditoría.
- Con más de dos integrantes, cada persona con una obligación de salida aprueba su parte. El mes queda cerrado cuando todas aceptaron.

Estados previstos: `abierto`, `pendiente_aprobacion`, `cerrado`, `desactualizado`.

## Propuesta de pantalla

```text
FONDO COMÚN                           [ Junio 2026 ]

Fondo del mes       Gastos            Sobrante / exceso
ARS 4.000.000       ARS 3.500.000     ARS 500.000

Saldo acordado      Saldo verificado  Diferencia
ARS 500.000         ARS 500.000       ARS 0

Mauro — 76%                         Mica — 24%
Debe cubrir: ARS 3.040.000          Debe cubrir: ARS 960.000
Adelantó:    ARS 3.500.000          Aportó:      ARS 0
A recibir:   ARS 460.000             Pendiente:   ARS 960.000

Plan para cerrar el mes:
Mica → Mauro: ARS 460.000
Mica → Fondo: ARS 500.000

[ Aceptar y cerrar junio ]
```

La sección incluirá:

- selector de mes y estado del cierre;
- configuración compacta de monto y porcentajes;
- tarjetas de fondo, gastos, sobrante/exceso, saldo acordado, saldo verificado y diferencia;
- posición individual de cada integrante;
- propuesta automática de cierre;
- gráfico de gastos compartidos frente al fondo mensual;
- gráfico divergente de sobrante o exceso por mes;
- evolución de saldos acordado y verificado;
- tabla de movimientos resumidos.

## Tabla de movimientos

La tabla no debe mostrar todos los consumos item por item:

- agrupar tarjetas por mes, pagador y red, por ejemplo `Mauro · Mastercard`;
- agrupar otros gastos por pagador y origen;
- mostrar gastos de una cuenta MP común de forma resumida;
- mantener ingresos de Mercado Pago granulares;
- mantener movimientos manuales granulares;
- mostrar cierres mensuales y su estado.

Solo los movimientos manuales pueden editarse o borrarse desde esta sección. Los movimientos importados permiten únicamente acciones de clasificación necesarias para el fondo, como asignar aportante o excluir un ingreso.

## Movimientos manuales

Permitir registrar fecha, importe y nota, eligiendo origen y destino:

- persona → fondo;
- persona → persona;
- fondo → persona.

Un movimiento persona → persona redistribuye quién soportó el gasto y no cambia el saldo del fondo. Un movimiento persona → fondo sí incrementa el saldo verificado.

Aceptar un cierre no crea automáticamente estos movimientos reales; solo guarda el acuerdo mensual.

## Mercado Pago

### Clasificación de cuentas

Agregar a cada integración el rol `personal` o `fondo_comun`, con valor inicial `personal`.

- Cada usuario solo puede cambiar el rol de su propia integración, manteniendo las reglas actuales de propiedad del token.
- La pantalla del fondo muestra una fila por integrante: cuenta conectada, titular técnico y casilla «Usar para el fondo». Las cuentas ajenas se ven, pero solo su titular puede cambiar la casilla. Si no hay integración, la fila indica que debe conectarse desde Perfil.
- Una compra compartida desde una cuenta personal acredita al usuario como pagador directo.
- Una compra compartida desde una cuenta común reduce el fondo, pero no acredita al titular técnico del token.
- Aunque una cuenta esté marcada como común, solo sus consumos con `is_shared = true` entran en el gasto compartido.
- Al importar nuevas compras desde una cuenta MP común, marcarlas compartidas por defecto. Conservar las excepciones explícitas aprendidas; no reclasificar en masa los históricos al activar la cuenta.
- La lista de salidas a conciliar ofrece «Marcar compartida» para corregir una compra histórica o excepcional sin salir de la pantalla del fondo.
- La cuenta común se reserva para compras compartidas. Una compra marcada personal por error o excepción no entra en el reparto, pero reduce el saldo verificado y aparece como «salida personal a conciliar» atribuida al titular de esa cuenta.
- El titular debe reponer al fondo esa salida. Sus depósitos al fondo del mismo mes cubren primero esa reposición; solo el excedente cuenta como aporte a su cuota compartida. La propuesta de cierre muestra por separado cualquier importe personal aún por reponer. Para conciliar un mes cerrado, el reintegro debe registrarse con fecha contable de ese mes y reabrir el cierre.
- Cambiar el rol de una cuenta o el alcance compartido/personal de un consumo que afecte el cálculo desactualiza el cierre del mes.

### Ingresos y aportantes

- La pantalla muestra todos los ingresos importados de las cuentas MP comunes del hogar, con fecha y cuenta de destino, y permite filtrar por el mes seleccionado. No limita por defecto la lista al mes visible en el resto del fondo.
- Los ingresos de una MP común son candidatos a aportes.
- Nunca deben atribuirse automáticamente al titular del token solo por ser dueño de la integración.
- Intentar obtener un identificador estable del originante desde el settlement report o la API de Payments.
- Pedir al reporte `PAYER_NAME`, `PAYER_ID_TYPE`, `PAYER_ID_NUMBER` y `PAY_BANK_TRANSFER_ID`. Mostrar el nombre y solo los últimos cuatro dígitos del documento; usar un hash del tipo y número de documento como origen estable, nunca el número completo en la interfaz o reglas. Algunos movimientos pueden no traer estos campos.
- Si existe una regla aprendida para ese identificador, asignar el aporte automáticamente e indicar que proviene de una regla. Sin identificador fiable o regla previa, no inferir por descripción o importe.
- Si no hay certeza, dejar el movimiento pendiente para asignarlo a un miembro o excluirlo.
- Ofrecer `Recordar origen` únicamente cuando exista un identificador estable; no aprender por descripción o importe.
- El selector de ingresos solo ofrece «Pendiente», «Aporte de [integrante]» y «Excluir». No ofrece «Reembolso»: las devoluciones se concilian con el gasto original en un flujo separado y no se atribuyen como aportes.
- Al aparecer un ingreso MP equivalente a un movimiento manual ya registrado, vincularlos o pedir confirmación para evitar doble contabilización.
- En Carga de Resúmenes, además de la sincronización incremental, permitir sincronizar una fecha elegida. La sincronización diaria de producción se ejecuta a las 04:00 de Argentina con tres días de solapamiento; una sincronización histórica por fecha no mueve el cursor incremental.

Ejemplo MP:

- Mauro ingresa ARS 10.000.
- La cuenta gasta ARS 5.000.
- Mica ingresa ARS 15.000.
- La cuenta gasta ARS 10.000.
- El gasto total es ARS 15.000 y el saldo verificado remanente es ARS 10.000.
- Las compras no se acreditan a Mauro por ser titular; los aportes son Mauro ARS 10.000 y Mica ARS 15.000.

## Persistencia propuesta

Implementar cambios aditivos, sin reclasificar consumos históricos:

- `fund_month_configs`: hogar, período, monto mensual y metadatos de auditoría;
- `fund_month_shares`: configuración, usuario y porcentaje;
- `fund_opening_balances`: hogar, fecha de inicio e importe inicial;
- `fund_month_closures`: período, estado, fotografía del cálculo, huella de entradas y saldos acordados;
- `fund_closure_approvals`: cierre, usuario obligado, importe e instante de aceptación;
- `fund_manual_movements`: fecha, origen, destino, importe, nota y creador;
- `fund_mp_assignments`: ingreso/ImportLine, aportante, clasificación y estado;
- `fund_mp_origin_rules`: integración/origen estable y usuario asignado;
- columna `fund_role` en `mercadopago_integrations`.

Usar importes `Numeric/Decimal`, claves foráneas al hogar y usuarios, restricciones de unicidad por hogar/período y auditoría para crear, editar, borrar, cerrar, reabrir y asignar.

La huella de un cierre debe depender de la configuración efectiva, consumos incluidos, asignaciones MP y movimientos manuales relevantes. Una diferencia con la huella guardada marca el cierre como desactualizado.

## API propuesta

Agregar un router bajo `/households/{home_group_id}/fund`:

- `GET /summary?period=YYYY-MM`: configuración efectiva, totales, posiciones, plan de cierre, saldos, alertas y movimientos resumidos;
- `PUT /config/{period}`: guardar monto y porcentajes del mes;
- `PUT /opening-balance`: establecer o corregir saldo inicial;
- `POST /months/{period}/close`: generar la fotografía y propuesta de cierre;
- `POST /months/{period}/approve`: aceptar la parte del usuario autenticado;
- `POST /months/{period}/reopen`: reabrir con auditoría;
- `GET /series`: gastos, sobrante/exceso y saldos históricos;
- CRUD de `/manual-movements`;
- `PATCH /mp-contributions/{earning_id}`: asignar, excluir o corregir clasificación;
- endpoints para crear/eliminar reglas de origen MP.

Extender la API de Mercado Pago para exponer y actualizar `fund_role` sin exponer el token. El resumen del fondo puede mostrar metadata sanitizada de las integraciones del hogar.

## Reglas de permisos

- Todos los miembros del hogar pueden consultar la sección.
- Los cambios de configuración, saldo inicial, movimientos y cierres quedan auditados.
- Cada usuario aprueba únicamente su propia obligación de cierre.
- Cada usuario administra únicamente el rol de su integración MP.
- Las acciones nunca eliminan ni modifican consumos/importaciones originales desde la pantalla del fondo.

## Pruebas necesarias

### Backend

- herencia de configuración y validación de porcentajes;
- período de tarjeta por `statement_period` y fallback advertido;
- inclusión exclusiva de `is_shared`;
- conversión mediante `amount_ars`;
- cálculo de cuotas, adelantos, reintegros, depósitos y exceso;
- caso Mauro ARS 3,5 M: Mica → Mauro ARS 460k y Mica → Fondo ARS 500k;
- caso Mauro ARS 4 M: Mica → Mauro ARS 960k, sin aumentar el fondo;
- gasto superior al fondo con reparto porcentual y alerta;
- cuenta MP personal frente a común y ausencia de doble contabilización;
- ingresos MP pendientes, asignación manual, regla recordada y reembolsos;
- saldo inicial y acumulación entre meses;
- aceptación idempotente, cierre con múltiples obligados, reapertura y detección de cierre desactualizado;
- permisos de hogar e integración;
- edición/borrado de movimientos manuales y rechazo de mutaciones sobre filas derivadas.

### Frontend / E2E

- configuración inicial ARS 4 M, 76/24 e herencia mensual;
- selector de mes y estados del cierre;
- propuesta automática y una única confirmación por persona;
- saldos acordado, verificado y diferencia;
- advertencia por exceso y por datos MP pendientes;
- reapertura de un cierre desactualizado;
- clasificación de integración e ingresos MP;
- gráficos, tabla resumida y responsive layout;
- build del frontend y suite de Mercado Pago existente.

## Criterios de aceptación

- El usuario puede entender cuánto debe aportar cada persona sin hacer cálculos manuales.
- En el caso de ARS 3,5 M pagados por Mauro, Mica ve exactamente las dos acciones de ARS 460k y ARS 500k y solo debe aceptar el cierre.
- El mes siguiente toma ARS 500k como saldo acordado aunque la transferencia todavía no esté verificada.
- La pantalla nunca presenta un reintegro personal como dinero adicional del fondo.
- El titular de una cuenta MP común no recibe crédito por las compras realizadas desde ella.
- Los datos financieros actuales permanecen intactos y siguen editándose desde sus pantallas originales.
- Cualquier diferencia entre el acuerdo y los movimientos verificados queda visible y conciliable.
