"""
Subida de datos compartidos (LOB, Acuerdos Comerciales, Catálogo/tarifa, hojas de pedido,
condiciones, sell-out). Solo admin. Cada subida de un tipo "de snapshot único" (LOB, ACUERDOS,
CATALOGO) desactiva las anteriores del mismo tipo; los tipos "por etiqueta" (HOJA_PEDIDO,
CONDICIONES, SELL_OUT) desactivan solo las anteriores con la misma etiqueta (gama/campaña), porque
pueden convivir varias activas a la vez -- una hoja de pedido por gama, por ejemplo.

LOB/Acuerdos/Catálogo se parsean al subir para validar el fichero y devolver un recuento real al
admin (nunca "subida OK" a ciegas) -- si el parser falla, se rechaza la subida con el error, no se
guarda un fichero que luego rompería silenciosamente toda la cartera.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import Session, select

from backend.auth import requiere_admin
from backend.db import UPLOADS_DIR, get_session
from backend.models import Delegado, DocumentoCompartido, TipoDocumento
from src.parsers.acuerdos_parser import parse_acuerdos
from src.parsers.catalogo_parser import parse_catalogo
from src.parsers.lob_parser import parse_lob

router = APIRouter(prefix="/admin/documentos", tags=["admin"])

_PARSERS_VALIDACION = {
    TipoDocumento.LOB: parse_lob,
    TipoDocumento.ACUERDOS: parse_acuerdos,
    TipoDocumento.CATALOGO: parse_catalogo,
}


def _guarda_fichero(tipo: TipoDocumento, archivo: UploadFile) -> Path:
    carpeta = UPLOADS_DIR / tipo.value.lower()
    carpeta.mkdir(parents=True, exist_ok=True)
    marca_tiempo = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    destino = carpeta / f"{marca_tiempo}_{archivo.filename}"
    with destino.open("wb") as f:
        shutil.copyfileobj(archivo.file, f)
    return destino


def _sube_documento(
    tipo: TipoDocumento,
    archivo: UploadFile,
    etiqueta: str | None,
    admin: Delegado,
    session: Session,
) -> DocumentoCompartido:
    destino = _guarda_fichero(tipo, archivo)

    n_registros = None
    parser_fn = _PARSERS_VALIDACION.get(tipo)
    if parser_fn is not None:
        try:
            resultado = parser_fn(destino)
        except Exception as exc:  # noqa: BLE001 -- se traduce a un 400 explícito, no se guarda el fichero
            destino.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"No se pudo parsear el fichero: {exc}") from exc
        n_registros = len(resultado)

    activos_anteriores = session.exec(
        select(DocumentoCompartido).where(
            DocumentoCompartido.tipo == tipo,
            DocumentoCompartido.activo == True,  # noqa: E712
            DocumentoCompartido.etiqueta == etiqueta,
        )
    ).all()
    for doc in activos_anteriores:
        doc.activo = False
        session.add(doc)

    nuevo = DocumentoCompartido(
        tipo=tipo,
        etiqueta=etiqueta,
        nombre_fichero_original=archivo.filename,
        ruta_almacenada=str(destino),
        subido_por_delegado_id=admin.id,
        activo=True,
        n_registros=n_registros,
    )
    session.add(nuevo)
    session.commit()
    session.refresh(nuevo)
    return nuevo


@router.post("/lob")
def sube_lob(archivo: UploadFile, admin: Delegado = Depends(requiere_admin), session: Session = Depends(get_session)):
    doc = _sube_documento(TipoDocumento.LOB, archivo, None, admin, session)
    return {"id": doc.id, "n_clientes": doc.n_registros, "subido_en": doc.subido_en}


@router.post("/acuerdos")
def sube_acuerdos(archivo: UploadFile, admin: Delegado = Depends(requiere_admin), session: Session = Depends(get_session)):
    doc = _sube_documento(TipoDocumento.ACUERDOS, archivo, None, admin, session)
    return {"id": doc.id, "n_acuerdos": doc.n_registros, "subido_en": doc.subido_en}


@router.post("/catalogo")
def sube_catalogo(archivo: UploadFile, admin: Delegado = Depends(requiere_admin), session: Session = Depends(get_session)):
    doc = _sube_documento(TipoDocumento.CATALOGO, archivo, None, admin, session)
    return {"id": doc.id, "n_productos": doc.n_registros, "subido_en": doc.subido_en}


@router.post("/hoja-pedido")
def sube_hoja_pedido(
    archivo: UploadFile,
    gama: str,
    admin: Delegado = Depends(requiere_admin),
    session: Session = Depends(get_session),
):
    doc = _sube_documento(TipoDocumento.HOJA_PEDIDO, archivo, gama, admin, session)
    return {"id": doc.id, "gama": gama, "subido_en": doc.subido_en}


@router.post("/condiciones")
def sube_condiciones(
    archivo: UploadFile,
    etiqueta: str,
    admin: Delegado = Depends(requiere_admin),
    session: Session = Depends(get_session),
):
    doc = _sube_documento(TipoDocumento.CONDICIONES, archivo, etiqueta, admin, session)
    return {"id": doc.id, "etiqueta": etiqueta, "subido_en": doc.subido_en}


@router.post("/sell-out")
def sube_sell_out(
    archivo: UploadFile,
    etiqueta: str,
    admin: Delegado = Depends(requiere_admin),
    session: Session = Depends(get_session),
):
    doc = _sube_documento(TipoDocumento.SELL_OUT, archivo, etiqueta, admin, session)
    return {"id": doc.id, "etiqueta": etiqueta, "subido_en": doc.subido_en}


@router.get("")
def lista_documentos_activos(admin: Delegado = Depends(requiere_admin), session: Session = Depends(get_session)):
    activos = session.exec(select(DocumentoCompartido).where(DocumentoCompartido.activo == True)).all()  # noqa: E712
    return [
        {
            "id": d.id,
            "tipo": d.tipo,
            "etiqueta": d.etiqueta,
            "nombre_fichero_original": d.nombre_fichero_original,
            "subido_en": d.subido_en,
            "n_registros": d.n_registros,
        }
        for d in activos
    ]
