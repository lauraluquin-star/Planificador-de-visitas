"""
Genera el objeto JS `TARIFA_CN` (CN -> descripción/formato/PVL/héroe/marca/gama) embebido en las
fichas HTML, para el buscador "+ Añadir por CN": el usuario escribe un CN y la app rellena los
datos reales desde la tarifa, sin inventar nada -- si el CN no está aquí, no se añade.

Usa indice_por_cn (catalogo_parser.py), que ya resuelve los CN duplicados (mismo producto en
DIRECTO/CAMPAÑA o base/pack) quedándose con el de menor PVL -- la condición vigente para pedir.

Uso: python scripts/generar_tarifa_cn_js.py > /tmp/tarifa_cn.js
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parsers.catalogo_parser import indice_por_cn, parse_catalogo


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _titulo(desc: str) -> str:
    return desc.title() if desc.isupper() else desc


def generar_js(ruta_tarifa: str = "docs/catalogo/tarifa_ciclo_3_raw.tsv") -> str:
    productos = parse_catalogo(ruta_tarifa)
    idx = indice_por_cn(productos)
    entradas = []
    for cn in sorted(idx):
        p = idx[cn]
        if p.pvl is None:
            continue
        entradas.append(
            f'"{cn}":{{d:"{_esc(_titulo(p.descripcion))}",f:"{_esc(p.formato)}",'
            f'p:{p.pvl},h:{"true" if p.es_heroe else "false"},m:"{_esc(p.marca)}",g:"{_esc(p.gama)}"}}'
        )
    return "const TARIFA_CN = {\n  " + ",\n  ".join(entradas) + "\n};"


if __name__ == "__main__":
    print(generar_js())
