# Prompt para auditar el proyecto

Primero generar el paquete de código:

```bash
python scripts/empaquetar.py
```

Eso deja `docs/codigo-completo.txt` (~60 mil tokens, cabe en cualquier modelo
actual). Se sube ese archivo o se pega su contenido, y se usa el prompt de abajo.

---

```
Eres un ingeniero senior auditando un sistema antes de que se venda a empresas.
Te voy a dar el código completo. Quiero una auditoría dura y concreta, no una
lista de buenas prácticas genéricas.

## Qué es el sistema

Un agente de IA que contesta llamadas telefónicas de clientes de una
distribuidora, entiende el pedido dicho con palabras del cliente ("mándame
cuarenta bultos de la de siempre"), verifica contra inventario real, arma el
pedido y lo escribe al ERP. Atiende voz, WhatsApp y texto.

Python 3.11+, FastAPI, SQLite (con la intención de migrar a Postgres), SDK de
Anthropic y de Google GenAI.

## Qué está en juego

Esto NO es un proyecto de práctica. Se va a vender a empresas reales y va a
manejar:

- Datos de clientes: nombres, razón social, teléfonos, líneas de crédito, saldos
- Dinero: pedidos de decenas de miles de pesos que se escriben a un ERP
- Grabaciones y transcripciones de llamadas telefónicas
- Inventario del que dependen decisiones de venta

Un error aquí no es un bug de consola: es un pedido mal escrito al ERP, material
prometido que no existe, o datos de clientes expuestos.

## Decisiones de diseño INTENCIONALES

Esto NO son bugs. Si crees que alguna está mal, discútela con argumentos, pero
no la reportes como hallazgo por desconocimiento:

1. El LLM nunca produce un dato. Solo entiende, llama herramientas y habla.
   Existencias, precios y fechas salen de consultas deterministas.
2. El inventario es un espejo local; nunca se consulta el ERP en vivo durante
   una llamada.
3. Disponible = existencia − comprometido − reservas activas, más un colchón.
4. El pedido se arma como borrador local y se escribe al ERP solo al final, de
   forma idempotente.
5. Todo pedido pasa por aprobación humana por defecto.
6. La ambigüedad se pregunta, no se adivina.
7. Dos modelos corren en paralelo, nunca en cadena: uno rápido que solo dice
   una frase de acuse sin datos, y uno pesado que hace el trabajo.
8. Cada partida del pedido guarda la frase que la originó y el offset del audio.
9. Cuando falta material nunca se contesta solo "no hay": se devuelve un plan
   con lo que hay hoy, lo que entra después y qué sustituto sirve.
10. El proveedor de modelo es intercambiable; las herramientas se definen una
    sola vez y se traducen.

## Qué quiero que audites

Ve en este orden de importancia.

### 1. Correctitud del dinero y del inventario

Esto es lo que más importa. Busca específicamente:

- **Condiciones de carrera.** ¿Dos llamadas simultáneas pueden reservar el mismo
  material? Mira `inventario.reservar()`: lee disponibilidad y luego inserta.
  ¿Son atómicas esas dos operaciones? ¿Qué pasa con dos procesos?
- **Aritmética.** Conversiones de unidades (kg ↔ bultos ↔ tarimas), cálculo de
  importes, redondeo de dinero. ¿Se usa float para dinero? ¿Importa aquí?
- **Idempotencia real.** `pedidos.escribir_en_erp()` dice ser idempotente.
  ¿Lo es de verdad si el ERP responde después de un timeout de red?
- **Máquina de estados del pedido.** ¿Hay transiciones que dejen el sistema
  inconsistente? ¿Reservas que queden colgadas? ¿Material apartado que nunca
  se libere?
- **Transacciones.** ¿Hay operaciones que deberían ser atómicas y están en
  transacciones separadas?

### 2. Seguridad

- **Autenticación y autorización.** Revisa `canales/panel.py`. ¿Quién puede
  aprobar un pedido y escribirlo al ERP?
- **CORS.** ¿Cómo está configurado y qué implica en producción?
- **Inyección SQL.** ¿Todas las consultas usan parámetros? Busca f-strings
  dentro de SQL.
- **Secretos.** ¿Hay llaves o credenciales en código o que puedan terminar en
  logs?
- **El WebSocket de voz.** ¿Valida que quien conecta sea realmente Twilio?
- **Datos personales.** Con teléfonos, nombres y saldos de clientes: ¿qué se
  registra en la traza y qué se manda al proveedor del modelo?
- **Inyección de prompt.** El cliente habla libremente por teléfono y eso llega
  al modelo. ¿Puede un cliente hacer que el agente se salte reglas, cambie
  precios, o se comprometa a algo que no debe?

### 3. Escalabilidad

El sistema se va a vender a varias empresas a la vez.

- **SQLite.** ¿Hasta dónde aguanta? ¿Qué se rompe primero al migrar a Postgres?
  ¿Hay SQL específico de SQLite?
- **Estado en memoria.** Busca diccionarios a nivel de módulo. ¿Qué pasa con
  dos instancias del proceso detrás de un balanceador?
- **Multi-tenant.** Todas las tablas llevan `tenant`. ¿Se filtra por él en TODAS
  las consultas? Busca alguna que se le haya olvidado — eso sería una fuga de
  datos entre clientes.
- **Concurrencia.** ¿El código async bloquea en operaciones síncronas de base de
  datos? ¿Importa?

### 4. Robustez en llamada

Una excepción no manejada con un cliente en la línea es una llamada perdida.

- ¿Qué pasa si la API del modelo falla a media llamada?
- ¿Si el ERP no responde?
- ¿Si la base de datos está bloqueada?
- ¿Si el cliente cuelga a media transacción?
- ¿Hay algún camino donde una excepción suba hasta tumbar el WebSocket?

### 5. Lo que falta para producción

Sé concreto: qué le falta a esto para ponerlo frente a un cliente que paga.

## Formato de la respuesta

Para cada hallazgo:

**[SEVERIDAD] Título corto**
- Dónde: `archivo.py:línea`
- Qué pasa: una o dos frases
- Cómo se rompe: un escenario concreto con datos concretos, no teoría
- Cómo se arregla: la corrección específica

Severidades: CRÍTICO (pierde dinero, corrompe datos o expone información),
ALTO (falla en producción bajo condiciones normales), MEDIO (falla en casos
límite), BAJO (deuda técnica).

Ordena por severidad. Al final, dame las 5 cosas que arreglaría yo primero si
solo tuviera un día.

## Qué NO quiero

- "Agrega type hints", "considera usar logging", "falta documentación" —
  a menos que la ausencia cause un bug concreto.
- Reescribir el estilo. El código está en español a propósito.
- Sugerencias de arquitectura alternativa sin señalar un problema real en la
  actual.
- Hallazgos inventados para llenar la lista. Si algo está bien, dilo.

Prefiero cinco hallazgos reales que cuarenta genéricos.
```

---

## Lo que ya sé que está flojo

Para que la auditoría no te tome por sorpresa, estas son las debilidades que
conozco y que el auditor debería confirmar:

| Qué | Dónde | Gravedad |
|---|---|---|
| El panel no tiene autenticación: quien llegue al puerto aprueba pedidos y escribe al ERP | `canales/panel.py` | **Crítico para producción** |
| CORS abierto a `*` por defecto | `canales/panel.py:38` | Alto |
| Posible carrera al reservar: leer disponibilidad e insertar no son atómicas | `inventario.reservar()` | Alto |
| Sesiones de voz en memoria del proceso: se rompe con más de una instancia | `canales/voz.py:45` | Medio (hasta escalar) |
| El WebSocket de voz no valida que quien conecta sea Twilio | `canales/voz.py` | Alto |
| SQLite: aguanta un tenant, no varios con carga | `db.py` | Medio (conocido) |
| Dinero en `float` en vez de decimal | esquema y `pedidos.py` | Medio |

Ninguna impide demostrar el sistema. Todas hay que resolverlas antes de
facturarle a un cliente.
