"""
Exporta la cartera consolidada de un delegado a JSON para la Vista de Grupo
(scripts/generar_vista_grupo.py). Antes esto se hacía con snippets sueltos no
versionados -- este script es la fuente reproducible.

Uso: python scripts/exportar_cartera_grupo.py ["NOMBRE DELEGADO"] [ruta_salida.json]

Nota sobre "objetivo del pacto" (spec sección 5 y 15-16): el objetivo real de
Pacto ADA/Dexeryl sale de la Ficha Cliente 2026, que solo tenemos para 2
clientes de ejemplo, no para toda la cartera. Por eso este export NO calcula
ni inventa un objetivo por cliente -- la spec es explícita: "Si no hay pacto
oficial de una farmacia: indicar 'Objetivo de pacto individual no disponible'
(nunca sustituir silenciosamente)". Lo que sí exportamos es el desglose real
por marca (Avène, Ducray, A-Derma, Dexeryl), que viene directo del LOB.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from src.engine.comparacion import ResumenCliente, cartera_delegado
from src.parsers.acuerdos_parser import objetivos_por_pos_id, parse_acuerdos
from src.parsers.lob_parser import MARCAS_ADA, parse_lob

MARCAS_EXPORT = MARCAS_ADA + ["dexeryl"]
NOMBRE_MARCA = {
    "avene_sin_solar": "Avène (sin solar)",
    "avene_solar": "Avène Solar",
    "ducray": "Ducray",
    "aderma": "A-Derma",
    "dexeryl": "Dexeryl",
}


def _fila(resumen: ResumenCliente, idx: int) -> dict:
    c = resumen.cliente
    marcas = {}
    for m in MARCAS_EXPORT:
        medida = c.marcas.get(m)
        if medida and medida.estado == "OK":
            marcas[m] = {"nombre": NOMBRE_MARCA[m], "ytd1": medida.importe_neto_ytd1, "ytd": medida.importe_neto_ytd}
        else:
            marcas[m] = {"nombre": NOMBRE_MARCA[m], "ytd1": None, "ytd": None}

    return {
        "id": idx,
        "pos_ids": c.pos_ids,
        "nombre": c.nombre_cliente,
        "poblacion": c.poblacion,
        "grupo": c.grupo_compra,
        "n_pos": len(c.pos_ids),
        "ada_ytd": resumen.pacto_ada.ytd,
        "ada_ytd1": resumen.pacto_ada.ytd1,
        "ada_evol": resumen.pacto_ada.evolucion_pct,
        "ada_estado": resumen.pacto_ada.estado,
        "ada_objetivo": resumen.pacto_ada.objetivo,
        "ada_pct_cumplimiento": resumen.pacto_ada.pct_cumplimiento,
        "ada_gap": resumen.pacto_ada.gap,
        "dex_ytd": resumen.pacto_dexeryl.ytd,
        "dex_ytd1": resumen.pacto_dexeryl.ytd1,
        "dex_evol": resumen.pacto_dexeryl.evolucion_pct,
        "dex_estado": resumen.pacto_dexeryl.estado,
        "dex_objetivo": resumen.pacto_dexeryl.objetivo,
        "dex_pct_cumplimiento": resumen.pacto_dexeryl.pct_cumplimiento,
        "dex_gap": resumen.pacto_dexeryl.gap,
        "perdido_ada": resumen.perdida_ada is not None,
        "perdido_dex": resumen.perdida_dexeryl is not None,
        "perdida_ada_valor": resumen.perdida_ada.facturacion_perdida if resumen.perdida_ada else 0,
        "perdida_dex_valor": resumen.perdida_dexeryl.facturacion_perdida if resumen.perdida_dexeryl else 0,
        "perdida_ada_marcas": (
            [{"marca": NOMBRE_MARCA[m], "valor": v} for m, v in resumen.perdida_ada.por_marca.items()]
            if resumen.perdida_ada
            else []
        ),
        "marcas": marcas,
    }


def main() -> None:
    delegado = sys.argv[1] if len(sys.argv) > 1 else "LAURA LUQUIN FRANQUET"
    salida = sys.argv[2] if len(sys.argv) > 2 else "/tmp/cartera_laura_consolidada.json"

    clientes = parse_lob("docs/lob_compar/Listado_LOB_03_08_26.csv")
    acuerdos = parse_acuerdos("docs/acuerdos_comerciales/Listado_Acuerdos_Comerciales_LIVE.csv")
    objetivos = objetivos_por_pos_id(acuerdos)
    cartera = cartera_delegado(clientes, delegado, consolidar=True, objetivos_por_pos=objetivos)

    data = [_fila(r, i) for i, r in enumerate(cartera)]
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"OK: {len(data)} farmacias consolidadas exportadas a {salida}")


if __name__ == "__main__":
    main()
