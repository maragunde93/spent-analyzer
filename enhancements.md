Lee docs/codex_context.md y trabaja principalmente en el modulo de importar consumos (solo consultar otros modulos si es absolutamente necesario). Quisiera que haya un boton al importar consumos al lado de la persona que tiene los consumos para copiar al portapapeles los consumos (esto es principalmente para luego enviarlo por whatsapp a la persona dueña de la tarjeta). Deberia copiar en el siguiente formato:
Total Ars: XXXX Total USD: XXX
Consumo x 
Consumo y
O sea los totales en cada moneda y despues las lineas de consumo con la descripcion y el monto de cada uno


Lee docs/codex_context.md y trabaja solo en el modulo de historial, quiero que el resumen de importaciones guarde el valor de conversion dolar blue ars utilizado en esa carga (tomar el valor del dia de la carga que este guardado en la base de datos). Ademas en el mismo modulo quiero que corrijas la logica, actualmente crea una nueva linea si ya hay un mes que tiene el statement procesado y lo vuelvo a cargar. Quiero evitar eso ya que el resumen es basicamente para saber si un mes fue cargado o no, si lo cargo 1 o 3 veces no deberia cambiar el resumen en si. Por lo  que la logica debeira ser: si el statement de la tarjeta ya esta cargado para ese mes, no crear una nueva fila, simplemente ignorarlo. ESTO DBERIA SER por tarjeta y pagador, por ejemplo statement cuenta, tarjeta visa mauro, tarjeta visa mica, tarjeta mastercard mauro, esttan bien, pperoo no deberia haber 2 tarjeta visa pago por mauro.

Revisar por que hay impuestos negativos como consumos, esto no es solo un tema de la app sino del resumen en si, el resumen de mica tiene un impouesto negativo sin su contraparte positiva lo que es extraño, entender primero el caso de uso real y despues mejorar la app

Mejorar el grafico de consumo acumulado, deberia ser mas alto para tener mas espacio y ademas poder mostrar bien el tooltip del mouse over, actualmente el tooltip esta quedanto trabado a la izquiera y no se ve entero.

Evaluar si mejorar el nombred de herramientas para que incluya arreglos de la casa o poner algunacategoria nueva o trackearlo denro de hogar etc