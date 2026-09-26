# Prompt para la IA de diseño

Copiar todo lo que está dentro del bloque y pegarlo en la herramienta de diseño
(v0, Lovable, Figma Make, Claude, la que sea).

Los campos que aparecen abajo son los reales de la base — no son inventados.
Eso importa: si el diseño usa campos que existen, conectarlo después es trabajo
de horas en vez de rediseñar.

---

```
Diseña el panel web de un agente de inteligencia artificial que contesta llamadas
telefónicas de clientes y levanta pedidos de venta, conectado al inventario y al
ERP de la empresa.

## Qué es el producto

Una distribuidora de productos a granel (harinas, azúcares, granos) recibe
llamadas de sus clientes para hacer pedidos. Un agente de IA contesta el
teléfono, reconoce quién llama, entiende lo que pide aunque lo diga con sus
propias palabras ("mándame cuarenta bultos de la de siempre"), verifica contra
el inventario real, arma el pedido y lo deja registrado.

Este panel es donde la empresa VE y CONTROLA lo que el agente está haciendo.

El producto se vende a distintos giros — ferreterías, refaccionarias,
distribuidoras — así que el diseño no debe amarrarse a nombres de productos
específicos.

## Quién lo usa

1. **Mesa de control / capturista.** Todo el día en la Bandeja. Su trabajo es
   revisar y soltar los pedidos que levantó la IA. Necesita velocidad: muchos
   pedidos, pocos clics, teclado.

2. **Gerente de ventas.** Entra dos o tres veces al día. Quiere saber cuánto se
   vendió, qué se perdió por falta de inventario, y si el agente está fallando.

3. **Dueño / director.** Entra una vez a la semana. Quiere una sola pantalla que
   le diga si esto vale la pena.

4. **El vendedor del sistema (durante demostraciones).** Necesita que se vea
   impresionante y que se entienda en treinta segundos.

## Pantallas

### 1. BANDEJA DE APROBACIÓN — la pantalla principal

Es el corazón del producto. La IA levanta pedidos pero NO los escribe al ERP sin
que una persona los apruebe. Aquí es donde eso pasa.

Lista de pedidos pendientes. Cada tarjeta muestra:
- Folio (ej. BOR-04E816DF12)
- Cliente y su teléfono
- Canal por el que entró: voz, whatsapp, texto, email
- Hora
- Las partidas: número de línea, descripción del producto, cantidad en kg,
  cómo lo pidió el cliente ("40 bultos"), precio unitario, importe
- Total
- Crédito disponible del cliente y si el pedido cabe en ese crédito
- Banderas de riesgo si las hay: crédito excedido, inventario justo, cliente
  nuevo no registrado, producto sustituido

Dos acciones grandes: **Aprobar** (se escribe al ERP) y **Rechazar** (se cancela
y se libera el material apartado). Y una tercera, secundaria: **Editar antes de
aprobar**.

Requisito fuerte: esta pantalla se opera con teclado. Flechas para moverse entre
pedidos, una tecla para aprobar, otra para rechazar. Quien la usa va a pasar aquí
seis horas al día.

Debe poder aprobarse en lote cuando los pedidos no tienen banderas.

### 2. DETALLE DE CONVERSACIÓN — el diferenciador

Se abre al hacer clic en un pedido. Muestra la llamada completa.

A la izquierda, la transcripción tipo chat: turnos del cliente y del agente, con
marca de tiempo. Entre los turnos, marcadores discretos de cada consulta que hizo
el agente al sistema (buscar_producto, consultar_disponibilidad, agregar_al_pedido…)
con su latencia en milisegundos.

A la derecha, el pedido que salió de esa conversación.

**Lo más importante de esta pantalla:** cada renglón del pedido está ENLAZADO a
la frase exacta de la conversación que lo originó. Al pasar el cursor o hacer
clic sobre un renglón, se resalta en la transcripción la frase donde el cliente
lo pidió, y si fue una llamada, se puede reproducir el audio desde ese segundo
exacto.

Ese enlace resuelve las disputas: cuando el cliente reclame "yo pedí doscientos,
no cien", se abre el renglón y suena su propia voz. Diséñalo como la joya de la
pantalla, no como un detalle.

Si hubo un reproductor de audio, que la barra de progreso tenga marcas en los
momentos donde se originó cada partida.

### 3. TABLERO

Lo que la empresa quiere saber. Selector de periodo: hoy, semana, mes.

Indicadores principales, arriba:
- Llamadas atendidas
- Pedidos levantados y monto total vendido
- **Tasa de acierto**: porcentaje de pedidos que se aprobaron sin corregir nada.
  Esta es LA métrica del producto: mientras no suba de 95% la IA no escribe sola
  al ERP. Dale el tamaño y la jerarquía de una métrica crítica, con su tendencia.
- Tiempo promedio de respuesta del agente, en milisegundos
- Escalamientos a persona, con el motivo

Después, tres bloques que valen oro comercialmente:

**Venta en riesgo.** Lista de lo que los clientes pidieron y no había, con el
monto que eso representa. Ordenado por dinero perdido. Es el argumento de compra
más fuerte del producto: "tu inventario te costó tanto este mes y no lo sabías".

**Lo que la IA no entendió.** Términos que los clientes usaron y el catálogo no
reconoció, con cuántas veces se repitieron. Cada uno tiene un botón para
asignarlo a un producto y que la próxima vez sí se entienda. Muestra que el
sistema mejora solo.

**Actividad por hora.** Gráfica de cuándo entran las llamadas. Sirve para
justificar el producto: la barra de las 7 de la mañana y la de las 9 de la noche
son las horas donde no hay nadie contestando.

### 4. SALUD DEL CATÁLOGO

Tabla de productos con: SKU, nombre, cuántos alias tiene registrados, cuántas
veces se pidió este mes, y una barra de "qué tan bien se entiende" (basada en la
confianza promedio con que se reconoció).

Los productos que se piden mucho y se entienden mal van arriba, marcados. Ahí es
donde hay que agregar sinónimos.

Debe poder agregarse un alias nuevo sin salir de la tabla.

### 5. INVENTARIO Y ENTRADAS

Por producto: existencia, comprometido, apartado en llamadas activas, y
disponible real. Que se vea que "disponible" no es lo mismo que "existencia".

Debajo, lo que viene en camino: compras y producción programada con su fecha y
si está confirmada o es estimada. El agente usa esto para decir "hoy no tengo,
pero el jueves entran ocho toneladas" en vez de "no hay".

### 6. LLAMADAS EN VIVO (opcional, para demostraciones)

Las llamadas que están ocurriendo en este momento. La transcripción apareciendo
en tiempo real, el pedido armándose renglón por renglón mientras el cliente
habla. Es puro efecto, pero cierra ventas.

## Los datos reales

Estos son los campos que existen en la base. Úsalos con estos nombres.

**pedidos**: folio, cliente_id, canal (voz|whatsapp|texto|email), estado
(borrador|por_aprobar|confirmado|en_erp|fallido|cancelado), total, fecha_entrega,
observaciones, folio_erp, motivo_fallo, creado_en, conversacion_id

**partidas**: linea, sku, descripcion, cantidad_kg, cantidad_texto ("40 bultos"),
precio_unitario, importe, frase_origen, offset_audio_ms

**clientes**: cliente_id, nombre, razon_social, telefono, vendedor,
limite_credito, saldo_actual, dias_credito

**productos**: sku, nombre_erp, nombre_corto, alias, presentaciones, precio_kg

**existencias**: sku, almacen, existencia_kg, comprometido_kg

**reposiciones**: sku, cantidad_kg, fecha_estimada, origen (compra|produccion|
traspaso), confianza (confirmada|estimada), referencia

**traza**: conversacion_id, secuencia, tipo (cliente|agente|herramienta|sistema),
contenido, herramienta, entrada, salida, latencia_ms, offset_audio_ms, creado_en

**conversaciones**: conversacion_id, canal, telefono, cliente_id, estado
(abierta|cerrada|escalada), motivo_cierre, iniciada_en, terminada_en

**incidencias**: tipo (queja|consulta|seguimiento|aclaracion), resumen, detalle,
prioridad, estado

**alias_pendientes**: termino, veces, sku_resuelto, revisado

## Cómo debe verse

Es software de trabajo para gente de bodega y oficina en México, no una app de
consumo. Que se vea serio y confiable, no juguetón.

- **Densidad alta.** Prefiere tablas compactas sobre tarjetas grandes con aire.
  Quien lo usa quiere ver veinte pedidos en pantalla, no tres.
- **Los números mandan.** Tipografía tabular en todo lo que sea cantidad o
  dinero, alineada a la derecha. Los pesos siempre con separador de miles.
- **Color con oficio.** Un acento único y tres semánticos: verde aprobado, ámbar
  requiere atención, rojo problema. Nada de degradados ni de siete colores.
- **Modo claro y oscuro**, los dos resueltos.
- **Español de México**, neutro pero natural.
- **Funciona en tablet**, porque el gerente de almacén anda con una en la mano.
  En teléfono basta con que la Bandeja y el Tablero se vean bien.

## Qué NO hacer

- Nada de "IA" decorativa: sin cerebros, sin chispas, sin círculos pulsantes
  morados. El producto se vende por la operación, no por la moda.
- Sin tarjetas enormes con un solo número gigante y mucho vacío.
- Sin gráficas que no se puedan leer de un vistazo. Si una gráfica necesita
  leyenda de siete colores, está mal planteada.
- Sin diálogos modales para aprobar. Eso tiene que ser una tecla.
- Sin texto de relleno tipo "Bienvenido a tu dashboard".

## Entregable

Prioriza en este orden: Bandeja de Aprobación, Detalle de Conversación, Tablero.
Esas tres son el producto. Las demás pueden quedar más esquemáticas.

Entrega HTML con Tailwind, o React con Tailwind. Datos de ejemplo realistas ya
puestos (clientes mexicanos, productos a granel, montos en pesos de entre veinte
mil y doscientos mil). Componentes separados y limpios, porque esto se va a
conectar a una API real después.
```

---

## Después de que la IA de diseño entregue

El backend ya tiene los endpoints listos en `src/agente/canales/panel.py`:

| Endpoint | Devuelve |
|---|---|
| `GET /api/bandeja` | Pedidos por aprobar con partidas, crédito y banderas |
| `POST /api/pedidos/{folio}/aprobar` | Aprueba y escribe al ERP |
| `POST /api/pedidos/{folio}/rechazar` | Cancela y libera reservas |
| `GET /api/conversaciones/{id}` | Transcripción con enlace a cada partida |
| `GET /api/metricas?periodo=hoy` | Todo el tablero |
| `GET /api/catalogo/salud` | Productos y qué tan bien se entienden |
| `POST /api/catalogo/alias` | Agrega un alias aprendido |
| `GET /api/inventario` | Existencias, apartados y entradas programadas |

Levantarlo:

```bash
uvicorn agente.canales.panel:app --port 8080 --reload
```

Y abrir `http://localhost:8080/docs` para ver todos los endpoints con sus
respuestas de ejemplo. Eso se le puede pasar también a la IA de diseño.
