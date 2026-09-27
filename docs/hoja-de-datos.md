# Hoja de datos del proyecto

Para quien escriba sobre esto. Todo lo de abajo es verificable corriendo el
código; nada es estimación ni promesa.

Repositorio: https://github.com/jesusjuarez6280-droid/agente-ventas

---

## Qué es, en una frase

Un agente que contesta llamadas telefónicas, entiende el pedido como lo dice el
cliente, lo verifica contra el inventario real y lo registra en el ERP.

## Cómo verlo funcionar en un minuto

```bash
git clone https://github.com/jesusjuarez6280-droid/agente-ventas
cd agente-ventas
pip install -r requirements.txt
python scripts/init_db.py --reset
python scripts/demo_sin_api.py
```

**Sin llave de API, sin cuenta, sin costo.** Eso es deliberado: cualquiera puede
verlo funcionar sin pedir nada ni gastar nada.

---

## Hechos verificables

### El problema que resuelve

No es "una IA que habla". Son dos problemas concretos:

1. **Traducir cómo habla el cliente al catálogo del ERP.** El cliente dice
   *"mándame 20 bultos de la de siempre"*; el ERP espera `HAR-TRG-REF, 1000 kg`.
2. **Que el inventario sea confiable.** Prometer material que no existe destruye
   la relación con el cliente en una sola llamada.

### Decisiones de diseño

| Decisión | Por qué |
|---|---|
| El LLM nunca produce un dato | Solo entiende, llama herramientas y habla. Existencias, precios y fechas salen de consultas deterministas |
| Inventario espejo, no consulta en vivo al ERP | Un ERP lento no puede colgar una llamada |
| El pedido se arma local y se escribe al ERP al final | Si la llamada se cae, el ERP nunca se enteró |
| La ambigüedad se pregunta, no se adivina | `"azúcar"` con dos azúcares en catálogo es ambiguo aunque sea alias exacto de uno |
| Aprobación humana por defecto | La escritura automática se abre por métrica medida, no por confianza |
| Proveedor de modelo intercambiable | Un solo archivo habla con el modelo. Claude, Gemini o reglas, por variable de entorno |

### Números medidos

Latencia por turno con herramientas, medida el 2026-09-26 contra la API real:

```
gemini-flash-lite-latest       798 ms
gemini-3.5-flash-lite        1,021 ms   ← el que usa
gemini-3.1-flash-lite        1,137 ms
gemini-3.8-flash             1,385 ms
gemini-3.5-flash            20,059 ms   ← descartado por lento
```

Costo por llamada de 8 turnos, con caché de prompt:

```
Claude Opus 5      $0.156
Claude Sonnet 5    $0.095
Claude Haiku 4.5   $0.030
```

Cobertura de pruebas: 34 verificaciones del núcleo + 13 de los hallazgos de
auditoría, todas en verde. Corren sin llave de API.

### La auditoría

El proyecto se sometió a una auditoría de seguridad externa que encontró 15
hallazgos. Los críticos están corregidos, **con pruebas que reproducen el
escenario original y demuestran que ya no ocurre**:

- Carrera al reservar inventario (probada con hilos reales y barrera de
  sincronización)
- Idempotencia de la escritura al ERP (probada simulando una caída del proceso
  entre la respuesta del ERP y el guardado local)
- Doble venta por reserva vencida mientras el pedido esperaba aprobación
- Ausencia total de control de acceso en el panel
- Fuga de datos entre clientes distintos en las métricas

```bash
python scripts/probar_auditoria.py
```

### Detalle que suele llamar la atención

Cada renglón del pedido guarda **la frase exacta del cliente que lo originó** y,
en llamadas de voz, el milisegundo del audio. Cuando un cliente reclama *"yo
pedí doscientos, no cien"*, se abre el renglón y suena su propia voz.

---

## Qué NO se puede afirmar de este proyecto

Para no exagerar:

- **No está en producción.** Es un sistema completo y probado, no un despliegue
  con tráfico real.
- **No se ha probado con llamadas telefónicas reales.** El canal de voz
  (Twilio ConversationRelay) está implementado pero requiere cuenta y número.
- **No se ha medido con carga concurrente.** La base es SQLite; para varios
  clientes simultáneos haría falta Postgres.

Pendientes documentados y conocidos: dinero en `float` en lugar de `Decimal`,
verificación de que lo que el modelo *dice* coincide con lo que las herramientas
devolvieron, y firma de los webhooks de telefonía.

---

## Capturas

Para sacarlas:

```bash
python scripts/init_db.py --reset
python scripts/crear_usuario.py demo "demostracion2026" revisor
python scripts/demo_sin_api.py
python -m uvicorn agente.canales.panel:app --port 8080 --app-dir src
```

Abrir `http://localhost:8080`, entrar con `demo` / `demostracion2026`.

Lo que vale la pena capturar:

1. **La bandeja de aprobación** con los pedidos y el detalle abierto: se ve la
   columna *"Lo pidió así"* con las palabras del cliente junto a la cantidad ya
   convertida a kilos.
2. **La salida de `demo_sin_api.py`** en la terminal: la conversación completa
   con el momento en que no hay azúcar refinada y ofrece la estándar.
3. **La salida de `probar_auditoria.py`**: la lista de hallazgos cerrados.

## Perfil técnico que demuestra

Python, FastAPI, WebSockets, SQLite/SQL, integración con APIs de LLM (Anthropic
y Google), diseño de esquemas relacionales, transacciones y concurrencia,
autenticación y control de acceso por roles, y corrección de hallazgos de
seguridad con pruebas de regresión.
