# Smart Visit Planner — Instrucciones de proyecto para Claude Code

## Qué es esto
App para delegados comerciales de Avène, Ducray, A-Derma y Dexeryl (grupo Pierre Fabre).
Ayuda a preparar visitas a farmacias: evolución del cliente, gaps vs. pactos comerciales,
propuesta de pedido editable, simulación de impacto. Uso principal: iPad.

**Lee siempre `docs/00_SPEC_MAESTRA.md` antes de tomar decisiones de negocio o de arquitectura.**
Es la fuente de verdad. Ante cualquier duda de reglas de negocio, esa spec manda sobre cualquier
suposición razonable que se te ocurra.

## Reglas de negocio que NUNCA se rompen (resumen — el detalle está en la spec)
- Klorane NUNCA se usa para calcular objetivos, gaps, pactos o recomendaciones.
- PACTO ADA (Avène+Ducray+A-Derma) y PACTO DEXERYL son independientes. Nunca sumarlos.
- Nunca mezclar EUROS con UNIDADES en un mismo cálculo.
- TAM12M − YTD no es nunca un "pedido recomendado".
- 0 por fallo de lectura/OCR ≠ 0 real. Diferenciar siempre 0 / N/D / NO DETECTADO / ERROR LECTURA.
- Nunca inventar CN, PVL, ni datos de un producto no identificado.
- Identidad del punto de venta = dirección + CP + población, no solo el CPV (puede cambiar).
- Todo análisis de facturación compara SIEMPRE con año anterior Y con el pacto, nunca solo uno.
- El pedido propuesto nunca se calcula solo para "rellenar el gap en euros".

## Datos disponibles en `docs/`
- `lob_compar/`: LOB (csv) + 2 COMPAR (xlsx: OCTUBRE 2025 y JUNIO 2026 — cada uno guarda su fecha de
  referencia; la evolución histórica se construye desde octubre 2024/2025, no mayo)
- `historico/`: histórico de gamas 2023-2025 (xlsx)
- `catalogo/`: tarifa del ciclo 3 (xlsx) — base para CN/PVL/producto
- `ciclo3/hojas_pedido/`: hojas de pedido por gama (pdf)
- `ciclo3/chuletas/`: condiciones comerciales ADA y transversales (pdf), plan comercial (pptx)
- `ciclo3/condiciones_descuentos/`: descuentos/incentivos de campaña vigentes (xlsx)

**Aún faltan** (pídelos al usuario cuando toque la Fase 4-5, no antes): Ficha Cliente 2026 de un
cliente real, y capturas de Veeva de ese mismo cliente. Sin esto no se puede validar el parser de
Ficha/Veeva, pero SÍ se puede avanzar con LOB, COMPAR, catálogo y motor de comparación mientras tanto.

## Orden de desarrollo — NO te saltes fases sin validar la anterior con el usuario
Ver sección 39 de la spec. Resumen:
1. Modelo de datos (esquema completo: cliente, pactos, marcas, gamas, productos, histórico, ciclo, pedido)
2. Parser + validación de LOB
3. Parser + validación de COMPAR (múltiples fechas)
4. Parser + validación de Ficha 2026 (cuando llegue el ejemplo)
5. Parser + validación de Veeva (cuando lleguen las capturas)
6. Tabla de normalización marca/gama/producto (nomenclatura Veeva → nombres canónicos, sección 9)
7. Motor de comparación: año anterior + pacto + tendencia
8. Proyección de cierre 2026 (con estacionalidad si hay datos suficientes; si no, "proyección orientativa")
9. Ficha visual (UI)
10. Catálogo/CN + hojas de pedido integrados
11. Propuesta de pedido editable con recálculo en tiempo real
12. Modo grupo/consolidado

Después de cada fase: para, muestra al usuario qué se ha validado con datos reales, y confirma antes
de avanzar a la siguiente.

## Stack sugerido (proponer, no imponer)
- Backend/lógica: Python (pandas para LOB/COMPAR/tarifa, buena lectura de xlsx/csv) o Node/TS si el
  usuario prefiere una sola stack para front+back.
- Frontend: pensado para iPad — web responsive (React/Next o similar) es razonable para no depender
  de App Store; también válido como PWA.
- Persistencia: empezar simple (SQLite o incluso JSON estructurado) mientras se valida el modelo de
  datos; no sobre-ingenierizar en la Fase 1.
- Los documentos de ciclo (chuletas, hojas de pedido, tarifa, descuentos) deben poder actualizarse
  sin tocar código — diséñalo como datos de configuración cargables, no hardcodeados.

## Estilo de trabajo
- El usuario tiene una semana. Prioriza tener SIEMPRE algo funcionando de punta a punta (aunque sea
  con datos parciales) sobre perseguir completitud en una sola fase.
- Al final de cada fase, enseña resultados con datos reales de los ficheros en `docs/`, no con datos
  inventados.
- Si una regla de negocio no está clara en la spec, pregunta — no la asumas ni la simplifiques en
  silencio (ver Control 6-9 de la sección 37: nunca rellenar huecos con inventos).
