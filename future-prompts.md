

Nueva seccion fondo comun de hogar
Trackear en una neuva seccion los gastos compartidos por mes y el aporte de cada persona. 

Contexto del end user: La idea es que con mi novia tengamos un fondo de 4 millones mensaules para gastos compartidos, el sobrante queda en el fondo para vacaciones u otras cosas. De ese fondo yo aporto el 76% y ella el 24%.

Para esta nueva funcionalidad quiero que haya una pantalla nueva con:
- Una pequeña seccion de configuracion donde definimos el monto del fondo (el cual se debe mantener en los meses a menos que se actualice, por lo que se deberia persistir por mes. Por defecto deberia tomar el valor del ultimo mes. Poner inicialmente 4 millones de pesos), la participacion de cada uno porcentualmente. Que calcule el monto en pesos que tiene que aportar cada uno basado en esos parametros (monto total * participacion, e.g. 4.000.000 * 0.24).
- Una seccion de visualizacion donde:
    - Muestre el monto del fondo (4 millones) y lo que deberia aportar cada uno
    - Que calcule basado en lo que debe aportar cada uno cuanto pago ya de por si teniendo en cuenta gastos en tarjetas de credito de ese mes (los cuales ya estarian cargados), Ingresos de dinero a mercado pago y otros gastos trackeados en la pagina. Esto tiene que ser claro por ejemplo mauro tiene que poner 3.2m , pago en tarjeta  3m le quedan 200k, quizas da que puso de mas y por lo tanto micaela le deberia dar a manuro (a menos que ella haya puesto su % en tal caso el problema es que se excedio de los 4 millones). Proponer como hacer esto visualmente , quizas hacer algun mockiup inicial
    - Ingresar aporte (de forma manual y con fecha, por ejemplo mauro aporto xy en junio), con un campo notas
    - Gastos comaprtidos por mes (un grafico de barras), seria lo mismo que en la pagina inicial pero en esta nueva pagina.
    - Sobrante o exedente por mes (grafico de barras) Por ejemplo si un mes gastamos 3,5m y el fondo era 4m deberia motrar que sobraron 500k
    - Sobrantes acumulados hasta la fecha (se podria calcular teniendo en cuenta los aportes + los sobrantes - los gastos compartidos -  excedentes)
    - tabla de ingresos y egresos que muestre consumo resumido de gastos pagados. Creo que aca es importante saber el grado de granularidad que queremos, la idea es que no esten todos los gastos item por item, sino que diga Mauro tarjeta mastercard 2 millones, ingreso manual aporte 100k, ingreso mercado pago 10k (aca si que sea granular lo del ingreso mercado pago). Ademas que se puedan modificar / borrar entradas.
    - Con la funcionalidad ya existente de integracion con mercadopago, trackear los aportes de dinero de mauro y micaela, basicamente los ingresos de dinero. Como usamos una cuenta compartida no se puede definir que si la cuenta es de mauro el aporte es de maruo, hay que verificar el detalle y revisar de que cuenta origin viene el ingreso de dinero a mercadopago y su fecha, esto deberia contar para los aportes de dinero de cada uno. Un desafio aca es que micaela tambien va a tener su cuenta de mercado pago integrada para realizar compras, pero esas compras se consideran todas individuales. Esto habria qeu ver como manejarlo, quizas que muestre las cuentas de mercado pago y poder marcarla como compartida o individual?

    - los gastos de tarjeta deberian considerarse para el mes de cierre (o el anterior si es a principio del mes siguiente), por ejemplo a veces los gastos de junio que uno paga en julio la tarjeta peude cerrar a fin de junio o a principio de julio pero los gastos se deberian considerar de junios. Para esto dame feedbackq eu te parece con respecto a lo que buscamos de la funcionaldiad que basicamente es organizar nuestras finanzas por un fondo compartido equitativamente, el cual revisariamos cuandoi pagamos las tarjetas, la idea principal del sistema es

Uno de los desafios de esta funcionalidad es que los gastos de mercado pago pueden aparecer como que mauro fue el pagador ya que usamos mi cuenta pero como micaela tambien aporta a esa cuenta en realidad tambien lo estaria pagando ella, pongamos un ejemplo para analizarlo

Mauro ingresa 10k
Cuenta se gasta 5k
Micaela ingresa 15k
Cuenta se gastan 10k
Remanente 10k
Gasto total 15k
Ingreso total 25k


No se si esto traeria algun problema la veradd, lo que pienso es que quizas apra esta funcionalidad no importa tanto quien pago sino quien Aporto y el gasto total, por ejemplo en mercado pago se toman los ingresos como aportes y el gasto total. En  otros gastos si se toma el pagador como aporte porque no se comparte, si viene el resumen a mi banco voy a ser yo quien lo pague y luego se vera si mica me tiene que trasnferir plata o no. AnALIZAR la funcionalidad  para saber si tiene sentido o conviene cambiar algo, La idea es no modificar los datos actuales en si, sino generar una nueva vista y agregar las cosas necesarias.