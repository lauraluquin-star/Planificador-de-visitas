"""
Subida de Ficha Cliente 2026 y capturas de Veeva, por cliente, para preparar una visita.

Cualquier delegado puede subir para un pos_id de SU PROPIA cartera (no de admin) -- se comprueba
contra el LOB activo antes de aceptar la subida. La extracción vía Claude se dispara al subir y se
guarda en extraccion_json con estado PENDIENTE_REVISION; el motor de comparación nunca debe leer
ese campo directamente (spec: nunca usar una extracción sin confirmar). El delegado revisa/corrige
en el frontend y llama al endpoint de confirmación, que es lo único que escribe
datos_confirmados_json.

Si la extracción falla (Claude no devuelve JSON válido, o la llamada da error), la fila se guarda
igualmente con estado ERROR_EXTRACCION y el texto crudo en nota_inconsistencia -- nunca se pierde
la subida ni se inventa una extracción vacía.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import Session, select

from backend.auth import delegado_actual
from backend.datos_compartidos import clientes_lob_actuales
from backend.db import UPLOADS_DIR, get_session
from backend.extraccion_visita import ExtraccionError, extrae_ficha2026, extrae_veeva
from backend.models import Delegado, EstadoExtraccion, Ficha2026, VeevaCaptura

router = APIRouter(prefix="/cartera", tags=["visita"])


def _verifica_pos_id_propio(pos_id: str, delegado: Delegado, session: Session) -> None:
    clientes = clientes_lob_actuales(session)
    if not any(c.pos_id == pos_id and c.delegado_nombre == delegado.nombre_lob for c in clientes):
        raise HTTPException(
            status_code=404,
            detail=f"'{pos_id}' no está en tu cartera (o todavía no hay LOB activo subido).",
        )


def _guarda_capturas(carpeta_tipo: str, pos_id: str, archivos: list[UploadFile]) -> tuple[list[Path], str]:
    carpeta = UPLOADS_DIR / carpeta_tipo / pos_id
    carpeta.mkdir(parents=True, exist_ok=True)
    marca_tiempo = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    rutas: list[Path] = []
    for i, archivo in enumerate(archivos):
        destino = carpeta / f"{marca_tiempo}_{i}_{archivo.filename}"
        with destino.open("wb") as f:
            shutil.copyfileobj(archivo.file, f)
        rutas.append(destino)
    nombres = ", ".join(a.filename for a in archivos)
    return rutas, nombres


@router.post("/{pos_id}/ficha2026")
def sube_ficha2026(
    pos_id: str,
    archivos: list[UploadFile],
    delegado: Delegado = Depends(delegado_actual),
    session: Session = Depends(get_session),
):
    _verifica_pos_id_propio(pos_id, delegado, session)
    rutas, nombres = _guarda_capturas("ficha2026", pos_id, archivos)

    fila = Ficha2026(
        pos_id=pos_id,
        delegado_id=delegado.id,
        nombre_fichero_original=nombres,
        ruta_almacenada=json.dumps([str(r) for r in rutas]),
    )
    try:
        fila.extraccion_json = json.dumps(extrae_ficha2026(rutas), ensure_ascii=False)
        fila.estado = EstadoExtraccion.PENDIENTE_REVISION
    except ExtraccionError as exc:
        fila.estado = EstadoExtraccion.ERROR_EXTRACCION
        fila.nota_inconsistencia = f"Claude no devolvió JSON válido: {exc.texto_crudo[:2000]}"
    except Exception as exc:  # noqa: BLE001 -- se guarda igual, nunca se pierde la subida
        fila.estado = EstadoExtraccion.ERROR_EXTRACCION
        fila.nota_inconsistencia = f"Error llamando a la extracción: {exc}"

    session.add(fila)
    session.commit()
    session.refresh(fila)
    return _ficha_a_dict(fila)


@router.get("/{pos_id}/ficha2026")
def lista_ficha2026(
    pos_id: str,
    delegado: Delegado = Depends(delegado_actual),
    session: Session = Depends(get_session),
):
    _verifica_pos_id_propio(pos_id, delegado, session)
    filas = session.exec(
        select(Ficha2026)
        .where(Ficha2026.pos_id == pos_id, Ficha2026.delegado_id == delegado.id)
        .order_by(Ficha2026.subido_en.desc())
    ).all()
    return [_ficha_a_dict(f) for f in filas]


@router.post("/ficha2026/{ficha_id}/confirmar")
def confirma_ficha2026(
    ficha_id: int,
    datos_confirmados: dict,
    delegado: Delegado = Depends(delegado_actual),
    session: Session = Depends(get_session),
):
    fila = session.get(Ficha2026, ficha_id)
    if fila is None or fila.delegado_id != delegado.id:
        raise HTTPException(status_code=404, detail="Ficha no encontrada")
    fila.datos_confirmados_json = json.dumps(datos_confirmados, ensure_ascii=False)
    fila.estado = EstadoExtraccion.CONFIRMADA
    fila.confirmado_en = datetime.utcnow()
    session.add(fila)
    session.commit()
    session.refresh(fila)
    return _ficha_a_dict(fila)


@router.post("/{pos_id}/veeva")
def sube_veeva(
    pos_id: str,
    archivos: list[UploadFile],
    delegado: Delegado = Depends(delegado_actual),
    session: Session = Depends(get_session),
):
    _verifica_pos_id_propio(pos_id, delegado, session)
    rutas, nombres = _guarda_capturas("veeva", pos_id, archivos)

    fila = VeevaCaptura(
        pos_id=pos_id,
        delegado_id=delegado.id,
        nombre_fichero_original=nombres,
        ruta_almacenada=json.dumps([str(r) for r in rutas]),
    )
    try:
        fila.extraccion_json = json.dumps(extrae_veeva(rutas), ensure_ascii=False)
        fila.estado = EstadoExtraccion.PENDIENTE_REVISION
    except ExtraccionError as exc:
        fila.estado = EstadoExtraccion.ERROR_EXTRACCION
        fila.datos_confirmados_json = None
        fila.extraccion_json = json.dumps({"_error_texto_crudo": exc.texto_crudo[:2000]})
    except Exception as exc:  # noqa: BLE001 -- se guarda igual, nunca se pierde la subida
        fila.estado = EstadoExtraccion.ERROR_EXTRACCION
        fila.extraccion_json = json.dumps({"_error": str(exc)})

    session.add(fila)
    session.commit()
    session.refresh(fila)
    return _veeva_a_dict(fila)


@router.get("/{pos_id}/veeva")
def lista_veeva(
    pos_id: str,
    delegado: Delegado = Depends(delegado_actual),
    session: Session = Depends(get_session),
):
    _verifica_pos_id_propio(pos_id, delegado, session)
    filas = session.exec(
        select(VeevaCaptura)
        .where(VeevaCaptura.pos_id == pos_id, VeevaCaptura.delegado_id == delegado.id)
        .order_by(VeevaCaptura.subido_en.desc())
    ).all()
    return [_veeva_a_dict(f) for f in filas]


@router.post("/veeva/{veeva_id}/confirmar")
def confirma_veeva(
    veeva_id: int,
    datos_confirmados: dict,
    delegado: Delegado = Depends(delegado_actual),
    session: Session = Depends(get_session),
):
    fila = session.get(VeevaCaptura, veeva_id)
    if fila is None or fila.delegado_id != delegado.id:
        raise HTTPException(status_code=404, detail="Captura de Veeva no encontrada")
    fila.datos_confirmados_json = json.dumps(datos_confirmados, ensure_ascii=False)
    fila.estado = EstadoExtraccion.CONFIRMADA
    fila.confirmado_en = datetime.utcnow()
    session.add(fila)
    session.commit()
    session.refresh(fila)
    return _veeva_a_dict(fila)


def _ficha_a_dict(f: Ficha2026) -> dict:
    return {
        "id": f.id,
        "pos_id": f.pos_id,
        "nombre_fichero_original": f.nombre_fichero_original,
        "subido_en": f.subido_en,
        "estado": f.estado,
        "extraccion": json.loads(f.extraccion_json) if f.extraccion_json else None,
        "datos_confirmados": json.loads(f.datos_confirmados_json) if f.datos_confirmados_json else None,
        "confirmado_en": f.confirmado_en,
        "nota_inconsistencia": f.nota_inconsistencia,
    }


def _veeva_a_dict(f: VeevaCaptura) -> dict:
    return {
        "id": f.id,
        "pos_id": f.pos_id,
        "nombre_fichero_original": f.nombre_fichero_original,
        "subido_en": f.subido_en,
        "estado": f.estado,
        "extraccion": json.loads(f.extraccion_json) if f.extraccion_json else None,
        "datos_confirmados": json.loads(f.datos_confirmados_json) if f.datos_confirmados_json else None,
        "confirmado_en": f.confirmado_en,
    }
