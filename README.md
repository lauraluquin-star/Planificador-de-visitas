# Smart Visit Planner · V2.2

Esta versión corrige los problemas observados en V2.1.

## Qué cambia

- Recupera una interfaz visual con semáforos rojo/amarillo/verde y gráficos.
- El parser de la Ficha 2026 está adaptado a la tabla **Evolución Pacto**.
- El objetivo principal se obtiene de la Ficha 2026; nunca se sustituye por el LOB.
- Corrige la lectura económica del LOB: valores como `21.025` se interpretan como `21.025 €`, no como `21 €`.
- El parser Veeva reconoce filas de gamas por sus códigos reales.
- **DCC-CHUTE DE CHEVEUX = Ducray Anticaída.**
- **DCG-AP CAPILLAIRES NO se interpreta como Anticaída.**
- Lee YTD y TAM12M por gama y, cuando la captura lo permite, por producto.
- Muestra el volumen comparable restante `TAM12M - YTD` sin convertirlo automáticamente en un pedido.
- Genera una propuesta de pedido conservadora y editable usando catálogo/tarifa + Veeva.
- Evita propuestas de 100+ unidades de una referencia: el algoritmo usa aproximadamente un mes de rotación comparable, con topes por gama y SKU.
- Detecta acciones SELL_OUT del cliente por CPV/nombre en los Excel persistentes.
- Mantiene cambio de titular/CPV por punto de venta físico.
- Mantiene modo Grupo / consolidado y Gestión de ciclo.
- COMPAR admite varios archivos Excel.

## Archivos a sustituir en GitHub

Solo:
- `app.py`
- `requirements.txt`
- `packages.txt`
- `README.md`

No borres LOB, COMPAR, product_catalog, hojas de pedido, chuletas ni SELL_OUT.

## Prueba de regresión usada

La lógica de lectura se ha ajustado y comprobado con las capturas de FONT SOLER PILAR compartidas el 19/08/2026:
- Ficha cliente 2026 con Evolución Pacto.
- Veeva Avène por gama.
- Veeva Ducray / PFD / A-Derma.
- Detalle Hydrance y detalle Hyaluron Activ.

La app debe leer la Ficha y Veeva antes de construir el plan y la propuesta. Si no puede confirmar un dato, lo marca como no confirmado en lugar de inventarlo.

## V2.3 — corrección lógica 19/08/2026
- El gap por marca incluye Avène y se prioriza por importe, sin filtrar Klorane/Dexeryl.
- El Plan Express muestra como máximo 4 prioridades reales; se eliminan las tarjetas masivas de TAM12M.
- 0 YTD / 0 TAM12M = SIN ACTIVIDAD, no oportunidad automática.
- Avène Solar usa Veeva como fuente de unidades y LOB solo como contraste económico, mostrando alerta de discrepancia.
- El indicador LOB ya no muestra 0% artificial cuando los campos no están mapeados de forma fiable.
