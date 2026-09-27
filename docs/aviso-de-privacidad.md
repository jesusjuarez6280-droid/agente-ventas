# Aviso de privacidad

> **Esto es una plantilla, no un documento legal listo para usar.** Está
> redactada a partir de lo que el sistema hace realmente con los datos, para
> que sirva de punto de partida. Antes de entregarla a un cliente o publicarla,
> **debe revisarla un abogado**: los nombres, domicilios, plazos y la
> designación del responsable cambian en cada implantación, y un aviso mal
> redactado no protege a nadie.
>
> En este repositorio cumple otra función además: documenta con precisión qué
> datos toca el sistema y dónde quedan, que es información que cualquiera
> debería poder revisar antes de conectarlo a clientes reales.

---

## Qué datos personales trata este sistema

Esto no es una lista genérica: sale de las tablas del esquema.

### De los clientes de la empresa que lo implanta

| Dato | Dónde vive | Para qué |
|---|---|---|
| Nombre y razón social | tabla `clientes` | Reconocer a quien llama y saludarlo por su nombre |
| Teléfono | `clientes`, `conversaciones` | Identificar la llamada entrante antes de contestar |
| Nombre del vendedor asignado | `clientes` | Transferir la llamada a la persona correcta |
| Límite de crédito, saldo y días de crédito | `clientes` | Verificar si el pedido cabe en su línea de crédito |
| Historial de compras | `historial_compras` | Resolver frases como *"mándame lo de siempre"* |
| Pedidos y sus partidas | `pedidos`, `partidas` | Operar la venta y escribirla al ERP |
| Quejas, aclaraciones y seguimientos | `incidencias` | Dar seguimiento a lo que no se resolvió en la llamada |

### De las conversaciones

| Dato | Dónde vive | Para qué |
|---|---|---|
| Transcripción completa de la llamada | tabla `traza` | Auditar lo acordado y depurar errores del agente |
| Frase textual que originó cada partida | `partidas.frase_origen` | Resolver disputas sobre lo que se pidió |
| Momento del audio de cada partida | `partidas.offset_audio_ms` | Poder reproducir la grabación desde ese segundo |
| Grabación de audio | `conversaciones.ruta_audio` | Prueba de lo acordado |
| Motivo por el que se escaló a una persona | `conversaciones.motivo_cierre` | Mejorar el servicio |

### De quienes operan el panel

| Dato | Dónde vive | Para qué |
|---|---|---|
| Usuario, nombre y rol | tabla `usuarios` | Controlar quién puede aprobar pedidos |
| Contraseña | `usuarios.password_hash` | **Nunca se guarda en claro.** Se guarda con scrypt y sal |
| Último acceso y sesiones activas | `usuarios`, `sesiones` | Seguridad y cierre de sesión |

---

## Terceros que reciben datos

Esto es lo que más suele pasarse por alto, y es lo que un cliente pregunta:

| Tercero | Qué recibe | Cuándo |
|---|---|---|
| **Proveedor del modelo** (Anthropic o Google, según configuración) | El texto de la conversación y el nombre del producto consultado | En cada turno |
| **Proveedor de telefonía** (Twilio, si se usa el canal de voz) | El audio de la llamada y su transcripción | Durante la llamada |
| **ERP del cliente** | Los pedidos confirmados | Al aprobar |

**Advertencia sobre los niveles gratuitos.** El nivel gratuito de Gemini usa los
datos enviados para mejorar sus modelos. **No debe usarse con datos de clientes
reales.** Para operar con datos reales hay que estar en un nivel de pago, donde
el contenido no se utiliza para entrenamiento. Lo mismo aplica a cualquier
proveedor: hay que verificar su política antes de conectar datos de verdad.

---

## Plantilla del aviso

> Lo de abajo es el texto que iría dirigido a los titulares de los datos.
> Sustituir lo que está entre corchetes.

---

**AVISO DE PRIVACIDAD**

**[Razón social de la empresa]**, con domicilio en **[domicilio fiscal]**, es
responsable del tratamiento de sus datos personales, conforme a la Ley Federal
de Protección de Datos Personales en Posesión de los Particulares.

**Datos que recabamos.** Nombre, razón social, teléfono, domicilio de entrega,
información de crédito e historial de compras. Cuando usted se comunica con
nosotros por teléfono, recabamos también la grabación y la transcripción de la
llamada.

**Grabación de llamadas.** Las llamadas que usted realiza a nuestros números de
atención son grabadas y transcritas. Se le informa de ello al inicio de cada
llamada. Si no desea ser grabado, puede solicitar atención por otro medio.

**Atención automatizada.** Sus llamadas pueden ser atendidas por un sistema
automatizado que toma su pedido. Usted puede solicitar en cualquier momento
hablar con una persona, y será transferido.

**Finalidades.** Los datos se utilizan para atender y surtir sus pedidos,
verificar su línea de crédito, dar seguimiento a aclaraciones, y como
constancia de lo acordado. No se utilizan para fines distintos ni se venden a
terceros.

**Transferencias.** Para prestar el servicio, sus datos pueden ser procesados
por nuestros proveedores de tecnología de telefonía e inteligencia artificial,
bajo contrato y únicamente para las finalidades descritas.

**Conservación.** Los datos se conservan mientras dure la relación comercial y
por **[plazo]** adicional, conforme a las obligaciones fiscales aplicables.

**Sus derechos.** Usted puede acceder, rectificar, cancelar u oponerse al
tratamiento de sus datos (derechos ARCO), así como revocar su consentimiento,
escribiendo a **[correo de contacto]**. Responderemos en un plazo máximo de
veinte días hábiles.

**Cambios.** Cualquier modificación a este aviso se publicará en
**[sitio web]**.

**Última actualización: [fecha]**

---

## Qué le falta al sistema para cumplir

Con honestidad, para que un cliente pueda operar esto en cumplimiento:

- **Borrado de datos a petición** (derecho de cancelación). Hoy no hay una
  operación que borre a un cliente y toda su traza.
- **Retención automática.** Nada purga conversaciones viejas; se acumulan
  indefinidamente.
- **Cifrado en reposo** de grabaciones y transcripciones.
- **Bitácora de accesos**: quién consultó qué datos de qué cliente y cuándo.
- **Consentimiento registrado** para la grabación, no solo anunciado en voz.

El aviso de grabación al inicio de la llamada **sí** está implementado: vive en
`config/giros/granos.yaml` bajo `aviso_grabacion` y el agente lo dice en el
saludo.
