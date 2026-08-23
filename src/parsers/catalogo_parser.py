"""
Parser de la tarifa/catálogo del ciclo 3 (docs/catalogo/tarifa_ciclo_3_raw.tsv).

Transcrita a mano por el usuario desde el Numbers original (exportar a CSV/PDF no funcionaba
bien en el iPad para este fichero) -- ver docs/catalogo/tarifa_ciclo_3_raw.tsv. 358 productos
reales de Avène, Ducray, A-Derma y Dexeryl (nunca Klorane -- CLAUDE.md).

Nota sobre el CN: la columna "Código Nacional" no siempre es un CN puro -- algunas filas son
packs/promos con sufijo de letra (ej. "356709.1P") o vienen vacías (packs-regalo sin CN propio,
identificados solo por "Codigo Articulo" tipo P00xxxxx). Se extrae la parte numérica inicial como
CN cuando existe; si no hay CN numérico, el producto se conserva igualmente indexado por su
Código Articulo, nunca se descarta ni se inventa un CN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class Producto:
    cn: int | None
    codigo_articulo: str
    descripcion: str
    formato: str
    pvl: float | None
    pvp_recomendado: float | None
    tipo_iva: str
    es_heroe: bool
    gama: str
    marca: str
    tipo_pedido: str  # DIRECTO | CAMPAÑA


def _extraer_cn(valor: str | float | None) -> int | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or not str(valor).strip():
        return None
    m = re.match(r"^(\d+)", str(valor).strip())
    return int(m.group(1)) if m else None


def _to_num(valor: str | float | None) -> float | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or not str(valor).strip():
        return None
    try:
        return float(str(valor).strip().replace(",", "."))
    except ValueError:
        return None


MARCA_CANONICA = {
    "AV-AVENE": "Avène",
    "DU-DUCRAY": "Ducray",
    "AD-A-DERMA": "A-Derma",
    "DEXERYL": "Dexeryl",
}


def parse_catalogo(path: str | Path) -> list[Producto]:
    df = pd.read_csv(path, sep="\t", dtype=str)
    productos = []
    for _, row in df.iterrows():
        productos.append(
            Producto(
                cn=_extraer_cn(row["Código Nacional"]),
                codigo_articulo=str(row["Codigo Articulo"]).strip(),
                descripcion=str(row["Descripción"]).strip(),
                formato=str(row["Formato"]).strip() if pd.notna(row["Formato"]) else "",
                pvl=_to_num(row["PVL sin IVA 2026"]),
                pvp_recomendado=_to_num(row["PVP IVA Recomendado 2026"]),
                tipo_iva=str(row["TIPO DE IVA"]).strip(),
                es_heroe=str(row.get("HEROE & BEST SELLER", "")).strip() != "" and pd.notna(row.get("HEROE & BEST SELLER")),
                gama=str(row["Nombre Gama España"]).strip() if pd.notna(row["Nombre Gama España"]) else "",
                marca=MARCA_CANONICA.get(str(row["MARCA"]).strip(), str(row["MARCA"]).strip()),
                tipo_pedido=str(row["TIPO DE PEDIDO FARMACIA"]).strip(),
            )
        )
    return productos


def indice_por_cn(productos: list[Producto]) -> dict[int, Producto]:
    """Cuando hay CN duplicado (ej. mismo producto en DIRECTO y CAMPAÑA), se queda el de menor PVL
    (la condición de campaña, que es la vigente para pedir en promoción)."""
    idx: dict[int, Producto] = {}
    for p in productos:
        if p.cn is None:
            continue
        if p.cn not in idx or (p.pvl is not None and (idx[p.cn].pvl is None or p.pvl < idx[p.cn].pvl)):
            idx[p.cn] = p
    return idx


if __name__ == "__main__":
    productos = parse_catalogo("docs/catalogo/tarifa_ciclo_3_raw.tsv")
    print(f"Productos parseados: {len(productos)}")
    con_cn = sum(1 for p in productos if p.cn is not None)
    print(f"Con CN numérico: {con_cn} / {len(productos)}")
    idx = indice_por_cn(productos)
    print(f"CN únicos indexados: {len(idx)}")
    heroes = [p for p in productos if p.es_heroe]
    print(f"Héroes/Best sellers: {len(heroes)}")
    ejemplo = idx.get(170675)
    print("\nEjemplo (CN 170675, Exomega Crema Emoliente):", ejemplo)
