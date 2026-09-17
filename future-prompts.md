Prompts:

- The "Consumos del hogar" page should allow:
 - to input a date when loading a new expense.
 - input 'Debito MercadoPago' as type of change (where you select efectivo, transferencia, etc)
 - Automatically select the payer as the currently logged user


The option to sincronize mercadopago should also be in "Carga de resumenes" dont remove it from the user config, in that place you can define the token and do a sync, but after that you would usually use the option from carga de resumens (which should not allow to udopate the token, just sync)

Poder categorizar cualqueir gasto como compartido entre el household o individual de la persona, y poder filtrar cualquiera de las paginas actuales por ese gasto compartido. Categorizacion inicial por defecto y aprendizaje de gastos compartidos (por ejemplo todos los servicios suelen ser compartidos, excepto chat gpt y telefonia movil, compras supercmercado, carniceria, etc suelen ser compartidos). Ademas tener una regla que si los gastos provinene de la tarjeta Mastercard de mauro , por defecto son todos compartidos ya que usamos esa tarjeta para eso.


Agregar uan funcionalidad en la pantalla de consumos que permita descargar todos los consumos como xls, tomar los filtros actuales para la descarga


En la seccion de consumos, la parte de nota tiene un icono el cual hay que cliquear para ver la nota, la nota deberia aparecer visible por defecto y al ser la columna bastante grande ya no creo que haya problema con el tamaño


Al cargar resumen de cuenta selecionar como pagador al usuario logueado por defecto

Al cargar el resumen de cuenta de debito se pueda modificar la descripcion del consumo antes de procesarlo )en la pantalla de carga por  ejemplo cargo el xls, se parsea y me muestra los cargos, ahi deberia poder modificarlo y luego procesarlo. Ademas guardar estas modificaciones en la memoria del browser o en algun lado ya que si se cierra la pagina o algo quisiera que queden hasta que se procese

Nueva seccion fondo comun de hogar
Trackear en una neuva seccion los gastos compartidos por mes y el aporte de cada persona. La idea es que con mi novia tengamos un fondo de 4 millones mensaules para gastos compartidos, el sobrante queda en el fondo para vacaciones u otras cosas. De ese fondo yo aporto el 76% y ella el 24% Para esta nueva funcionalidad quiero que:
- Haya una seccion de configuracion donde definimos el monto del fondo (inicialmente 4m), la participacion de cada uno porcentualmente. Que calcule cuanto tiene que aportar cada uno basado en esos parametros.
- Una seccion de visualizacion donde:
    - Muestre el monto del fondo (4 millones) y lo que deberia aportar cada uno
    - Que calcule basado en lo qeu debe aportar cada uno cuanto pago ya de por si teniendo en cuenta gastos en tarjetas de credito de ese mes (los cuales ya estarian cargados), Ingresos de dinero a mercado pago (aun a definir como trackearlo, por ahroa va a ser manual con la funcionalidad de abajo). Esto tiene que ser claro por ejemplo mauro tiene que poner 3.2m , pago en tarjeta  3m le quedan 200k, quizas da que puso de mas y por lo tanto micaela le deberia dar a manuro (a menos que ella haya puesto su % en tal caso el problema es que se excedio de los 4 millones). Proponer como hacer esto visualmente , quizas hacer algun mockiup inicial
    - Ingresar aporte (de forma manual y con fecha, por ejemplo mauro aporto xy en junio)
    - Gastos comaprtidos por mes (un grafico de barras)
    - Sobrante o exedente por mes (grafico de barras) Por ejemplo si un mes gastamos 3,5m deberia msotrar eso
    - Sobrantes acumulados hasta la fecha (se podria calcular teniendo en cuenta los aportes + los sobrantes - los gastos compartidos -  excedentes)
    - tabla de aportes (donde se pueda modificar / borrar entradas)
    - Con la funcionalidad ya existente de integracion con mercadopago, trackear los aportes de dinero de mauro y micaela, como usamos una cuenta compartida no se puede definir que si la cuenta es de mauro el aporte es de maruo, hay que verificar el detalle y revisar de que cuenta origin viene el ingreso de dinero a mercadopago y su fecha, esto deberia contar para los aportes de dinero de cada uno. 
Los gastos siempre se consideran por mes de la fecha del gasto

