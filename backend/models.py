"""
Modelos de base de datos.

Deliberadamente NO se duplica aquí el modelo de datos de clientes (ClienteLOB,
PuntoVentaConsolidado, etc.) -- ese ya vive en src/parsers y src/engine, validado con datos reales.
La base de datos solo guarda:

1. Delegado: quién puede entrar y ver qué cartera (cruce por nombre, igual que el motor).
2. DocumentoCompartido: cada subida de LOB/Acuerdos/Catálogo/hojas de pedido/condiciones/sell-out,
   versionada -- el motor siempre lee la última activa de cada tipo, pero no se pierde el histórico
   (spec: poder auditar cambios de ciclo).
3. Ficha2026 / VeevaCaptura: subida por delegado y cliente, con la extracción (vía Claude) pendiente
   de revisión antes de confirmarse -- nunca se usa una extracción sin confirmar en el motor.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class TipoDocumento(str, Enum):
    LOB = "LOB"
    ACUERDOS = "ACUERDOS"
    CATALOGO = "CATALOGO"
    HOJA_PEDIDO = "HOJA_PEDIDO"
    CONDICIONES = "CONDICIONES"
    SELL_OUT = "SELL_OUT"


class EstadoExtraccion(str, Enum):
    PENDIENTE_REVISION = "PENDIENTE_REVISION"
    CONFIRMADA = "CONFIRMADA"
    ERROR_EXTRACCION = "ERROR_EXTRACCION"


class Delegado(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Debe coincidir EXACTO con la columna "Nombre Delegado" del LOB (nunca nombre_dnv) para que
    # cartera_delegado() cruce bien -- ver src/parsers/lob_parser.py.
    nombre_lob: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    passcode_hash: str
    es_admin: bool = False  # admin: puede subir LOB/Acuerdos/Catálogo/hojas de pedido/condiciones
    creado_en: datetime = Field(default_factory=datetime.utcnow)


class DocumentoCompartido(SQLModel, table=True):
    """Una subida de dato compartido entre todos los delegados (LOB, Acuerdos, Catálogo, hojas de
    pedido, condiciones, sell-out). Versionado: activo=True marca la última vigente de cada tipo
    (y, para HOJA_PEDIDO/CONDICIONES/SELL_OUT, también de cada `etiqueta` -- puede haber varias
    hojas de pedido activas a la vez, una por gama)."""

    id: int | None = Field(default=None, primary_key=True)
    tipo: TipoDocumento
    etiqueta: str | None = None  # p.ej. gama de la hoja de pedido ("Atopia", "Dexeryl"...)
    nombre_fichero_original: str
    ruta_almacenada: str
    subido_por_delegado_id: int = Field(foreign_key="delegado.id")
    subido_en: datetime = Field(default_factory=datetime.utcnow)
    activo: bool = True
    n_registros: int | None = None  # p.ej. nº clientes parseados del LOB, para mostrar confirmación


class Ficha2026(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pos_id: str = Field(index=True)  # cruza con ClienteLOB.pos_id
    delegado_id: int = Field(foreign_key="delegado.id")
    nombre_fichero_original: str
    ruta_almacenada: str
    subido_en: datetime = Field(default_factory=datetime.utcnow)
    estado: EstadoExtraccion = EstadoExtraccion.PENDIENTE_REVISION
    extraccion_json: str | None = None  # JSON crudo devuelto por la extracción (Claude), sin confirmar
    datos_confirmados_json: str | None = None  # JSON tras revisión/edición del delegado -- el único que usa el motor
    confirmado_en: datetime | None = None
    nota_inconsistencia: str | None = None  # p.ej. mismatch Total general vs Evolución Pacto (spec 37.1: nunca ocultarlo)


class VeevaCaptura(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pos_id: str = Field(index=True)
    delegado_id: int = Field(foreign_key="delegado.id")
    nombre_fichero_original: str
    ruta_almacenada: str
    subido_en: datetime = Field(default_factory=datetime.utcnow)
    estado: EstadoExtraccion = EstadoExtraccion.PENDIENTE_REVISION
    extraccion_json: str | None = None
    datos_confirmados_json: str | None = None
    confirmado_en: datetime | None = None
