"""
Extracción de Ficha Cliente 2026 y capturas de Veeva vía Claude API (visión).

La extracción NUNCA se usa directamente en el motor de comparación -- se guarda como
"extraccion_json" pendiente de revisión (ver backend/models.py: EstadoExtraccion). El delegado
revisa/corrige en el frontend y confirma; solo entonces se escribe datos_confirmados_json, el
único campo que el motor podrá leer en el futuro.

Reglas de negocio que el prompt fuerza explícitamente (ver CLAUDE.md y docs/00_SPEC_MAESTRA.md):
- Nunca inventar un valor que no esté en la imagen -- celda vacía o no legible => null +
  "lectura" en "sin_dato"/"error_lectura", nunca un 0 salvo que la imagen muestre un 0 real.
- El pacto/objetivo que aparece en Veeva NO es fiable (confirmado por la delegada 01/09/2026) --
  se extrae aparte, en un bloque claramente separado que el motor nunca debe leer como pacto.
- Cualquier inconsistencia interna entre columnas que deberían cuadrar y no cuadran se reporta
  explícitamente, nunca se resuelve en silencio eligiendo una de las dos.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import anthropic

MODEL = "claude-opus-5"

_EXTENSION_MEDIA_TYPE = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class ExtraccionError(Exception):
    """La respuesta de Claude no fue JSON válido -- se conserva el texto crudo para depurar."""

    def __init__(self, texto_crudo: str):
        super().__init__("La extracción no devolvió JSON válido")
        self.texto_crudo = texto_crudo


def _bloque_para(path: Path) -> dict:
    datos = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    if path.suffix.lower() == ".pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": datos}}
    media_type = _EXTENSION_MEDIA_TYPE.get(path.suffix.lower())
    if media_type is None:
        raise ValueError(f"Formato no soportado para extracción: {path.suffix}")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": datos}}


def _extrae_json(paths: list[Path], system_prompt: str) -> dict:
    client = anthropic.Anthropic()
    contenido = [_bloque_para(p) for p in paths]
    contenido.append(
        {
            "type": "text",
            "text": "Extrae los datos de la(s) imagen(es) anteriores siguiendo exactamente el formato y las reglas indicadas.",
        }
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=system_prompt,
        messages=[{"role": "user", "content": contenido}],
    )
    texto = "".join(bloque.text for bloque in response.content if bloque.type == "text").strip()
    if texto.startswith("```"):
        primera_linea_fin = texto.find("\n")
        texto = texto[primera_linea_fin + 1 :] if primera_linea_fin != -1 else texto
        if texto.endswith("```"):
            texto = texto[: -3]
        texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ExtraccionError(texto) from exc


_FICHA_SYSTEM_PROMPT = """\
Eres un extractor de datos de la "Ficha Cliente 2026" de Pierre Fabre (ficha de preparación de \
visita de un delegado comercial de Avène, Ducray, A-Derma y Dexeryl). Te paso una o varias \
capturas de pantalla de la Ficha de UN cliente. Devuelve SOLO un JSON válido (sin texto antes ni \
después, sin ```), con exactamente esta forma:

{
  "cliente": {"nombre": string|null, "pos_id": string|null, "provincia": string|null, "telefono": string|null, "direccion": string|null},
  "facturacion_por_marca": [
    {"marca": string, "fact_2025": number|null, "fact_ytm_2025": number|null, "fact_ytm_2026": number|null, "evol_pct": number|null, "lectura": "ok"|"sin_dato"|"error_lectura"}
  ],
  "descuento_pacto_pct": [{"marca": string, "pct": number|null}],
  "evolucion_pacto": [
    {"marca": string, "fact_a1_colectivo": number|null, "fact_a_colectivo": number|null, "evol_a_colectivo_pct": number|null,
     "obj_15_a_colectivo": number|null, "falta_obj_colectivo": number|null, "fact_a1_marca": number|null,
     "fact_a_marca": number|null, "evol_a_marca_pct": number|null, "falta_obj_marca": number|null,
     "pct_rfa_marca": number|null, "rfa_marca": number|null}
  ],
  "gamas_prioritarias": [{"marca": string, "gama": string, "uds_2025": number|null, "uds_ytm_2025": number|null, "uds_ytd_2026": number|null}],
  "muestras": [{"marca": string, "uds_2025": number|null, "uds_2026": number|null}],
  "productos_heroe": [{"marca": string, "producto": string, "uds_2025": number|null, "uds_ytm_2025": number|null, "uds_ytd_2026": number|null}],
  "notas_libres": string|null,
  "inconsistencias_detectadas": [string]
}

Reglas que debes seguir sin excepción:
- Incluye TODAS las marcas visibles, incluidas Klorane y René Furterer si aparecen -- no las \
excluyas ni las omitas; la decisión de no usarlas en cálculos se toma después, fuera de esta \
extracción.
- Nunca inventes un número que no esté escrito en la imagen. Si una celda está vacía, en blanco, \
o no puedes leerla con confianza, pon null y marca "lectura":"sin_dato" o "error_lectura" según \
corresponda -- nunca pongas 0 salvo que la imagen muestre literalmente un 0.
- Si dos columnas que deberían coincidir no coinciden entre sí (por ejemplo una columna \
"Colectivo" y una "Marca" del mismo pacto que no cuadran, o un total que no suma sus partes), \
anótalo en "inconsistencias_detectadas" como texto libre explicando qué no cuadra exactamente. \
No lo resuelvas ni elijas un valor sobre otro.
- Copia los nombres de gama/producto tal y como aparecen en la imagen, sin traducir ni normalizar.
- "notas_libres" es para cualquier anotación visible en la ficha que no encaje en los campos \
anteriores (por ejemplo "KLORANE ADELANTADA: 392").
"""

_VEEVA_SYSTEM_PROMPT = """\
Eres un extractor de datos de capturas de pantalla de Veeva (Customer Card de una farmacia, \
Pierre Fabre). Te paso una o varias capturas de UN cliente. Devuelve SOLO un JSON válido (sin \
texto antes ni después, sin ```), con exactamente esta forma:

{
  "cliente_pos_id": string|null,
  "cliente_nombre": string|null,
  "marcas": [{"marca_veeva": string, "ytd": number|null, "tam12m": number|null}],
  "gamas": [{"marca_veeva": string, "gama_veeva": string, "ytd": number|null, "tam12m": number|null, "peso_ytd_pct": number|null, "peso_12m_pct": number|null}],
  "productos": [{"marca_veeva": string, "gama_veeva": string, "producto": string, "ytd": number|null, "tam12m": number|null}],
  "pacto_veeva_no_usar": [{"marca_veeva": string, "sell_in_y1": number|null, "objetivo_ventas": number|null, "pct_objetivo_alcanzado": number|null, "pendiente_ytd": number|null}],
  "periodo_o_fecha_captura": string|null,
  "notas_libres": string|null
}

Reglas que debes seguir sin excepción:
- "pacto_veeva_no_usar" es SOLO para trazabilidad -- si la captura muestra columnas de Objetivo \
Ventas / % Objetivo Alcanzado / Pendiente YTD, extráelas ahí. Estos datos NO son fiables como \
pacto (confirmado por la delegada) y jamás deben mezclarse con "marcas"/"gamas"/"productos".
- Incluye todas las marcas visibles (incluidas Klorane/René Furterer si aparecen).
- Nunca inventes un número. Celda vacía o no legible => null. Si una gama concreta NO aparece en \
absoluto dentro de una marca que sí está capturada por completo, eso puede significar 0 real de \
compra (Veeva no muestra filas sin compra) -- en ese caso NO inventes una fila a 0 en "gamas"; \
en su lugar anota en "notas_libres" qué marcas parecen capturadas por completo, para que el \
delegado decida.
- Copia nombres de marca/gama/producto tal y como aparecen, códigos Veeva incluidos (por ejemplo \
"ASO-Solaires", "PEL-Etats Pelliculaires").
"""


def extrae_ficha2026(paths: list[Path]) -> dict:
    return _extrae_json(paths, _FICHA_SYSTEM_PROMPT)


def extrae_veeva(paths: list[Path]) -> dict:
    return _extrae_json(paths, _VEEVA_SYSTEM_PROMPT)
