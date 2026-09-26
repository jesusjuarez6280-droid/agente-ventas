"""Prueba el nucleo sin gastar un solo token de modelo.

Ejercita exactamente lo que las herramientas del agente ejecutan por debajo:
busqueda de catalogo, conversion de unidades, disponibilidad real, reservas y
armado del pedido. Si esto no pasa, no tiene caso encender la voz.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agente import auditoria, catalogo, inventario, pedidos  # noqa: E402
from agente.herramientas import Sesion, ejecutar  # noqa: E402
from agente.unidades import a_unidad_base, describir  # noqa: E402

VERDE, ROJO, GRIS, FIN = "\033[92m", "\033[91m", "\033[90m", "\033[0m"
fallos = 0


def check(titulo: str, condicion: bool, detalle: str = "") -> None:
    global fallos
    marca = f"{VERDE}OK  {FIN}" if condicion else f"{ROJO}FALLA{FIN}"
    if not condicion:
        fallos += 1
    print(f"  {marca} {titulo}")
    if detalle:
        print(f"       {GRIS}{detalle}{FIN}")


def seccion(titulo: str) -> None:
    print(f"\n{titulo}\n{'-' * len(titulo)}")


# --------------------------------------------------------------------------
seccion("1. Catalogo: de como habla el cliente al SKU")

casos = [
    ("harina blanca", "HAR-TRG-REF"),
    ("la de siempre", "HAR-TRG-REF"),
    ("maseca", "HAR-MAI-NIX"),
    ("frijol", "FRJ-NEG-1RA"),
    ("arroz morelos", "ARR-SUP-MOR"),
    ("azucar estandar", "AZU-EST-STD"),
]
for frase, esperado in casos:
    r = catalogo.buscar(frase)
    sku = r.mejor.sku if r.mejor else None
    check(
        f'"{frase}" -> {sku}',
        sku == esperado,
        f"esperado {esperado}, confianza {r.mejor.score if r.mejor else 0}"
        + (", AMBIGUO -> el agente pregunta" if r.ambiguo else ""),
    )

r = catalogo.buscar("azucar")
check(
    '"azucar" se detecta ambiguo (estandar vs refinada)',
    r.ambiguo or len(r.candidatos) > 1,
    f"candidatos: {[c.sku for c in r.candidatos]}, ambiguo={r.ambiguo}",
)

r = catalogo.buscar("tornillos galvanizados")
check("producto inexistente no devuelve nada", not r.candidatos,
      "y queda anotado en alias_pendientes para revision")

# --------------------------------------------------------------------------
seccion("2. Unidades: bultos y tarimas a kilos")

for cantidad, unidad, esperado in [(40, "bultos", 2000), (1, "tarima", 2000),
                                   (500, "kilos", 500), (3, "bulto", 150)]:
    kg, err = a_unidad_base(cantidad, unidad, "kilo:1;bulto:50;tarima:2000")
    check(f"{cantidad} {unidad} = {kg:,.0f} kg", kg == esperado and not err, err or "")

kg, err = a_unidad_base(5, "guacaladas", "bulto:50")
check("unidad desconocida devuelve error, no adivina", bool(err), err or "")

check("describir(2000) suena a persona", "tarima" in describir(2000, "bulto:50;tarima:2000"),
      describir(2000, "bulto:50;tarima:2000"))

# --------------------------------------------------------------------------
seccion("3. Inventario: disponible real, no existencia bruta")

d = inventario.disponibilidad("HAR-TRG-REF", 2000)
check("harina refinada: alcanzan 2,000 kg", d.alcanza,
      f"existencia {d.existencia_kg:,.0f} - comprometido {d.comprometido_kg:,.0f}"
      f" = disponible {d.disponible_kg:,.0f} kg")

d = inventario.disponibilidad("AZU-REF-EXT", 500)
check("azucar refinada: NO alcanzan 500 kg", not d.alcanza, d.nota)

d = inventario.disponibilidad("MAN-VEG-HID", 20)
check("manteca: alcanza pero no es prometible (queda al limite)",
      d.alcanza and not d.prometible, d.nota)

alts = inventario.alternativas("AZU-REF-EXT", 500)
check("hay alternativa que ofrecer para el azucar", bool(alts),
      ", ".join(a["nombre_corto"] for a in alts) or "ninguna")

# --------------------------------------------------------------------------
seccion("4. Pedido completo: el caso de Alimentos del Valle")

conv = auditoria.abrir_conversacion("prueba", "+523311112222", "C-0001")
sesion = Sesion(conversacion_id=conv, canal="prueba", telefono="+523311112222")

datos = ejecutar(sesion, "identificar_cliente", {"telefono": "+523311112222"})
check("se identifica a Alimentos del Valle por su numero", datos.get("nombre") == "Alimentos del Valle",
      f"credito disponible ${datos.get('credito_disponible', 0):,.2f}")
check("trae sus productos frecuentes", bool(datos.get("productos_frecuentes")),
      ", ".join(p["producto"] for p in datos.get("productos_frecuentes", [])))

datos = ejecutar(sesion, "buscar_producto", {"descripcion": "lo de siempre"})
check('"lo de siempre" se resuelve por historial',
      datos.get("resuelto_por") == "historial",
      f"candidatos: {[c['sku'] for c in datos.get('candidatos', [])]}")

datos = ejecutar(sesion, "consultar_disponibilidad",
                 {"sku": "HAR-TRG-REF", "cantidad": 40, "unidad": "bultos"})
check("40 bultos de harina: hay y es seguro prometerlo",
      datos.get("alcanza") and datos.get("seguro_prometer"),
      f"solicitado {datos.get('solicitado')}, disponible {datos.get('disponible_hoy')}")

datos = ejecutar(sesion, "agregar_al_pedido",
                 {"sku": "HAR-TRG-REF", "cantidad": 40, "unidad": "bultos",
                  "frase_origen": "mandame 40 bultos de la de siempre"})
check("se agrega la partida y se aparta el material", datos.get("ok"), datos.get("mensaje", ""))

datos = ejecutar(sesion, "agregar_al_pedido",
                 {"sku": "AZU-REF-EXT", "cantidad": 500, "unidad": "kilos"})
check("azucar refinada se rechaza por falta de existencia", not datos.get("ok"),
      datos.get("mensaje", ""))
check("y el rechazo trae alternativas para ofrecer",
      bool(datos.get("alternativas")),
      ", ".join(a["nombre_corto"] for a in datos.get("alternativas", [])))

datos = ejecutar(sesion, "agregar_al_pedido",
                 {"sku": "AZU-EST-STD", "cantidad": 1000, "unidad": "kilos"})
check("azucar estandar si entra", datos.get("ok"), datos.get("mensaje", ""))

datos = ejecutar(sesion, "leer_pedido", {})
check("el pedido tiene 2 partidas", len(datos.get("partidas", [])) == 2,
      f"total ${datos.get('total', 0):,.2f}, "
      f"credito alcanza: {datos.get('credito', {}).get('alcanza')}")

datos = ejecutar(sesion, "cerrar_pedido", {"fecha_entrega": "2026-08-21"})
check("el pedido cierra en revision humana, no directo al ERP",
      datos.get("estado") == "por_aprobar", datos.get("mensaje", ""))

# --------------------------------------------------------------------------
seccion("5. Reserva: lo apartado deja de estar disponible")

antes = inventario.disponibilidad("HAR-TRG-REF").disponible_kg
folio2 = pedidos.abrir("C-0002", "prueba")
pedidos.agregar_partida(folio2, "HAR-TRG-REF", 10, "bultos")
despues = inventario.disponibilidad("HAR-TRG-REF").disponible_kg
check("apartar 500 kg reduce el disponible", antes - despues == 500,
      f"{antes:,.0f} -> {despues:,.0f} kg")

pedidos.cancelar(folio2, "prueba")
liberado = inventario.disponibilidad("HAR-TRG-REF").disponible_kg
check("cancelar devuelve el material al piso", liberado == antes,
      f"{despues:,.0f} -> {liberado:,.0f} kg")

# --------------------------------------------------------------------------
seccion("6. Escritura al ERP: idempotente")

folio3 = pedidos.abrir("C-0004", "prueba")
pedidos.agregar_partida(folio3, "HAR-MAI-NIX", 200, "kilos")
pedidos.cerrar(folio3)
from agente import db  # noqa: E402

with db.tx() as cx:
    cx.execute("UPDATE pedidos SET estado = 'confirmado' WHERE folio = ?", (folio3,))

r1 = pedidos.escribir_en_erp(folio3)
r2 = pedidos.escribir_en_erp(folio3)
check("se escribe al ERP con folio", r1.get("ok") and r1.get("folio_erp"),
      f"folio ERP: {r1.get('folio_erp')}")
check("reintentar NO duplica el pedido", r2.get("folio_erp") == r1.get("folio_erp"),
      r2.get("mensaje", ""))

# --------------------------------------------------------------------------
seccion("7. Traza: queda registro de todo")

turnos = auditoria.transcripcion(conv)
check("la conversacion dejo traza completa", len(turnos) >= 7,
      f"{len(turnos)} turnos registrados con entrada, salida y latencia")

partidas = db.consultar(
    "SELECT frase_origen, turno_id FROM partidas WHERE folio = ? AND frase_origen IS NOT NULL",
    (sesion.folio,),
)
check("cada partida sabe que frase la origino", bool(partidas),
      partidas[0]["frase_origen"] if partidas else "")

# --------------------------------------------------------------------------
seccion("8. Plan comercial: que vender hoy y que se podra tener")

plan = inventario.plan_comercial("AZU-REF-EXT", 500, "C-0001")
tipos = [o["tipo"] for o in plan["opciones"]]

check("cuando no alcanza, no devuelve solo un 'no hay'", len(plan["opciones"]) >= 3,
      f"opciones: {tipos}")
check("ofrece lo que si hay hoy", "parcial_hoy" in tipos,
      next((o["detalle"] for o in plan["opciones"] if o["tipo"] == "parcial_hoy"), ""))
check("dice cuando se completa con lo que viene en camino",
      "completo_diferido" in tipos,
      next((o["detalle"] for o in plan["opciones"] if o["tipo"] == "completo_diferido"), ""))
check("prioriza el sustituto que este cliente YA compra",
      plan["opciones"][0]["tipo"] == "sustituto"
      and plan["opciones"][0].get("ya_lo_compra") is True,
      plan["opciones"][0]["detalle"])

# El mismo producto para un cliente que nunca compro el sustituto: el
# sustituto sigue apareciendo, pero ya no encabeza por familiaridad.
plan_ajeno = inventario.plan_comercial("AZU-REF-EXT", 500, "C-0004")
sustituto = next((o for o in plan_ajeno["opciones"] if o["tipo"] == "sustituto"), None)
check("para un cliente que no lo compra, el sustituto no se marca como conocido",
      sustituto is not None and not sustituto.get("ya_lo_compra"),
      "misma opcion, distinta fuerza de venta")

plan_ok = inventario.plan_comercial("HAR-TRG-REF", 2000, "C-0001")
check("cuando si alcanza, la recomendacion es surtir directo",
      plan_ok["recomendacion"] == "surtir_completo", plan_ok["recomendacion"])

plan_justo = inventario.plan_comercial("MAN-VEG-HID", 20, "C-0001")
check("cuando queda al limite, pide confirmar con almacen",
      plan_justo["recomendacion"] == "surtir_confirmando_con_almacen",
      plan_justo.get("nota", ""))

# --------------------------------------------------------------------------
print()
if fallos:
    print(f"{ROJO}{fallos} verificacion(es) fallaron.{FIN}")
    sys.exit(1)
print(f"{VERDE}Nucleo completo funcionando.{FIN} Listo para conectarle la voz.")
