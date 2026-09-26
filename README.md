# Agente de ventas por teléfono

Contesta la llamada, entiende el pedido como lo dice el cliente, lo verifica
contra el inventario real y lo registra en el ERP.

```
CLIENTE  Que tal, necesito cuarenta bultos de harina refinada.
AGENTE   Anotado: 2,000 kg (1 tarima) de harina de trigo refinada
         a $18.50/kg = $37,000.00. ¿Algo más?

CLIENTE  También mándame quinientos kilos de azúcar refinada.
AGENTE   De azúcar refinada nada más tengo 150 kg. La estándar cubre
         la cantidad completa hoy, y usted ya la ha comprado antes.
         ¿Le sirve?

CLIENTE  Va, mándame de la estándar entonces.
AGENTE   Anotado: 500 kg (10 bultos) de azúcar estándar...
```

## Pruébalo en un minuto, sin pagar nada

```bash
pip install -r requirements.txt && python scripts/init_db.py --reset
```

```bash
python scripts/demo_sin_api.py
```

Eso corre la llamada completa: reconoce quién marca, entiende *"cuarenta bultos
de la de siempre"*, se niega a prometer material que no hay, ofrece la
alternativa que ese cliente ya compra, arma el pedido y deja traza. **Sin llave
de API, sin cuenta, sin costo.**

Y el núcleo entero, verificado:

```bash
python scripts/probar_nucleo.py
```

## Los problemas que resuelve

Lo difícil de esto no es que la IA hable. Es otra cosa:

**Traducir cómo habla el cliente a tu catálogo.** Nadie dice *"SKU HAR-TRG-REF,
500 kilogramos"*. Dicen *"mándame 20 bultos de la de siempre"*. La búsqueda va
en cascada — SKU, alias registrado, todos los términos, similitud difusa — y si
dos productos empatan, **pregunta en vez de adivinar**. Los términos que no
entiende quedan anotados para que alguien los enseñe; la siguiente llamada ya
los reconoce.

**Que el modelo no invente.** El LLM solo hace tres cosas: entender, llamar
herramientas y hablar. Cada existencia, precio y fecha sale de una consulta
determinista. Si la herramienta falla, dice *"déjeme confirmarlo"* — no adivina.

**Que el ERP no se ensucie.** El pedido se arma como borrador local y se escribe
al ERP hasta el final, de forma idempotente y tras revalidar el material. Si la
llamada se cae o el modelo se equivoca, el ERP nunca se enteró.

**Que suene a persona.** Un segundo de silencio se siente a robot. Se resuelve
con precarga por número entrante, una frase de acuse que se dice *mientras* se
consulta, y streaming al sintetizador.

## Lo que hay dentro

| | |
|---|---|
| **Tres cerebros intercambiables** | Claude, Gemini y uno de reglas sin costo. Mismo contrato, una variable de entorno |
| **Adaptadores de ERP** | Ocho operaciones. SAP, Odoo, Contpaqi o SQL directo se enchufan sin tocar el motor |
| **Paquetes de giro** | Un YAML por ramo. Cambiar de granos a ferretería es configuración, no código |
| **Panel web** | Bandeja de aprobación operable con teclado, con autenticación y roles |
| **Trazabilidad de origen** | Cada renglón del pedido sabe qué frase lo originó y en qué segundo del audio |
| **Auditado** | Una auditoría externa encontró 15 hallazgos; los críticos están corregidos con pruebas que los reproducen |

## Estado

Funcionando y verificado: catálogo, inventario con reservas que vencen, pedidos,
idempotencia, métricas, panel con autenticación, y los tres proveedores.

Sin cerrar todavía: dinero en `float` en vez de `Decimal`, verificación de que lo
que el modelo *dice* coincide con lo que las herramientas devolvieron, y firma de
los webhooks de telefonía. Están documentados en
[docs/prompt-auditoria.md](docs/prompt-auditoria.md).

---

## Arrancar

```bash
python -m pip install -r requirements.txt
```

```bash
cp .env.example .env
```

```bash
python scripts/init_db.py --reset
```

Verifica que el núcleo funciona — no gasta un solo token de modelo:

```bash
python scripts/probar_nucleo.py
```

Y que los dos carriles de voz no se encimen:

```bash
python scripts/probar_puente.py
```

## Demostrarlo sin pagar nada

Antes de tener llave de API, el sistema completo corre en modo demostración:

```bash
python scripts/demo_sin_api.py
```

Reconoce al que llama, entiende *"cuarenta bultos de harina refinada"*, verifica
inventario real, ofrece alternativa cuando falta azúcar, arma el pedido y deja
traza. Costo: cero.

**Qué es y qué no es.** No es la inteligencia artificial: es una máquina de
estados con reglas que llama a las mismas herramientas. La conversación va sobre
rieles — si el cliente se sale del guion, se atora. Lo que sí es idéntico es todo
lo de abajo: catálogo, inventario, plan comercial, pedido, auditoría.

Sirve para vender la mecánica. La conversación libre se enseña ya con la llave
puesta.

## Cuánto cuesta operarlo

```bash
python scripts/costo.py 8 500
```

Con una llamada de 8 turnos, tarifa de primera parte y caché de prompt activo:

| Modelo | Por llamada | 500 llamadas/mes |
|---|---|---|
| Opus 5 | $0.156 | $77.93 |
| Sonnet 5 | $0.095 | $47.43 |
| Haiku 4.5 | $0.030 | $15.25 |

El carril rápido es el 2.2% del total. No es ahí donde está el gasto.

No incluye telefonía (número, minutos, transcripción, voz) — esos precios se
toman de la página vigente de Twilio porque varían por país.

Para conversar hace falta poner `ANTHROPIC_API_KEY` en `.env`. Después:

```bash
python scripts/demo_llamada.py
```

O interactivo, escribiendo tú:

```bash
python src/agente/canales/texto.py +523311112222
```

---

## La regla que sostiene todo

**El modelo nunca inventa un dato.** Solo hace tres cosas: entender, llamar
herramientas y hablar. Cada existencia, precio y fecha sale de una consulta
determinista. Si una herramienta falla, el agente dice "déjeme confirmarlo y le
marco" — no adivina.

Esa sola regla es la diferencia entre una demo bonita y algo que puedes poner
frente a tus clientes.

---

## Cómo está armado

```
Canales      voz · whatsapp · texto        canales/
   ↓
Cerebro      turno con Claude + tools      cerebro.py
   ↓
Herramientas 9 operaciones deterministas   herramientas.py
   ↓
Núcleo       catálogo · inventario · pedidos
   ↓
Adaptador    un archivo por ERP            erp/
   ↓
ERP del cliente
```

| Archivo | Qué resuelve |
|---|---|
| [catalogo.py](src/agente/catalogo.py) | De *"mándame 20 bultos de la de siempre"* al SKU del ERP |
| [inventario.py](src/agente/inventario.py) | Disponible real y reservas suaves con vencimiento |
| [pedidos.py](src/agente/pedidos.py) | Borrador local → aprobación → escritura idempotente al ERP |
| [herramientas.py](src/agente/herramientas.py) | Las 9 operaciones que el modelo puede invocar |
| [cerebro.py](src/agente/cerebro.py) | El turno conversacional, con streaming y caché de prompt |
| [erp/puerto.py](src/agente/erp/puerto.py) | El contrato que cumple cualquier ERP |
| [canales/voz.py](src/agente/canales/voz.py) | WebSocket de Twilio ConversationRelay |
| [config/giros/granos.yaml](config/giros/granos.yaml) | Todo lo específico del negocio |

---

## Las decisiones que importan

**Inventario espejo, no consulta en vivo.** Durante una llamada se consulta una
copia local que se sincroniza aparte. Un ERP lento no puede colgar una llamada.

**Disponible ≠ existencia.** Es `existencia − comprometido − reservas activas`.
Y si el pedido se come casi todo lo disponible, el agente no se compromete:
el inventario real nunca es exacto.

**Reserva suave.** Al anotar una partida se aparta el material con vencimiento
(30 min por defecto). Si el pedido no se cierra, se libera solo.

**El pedido se crea en dos tiempos.** Borrador local durante la llamada, commit
al ERP al final, con clave de idempotencia. Si se cae la llamada o el modelo se
equivoca, el ERP nunca se enteró. Un reintento por timeout no duplica.

**Humano en el circuito desde el día 1.** Con `REQUIERE_APROBACION_HUMANA=true`
(por defecto) todo pedido queda en `por_aprobar` y una persona lo suelta con un
clic. Se abre la escritura automática cuando la métrica de acierto lo justifique,
no antes. Nadie confía en que una IA escriba al ERP el primer día, y con razón.

**Ambigüedad se pregunta, no se adivina.** Si dos productos empatan, el agente
pregunta. `"azúcar"` con dos azúcares en catálogo es ambiguo aunque sea alias
exacto de uno de ellos.

**Trazabilidad de origen.** Cada partida guarda la frase que la originó y, en
voz, el milisegundo del audio. Cuando el cliente reclame *"yo pedí 200, no 100"*,
se abre el renglón y suena el audio exacto.

**El catálogo aprende.** Cada término que un cliente usa y el catálogo no
entiende queda en `alias_pendientes`. Se revisan, se agregan como alias, y la
siguiente llamada ya lo entiende.

**Nunca se contesta solo "no hay".** Cuando falta material,
`inventario.plan_comercial()` arma la respuesta completa: cuánto sí hay hoy,
cuándo entra el resto (compras en tránsito y producción programada), y qué
sustituto sirve — priorizando el que ese cliente **ya compra**, porque una
alternativa que ya usó no hay que venderla. El orden lo calcula el sistema; el
modelo solo lo redacta.

```
Cliente pide 500 kg de azúcar refinada, solo hay 150:
  1. sustituto           azúcar estándar cubre la cantidad completa hoy,
                         y este cliente ya lo ha comprado antes
  2. completo_diferido   el pedido completo se surte desde el 21 de agosto
                         (compra confirmada)
  3. parcial_hoy         se pueden surtir 150 kg de inmediato
```

---

## Dos modelos, en paralelo — nunca en cadena

Hay dos carriles corriendo al mismo tiempo sobre el mismo turno:

| Carril | Modelo | Qué hace | Puede equivocarse en |
|---|---|---|---|
| **Rápido** | Haiku 4.5 | Una frase de acuse: *"Va, déjeme checar la harina"* | Nada. No tiene herramientas ni ve el inventario, y tiene prohibido decir cualquier dato |
| **Pesado** | Opus 5 | El trabajo real: herramientas, inventario, pedido | Todo lo que importa — por eso es el bueno |

Arrancan **juntos**. Si fueran en cadena sumarían latencias (1.4–2.6 s de silencio
en vez de 0.8–2 s); en paralelo el rápido solo ocupa el silencio que de todos
modos iba a existir.

Reglas que hacen que no se estorben, verificadas en `scripts/probar_puente.py`:

- Si el pesado alcanza a hablar primero, **el puente se descarta**. Dos voces
  encimadas suenan a sistema roto, peor que el silencio.
- Si el carril rápido falla o se cae, la llamada sigue. A lo mucho hay silencio.
- Se apaga entero con `USAR_PUENTE=false`.

Costo del carril rápido: unos 50 tokens por turno en el modelo más barato.
Medio centavo de dólar por llamada de diez turnos.

## Que suene a persona

| Técnica | Dónde está |
|---|---|
| **Precarga por número entrante** — al primer timbrazo ya se sabe quién llama y qué compra | `voz.py:entrante` |
| **Carril rápido** — la frase de acuse sale mientras el modelo grande trabaja | `cerebro.py:_emitir_puente` |
| **Relleno fijo** — respaldo cuando el puente está apagado | `cerebro.py:RELLENOS` |
| **Interrupción** — si el cliente habla encima, la voz se corta al instante | `voz.py` evento `interrupt` |
| **Streaming al TTS** — el audio empieza antes de que termine la frase | `cerebro.py:responder` |
| **Esfuerzo bajo, no modelo bajo** — `effort: low` recorta latencia sin degradar el modelo | `config.py:esfuerzo` |
| **Marcar 0 siempre lleva a una persona** | `voz.py` evento `dtmf` |

Presupuesto objetivo: menos de 1 segundo de silencio antes de que el agente
empiece a hablar.

---

## Cambiar de proveedor de modelo

Un solo archivo habla con el modelo, asi que el proveedor es una variable de
entorno:

```bash
PROVEEDOR=claude   # claude | gemini | demo
```

| Proveedor | Archivo | Cuando |
|---|---|---|
| `claude` | `cerebro.py` | Opus 5 + Haiku 4.5 de puente. El de produccion |
| `gemini` | `cerebro_gemini.py` | Gemini Flash. Mas barato, tiene tier gratis |
| `demo` | `cerebro_demo.py` | Reglas, sin modelo. Costo cero |

Las tres implementaciones cumplen el mismo contrato (`responder`, `saludo`,
`texto_relleno`) y usan **las mismas 9 herramientas**: `cerebro_gemini.py`
traduce `herramientas.DEFINICIONES` al formato de Gemini en vez de mantener una
segunda copia, para que los proveedores no se desincronicen.

### Sobre el tier gratis de Gemini

Sirve para desarrollar, **no para demostrar ni para produccion**:

- Los modelos Flash buenos dan ~20 peticiones al dia. Una llamada de 8 turnos
  consume 16. Alcanza para **una llamada diaria**.
- Flash-Lite da 500/dia (~30 llamadas) pero es el modelo mas chico.
- **El tier gratis usa los datos para entrenar.** Con nombres, telefonos,
  creditos y pedidos de clientes reales, eso no es opcion. Para datos de
  clientes hay que estar en el tier de paga.

## Panel de control

La API que consume la interfaz web:

```bash
uvicorn agente.canales.panel:app --port 8080 --reload
```

| Endpoint | Devuelve |
|---|---|
| `GET /api/bandeja` | Pedidos por aprobar con partidas, credito y banderas de riesgo |
| `POST /api/pedidos/{folio}/aprobar` | Aprueba y escribe al ERP |
| `POST /api/pedidos/{folio}/rechazar` | Cancela y libera reservas |
| `GET /api/conversaciones/{id}` | Transcripcion con cada partida enlazada a su frase |
| `GET /api/metricas?periodo=hoy` | Todo el tablero en una llamada |
| `GET /api/catalogo/salud` | Productos y que tan bien se entienden |
| `POST /api/catalogo/alias` | Ensena un termino nuevo al catalogo |
| `GET /api/inventario` | Existencias, apartados y entradas programadas |

Documentacion viva en `http://localhost:8080/docs`.

El prompt para la IA de diseno esta en [docs/prompt-diseno.md](docs/prompt-diseno.md).

### Las metricas que importan

**Tasa de acierto** — porcentaje de pedidos aprobados sin correccion. Es la que
decide cuando se le suelta al agente la escritura automatica al ERP. Umbral: 95%
con al menos 30 pedidos revisados.

**Venta en riesgo** — lo que los clientes pidieron y no habia, valuado en pesos.
Sale de la traza, sin instrumentar nada aparte. Es el argumento de compra mas
fuerte del producto: le pone precio a un problema que la empresa ya tenia y no
medía.

**Lo que no se entendio** — terminos que el catalogo no reconocio, con un boton
para asignarlos. El ciclo se cierra solo: no entendio, quedo anotado, alguien lo
asigno, la siguiente llamada ya lo entiende.

## Conectar un ERP real

Se implementa [`PuertoERP`](src/agente/erp/puerto.py) — ocho operaciones — y se
registra en `erp/__init__.py`. Nada más del sistema se entera de qué ERP hay
detrás.

```python
class ERPOdoo(PuertoERP):
    nombre = "odoo"

    def sincronizar_existencias(self) -> list[dict]:
        ...  # XML-RPC, SQL, CSV por SFTP, lo que ese ERP permita
```

Orden de preferencia para conectar, de mejor a peor:

1. API oficial (REST/SOAP/XML-RPC)
2. Réplica de lectura de la base + escritura por API
3. Archivos por SFTP (CSV/EDI) — muy común en ERPs mexicanos
4. RPA / navegador headless — último recurso
5. Sin ERP: el sistema mismo es el registro

---

## Adaptar a otro giro

Se copia `config/giros/granos.yaml`, se cambia el contenido, y se apunta
`GIRO=` en el `.env`. Ahí viven unidades, sinónimos, guion, mínimos, políticas
de crédito, qué puede prometer el agente y cuándo escalar. **El motor no cambia.**

---

## Voz en producción

```bash
uvicorn agente.canales.voz:app --host 0.0.0.0 --port 8080
```

El número de Twilio apunta a `POST /voz/entrante`, y `URL_WEBSOCKET_VOZ` en el
`.env` apunta a `wss://tu-dominio/voz/flujo`.

Endpoints de operación:

| Ruta | Para qué |
|---|---|
| `GET /salud` | Sonda de monitoreo y pedidos pendientes |
| `GET /pedidos/por-aprobar` | Bandeja de revisión humana |
| `POST /pedidos/{folio}/aprobar` | Aprueba y escribe al ERP |
| `POST /pedidos/{folio}/rechazar` | Cancela y libera reservas |

---

## Estado actual

Funcionando y verificado:

- Catálogo, unidades, inventario, reservas, pedidos, idempotencia y traza —
  cubierto por `scripts/probar_nucleo.py`, todo en verde
- Adaptador de ERP simulado, con el contrato listo para uno real
- Canal de texto y servidor de voz completos

Sin ejercitar todavía:

- El turno con Claude, por falta de `ANTHROPIC_API_KEY` en el equipo. El código
  está escrito y compila; falta correrlo contra la API.
- El canal de voz contra Twilio real. Necesita cuenta, número y URL pública.

Lo que sigue, en orden:

1. Poner la API key y correr `demo_llamada.py`
2. Cargar el catálogo real de la empresa (reemplazar `data/seed/`) y medir cuántas
   frases reales resuelve bien
3. Twilio + un número + túnel, y hacer la primera llamada de verdad
4. Bandeja de aprobación con interfaz, no solo API
5. Adaptador del ERP real, cuando se defina cuál
