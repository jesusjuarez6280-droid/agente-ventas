"""Cuanto cuesta operar esto. Para poder cotizarlo sin adivinar.

Modela el gasto real de una llamada: cuantas veces se llama al modelo, cuanto
del prompt se paga a precio de cache y cuanto completo, y que aporta el carril
rapido.

    python scripts/costo.py                  # escenario por defecto
    python scripts/costo.py 8 500            # 8 turnos por llamada, 500 llamadas al mes

OJO CON LO QUE NO ESTA AQUI: la telefonia. El precio por minuto de Twilio
(numero, minutos de voz, transcripcion y sintesis) hay que tomarlo de su
pagina de precios vigente — cambia por pais y por proveedor de voz. Lo que
sigue es solo el costo del modelo.
"""
from __future__ import annotations

import sys

# Precios por millon de tokens (tarifa Anthropic de primera parte).
# Verificar en anthropic.com/pricing antes de cotizarle a un cliente.
PRECIOS = {
    "claude-opus-5":   {"entrada": 5.00, "salida": 25.00},
    "claude-sonnet-5": {"entrada": 3.00, "salida": 15.00},
    "claude-haiku-4-5": {"entrada": 1.00, "salida": 5.00},
}
FACTOR_LECTURA_CACHE = 0.10   # leer del cache cuesta ~10% del precio normal
FACTOR_ESCRITURA_CACHE = 1.25  # sembrarlo cuesta ~25% mas, una vez por llamada

# Perfil de la llamada, medido sobre este sistema.
PREFIJO_CACHEADO = 2800    # instrucciones + las 9 herramientas
CRECE_POR_TURNO = 250      # lo que suma al historial cada ida y vuelta
SALIDA_POR_LLAMADA_MODELO = 110
LLAMADAS_MODELO_POR_TURNO = 2  # una para decidir la consulta, otra para contestar

ENTRADA_PUENTE = 320       # instrucciones cortas + lo que dijo el cliente
SALIDA_PUENTE = 20         # una frase de ocho palabras


def costo_llamada(modelo: str, turnos: int, con_puente: bool = True) -> dict:
    p = PRECIOS[modelo]
    requests = turnos * LLAMADAS_MODELO_POR_TURNO

    # El prefijo se siembra una vez y se lee en cada request posterior.
    escritura = PREFIJO_CACHEADO * FACTOR_ESCRITURA_CACHE
    lectura = PREFIJO_CACHEADO * FACTOR_LECTURA_CACHE * (requests - 1)

    # El historial crece y no se cachea (cambia en cada turno).
    historial = sum(CRECE_POR_TURNO * (i // LLAMADAS_MODELO_POR_TURNO) for i in range(requests))

    entrada_total = escritura + lectura + historial
    salida_total = SALIDA_POR_LLAMADA_MODELO * requests

    costo = (entrada_total * p["entrada"] + salida_total * p["salida"]) / 1_000_000

    costo_puente = 0.0
    if con_puente:
        h = PRECIOS["claude-haiku-4-5"]
        costo_puente = (
            (ENTRADA_PUENTE * h["entrada"] + SALIDA_PUENTE * h["salida"]) * turnos
        ) / 1_000_000

    return {
        "modelo": modelo,
        "requests": requests,
        "tokens_entrada": int(entrada_total),
        "tokens_salida": int(salida_total),
        "costo_modelo": costo,
        "costo_puente": costo_puente,
        "total": costo + costo_puente,
    }


def main() -> None:
    turnos = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    llamadas_mes = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    print()
    print("=" * 74)
    print(f"  COSTO DEL MODELO   ·   llamada de {turnos} turnos   ·   {llamadas_mes:,} llamadas/mes")
    print("=" * 74)
    print()
    print(f"  {'Modelo':<18}{'por llamada':>14}{'al mes':>14}{'por 1000 llam.':>18}")
    print("  " + "-" * 62)

    for modelo in PRECIOS:
        if modelo == "claude-haiku-4-5":
            continue
        d = costo_llamada(modelo, turnos)
        print(
            f"  {modelo:<18}"
            f"{'$' + format(d['total'], '.3f'):>14}"
            f"{'$' + format(d['total'] * llamadas_mes, ',.2f'):>14}"
            f"{'$' + format(d['total'] * 1000, ',.2f'):>18}"
        )

    d = costo_llamada("claude-haiku-4-5", turnos, con_puente=False)
    print(
        f"  {'claude-haiku-4-5':<18}"
        f"{'$' + format(d['total'], '.3f'):>14}"
        f"{'$' + format(d['total'] * llamadas_mes, ',.2f'):>14}"
        f"{'$' + format(d['total'] * 1000, ',.2f'):>18}"
        "   <- solo para demos"
    )

    d = costo_llamada("claude-opus-5", turnos)
    print()
    print("  Desglose de una llamada con Opus 5")
    print("  " + "-" * 62)
    print(f"    llamadas al modelo         {d['requests']:>10}")
    print(f"    tokens de entrada          {d['tokens_entrada']:>10,}   (la mayoria a precio de cache)")
    print(f"    tokens de salida           {d['tokens_salida']:>10,}")
    print(f"    costo del modelo pesado    {'$' + format(d['costo_modelo'], '.4f'):>10}")
    print(f"    costo del carril rapido    {'$' + format(d['costo_puente'], '.4f'):>10}   ({d['costo_puente']/d['total']*100:.1f}% del total)")
    print(f"    {'TOTAL':<26}{'$' + format(d['total'], '.4f'):>10}")

    print()
    print("  Cuanto rinden unos primeros creditos de prueba")
    print("  " + "-" * 62)
    for credito in (5, 10, 25):
        for modelo in ("claude-opus-5", "claude-haiku-4-5"):
            d = costo_llamada(modelo, turnos, con_puente=(modelo != "claude-haiku-4-5"))
            print(f"    ${credito:>3} con {modelo:<20} {int(credito / d['total']):>6,} llamadas de demo")

    print()
    print("  NO INCLUIDO: telefonia (numero, minutos, transcripcion, voz).")
    print("  Tomar esos precios de la pagina vigente de Twilio — varian por pais.")
    print("=" * 74)
    print()


if __name__ == "__main__":
    main()
