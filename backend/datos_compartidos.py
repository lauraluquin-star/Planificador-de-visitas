"""
Resuelve y cachea los datos compartidos vigentes (LOB, Acuerdos, Catálogo) a partir de la última
subida activa en DocumentoCompartido. Reutiliza directamente los parsers ya validados con datos
reales -- este módulo no reimplementa nada de parsing, solo decide QUÉ fichero es el vigente y
evita re-parsear en cada petición mientras no cambie.
"""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from backend.models import DocumentoCompartido, TipoDocumento
from src.parsers.acuerdos_parser import objetivos_por_pos_id, parse_acuerdos
from src.parsers.catalogo_parser import parse_catalogo
from src.parsers.lob_parser import parse_lob

_cache: dict[str, tuple[float, object]] = {}


def _con_cache(path: Path, clave: str, parser_fn):
    mtime = path.stat().st_mtime
    entrada = _cache.get(clave)
    if entrada is not None and entrada[0] == mtime:
        return entrada[1]
    resultado = parser_fn(path)
    _cache[clave] = (mtime, resultado)
    return resultado


def _ruta_activa(session: Session, tipo: TipoDocumento) -> Path | None:
    doc = session.exec(
        select(DocumentoCompartido)
        .where(DocumentoCompartido.tipo == tipo, DocumentoCompartido.activo == True)  # noqa: E712
        .order_by(DocumentoCompartido.subido_en.desc())
    ).first()
    return Path(doc.ruta_almacenada) if doc else None


def clientes_lob_actuales(session: Session):
    path = _ruta_activa(session, TipoDocumento.LOB)
    if path is None:
        return []
    return _con_cache(path, "lob", parse_lob)


def objetivos_pacto_actuales(session: Session):
    path = _ruta_activa(session, TipoDocumento.ACUERDOS)
    if path is None:
        return {}
    acuerdos = _con_cache(path, "acuerdos", parse_acuerdos)
    return objetivos_por_pos_id(acuerdos)


def catalogo_actual(session: Session):
    path = _ruta_activa(session, TipoDocumento.CATALOGO)
    if path is None:
        return []
    return _con_cache(path, "catalogo", parse_catalogo)
