# SMART VISIT PLANNER — Especificación Funcional Maestra

> Documento de referencia. Contiene la especificación completa entregada por el cliente.
> Claude Code debe releer este documento antes de tomar decisiones de arquitectura o de reglas de negocio.

## 1. OBJETIVO GENERAL

App profesional para delegados comerciales de las marcas AVÈNE, DUCRAY, A-DERMA y DEXERYL.

Ayuda al delegado a preparar una visita a farmacia: analizar evolución, detectar oportunidades comerciales,
proponer un pedido y simular el impacto de ese pedido sobre los pactos.

**NO** analiza Klorane ni la usa para calcular objetivos, gaps, prioridades, pedidos o recomendaciones.

Uso principal: iPad. Extremadamente visual, clara, rápida de interpretar. El delegado debe poder,
pocos minutos antes de entrar en la farmacia, responder a todas las preguntas de la sección 40.

## 2. LOS DOS PACTOS COMERCIALES

**PACTO ADA** = Avène + Ducray + A-Derma (conjuntamente).
**PACTO DEXERYL** = independiente.

Nunca sumar ADA + Dexeryl como si fueran un único pacto.

Para cada pacto mostrar siempre: objetivo, actual, actual año anterior comparable, evolución %,
% cumplimiento, gap, ritmo esperado a la fecha, desviación respecto al ritmo, previsión de cierre,
diferencia prevista respecto al objetivo.

## 3. REGLA GENERAL DE ANÁLISIS ECONÓMICO

Todo análisis de facturación se hace desde DOS perspectivas simultáneas: comparación con año anterior
Y comparación con objetivo del pacto. Nunca una sola.

Clasificación comercial resultante:
- CRECE Y VA POR ENCIMA DEL PACTO
- CRECE PERO NO LO SUFICIENTE PARA LLEGAR AL PACTO
- CAE PERO SIGUE EN RITMO PARA CUMPLIR
- CAE Y ADEMÁS ESTÁ FUERA DE RITMO
- YA HA CUMPLIDO
- NECESITA RECUPERACIÓN

## 4. PRINCIPIO FUNDAMENTAL: NO MEZCLAR MAGNITUDES

EUROS (facturación, objetivo, gap, pedido económico, sell-in, pacto) vs. UNIDADES
(YTD unidades, TAM12M, histórico por gama, productos vendidos, volumen de pedidos).
Nunca mezclar matemáticamente. Interpretar cada fuente por separado y generar conclusión comercial después.

## 5. FICHA CLIENTE 2026

Fuente principal (PDF o captura). Extraer cuando aparezca: cliente, CPV/POS ID, dirección, población,
provincia, teléfono, grupo, facturación, evolución, objetivos, pactos, datos por marca, gamas prioritarias,
productos héroe, muestras, bonificaciones, descuentos, Assortment Check, solar adelantada, info adicional.

Fuente principal para los objetivos de PACTO ADA y PACTO DEXERYL.

## 6. QUÉ ES EL LOB

Fuente estructurada de información económica de todos los clientes. Documento persistente de ciclo.
Sirve para: identificar clientes, CPV, dirección, grupo, delegado, facturación, objetivos, YTD, año anterior,
evolución, información económica por marca.

Jerarquía: **OBJETIVO DEL PACTO = Ficha 2026**. **LOB = seguimiento económico, evolución y contraste**.
LOB permite seleccionar una farmacia aunque no haya Ficha 2026 disponible.

## 7. LOB Y CAMBIOS DE TITULAR / RAZÓN SOCIAL

Identidad del punto de venta = DIRECCIÓN + CÓDIGO POSTAL + POBLACIÓN (no solo CPV).
Si cambia razón social/CPV pero la farmacia sigue en la misma ubicación: reconstruir histórico,
mostrar "Posible cambio de titular detectado", consolidar si la coincidencia de ubicación es fiable.
Nunca perder histórico solo por cambio de CPV.

## 8. VEEVA

Información de actividad comercial y unidades. Pueden adjuntarse varias capturas de un mismo cliente;
analizar el conjunto completo. Aporta: marca, gama, producto, YTD unidades, año anterior, TAM12M,
peso YTD, peso 12M, venta mensual, rotación, histórico, productos héroe, gamas no trabajadas.

Jerarquía siempre: MARCA → GAMA → PRODUCTO. Nunca sumar gamas de nombre parecido entre marcas distintas
(ej. Avène Cleanance ≠ Ducray Keracnyl; Avène XeraCalm ≠ Ducray Dexyane).

## 9. NOMENCLATURA VEEVA

Tabla de normalización obligatoria, nunca inferir por similitud de palabras. Ejemplos:
- DCC - CHUTE DE CHEVEUX = DUCRAY ANTICAÍDA
- DCG - AP CAPILLAIRES ≠ Anticaída
- PFD = DEXERYL

## 10. GAMA NO TRABAJADA

Solo es oportunidad real si: 0 unidades YTD Y 0 unidades TAM12M/año anterior, o no ha comprado ningún
producto héroe relevante de esa gama según reglas comerciales.

**0 por fallo de OCR ≠ gama no trabajada.** Diferenciar siempre: 0 (sabemos que es cero),
N/D (no disponible), NO DETECTADO, ERROR LECTURA (captura existe pero no se pudo interpretar).

## 11. TAM12M

Referencia de últimos 12 meses. TAM12M − YTD **no es** un pedido recomendado; representa volumen histórico
aún no capturado en el YTD actual. Usar para: potencial, ritmo, estacionalidad, comparar comportamiento.
Nunca convertir directamente en pedido.

## 12-13. COMPAR Y EVOLUCIÓN HISTÓRICA

Cargar y conservar VARIOS COMPAR de distintas fechas, cada uno con su fecha de referencia
(disponibles: COMPAR OCTUBRE 2025 —que también trae datos de OCTUBRE 2024— y COMPAR JUNIO 2026).

> Nota: la especificación original hablaba de "mayo 2025", pero el fichero real entregado es
> **COMPAR 16 OCTUBRE 2025**. La lógica no cambia, solo la fecha base: la evolución histórica
> se construye a partir de OCTUBRE 2024, no mayo 2024. Todo el resto del razonamiento (secciones
> 13-14, ficha visual, etc.) se aplica igual sustituyendo "mayo" por "octubre".

Construir evolución: OCTUBRE 2024 → OCTUBRE 2025 → JUNIO 2026 → PREVISIÓN CIERRE 2026, por marca y por pacto.
Calcular: diferencia y % evolución 2024→2025, diferencia y % evolución 2025→2026 comparable, tendencia,
ritmo actual, proyección de cierre 2026, comparación de la proyección con el objetivo del pacto.

La proyección debe incorporar evolución 2024, evolución 2025, comportamiento 2026, estacionalidad,
histórico mensual disponible — no solo multiplicar el YTD linealmente. Si no hay información suficiente,
mostrar "Proyección orientativa". No inventar precisión falsa.

## 14. ANÁLISIS DE TENDENCIA

🟢 POSITIVA (crece, previsión de cumplimiento) · 🟡 POSITIVA PERO INSUFICIENTE ·
🟡 NEGATIVA CONTROLADA (cae pero en ritmo) · 🔴 NEGATIVA (cae y previsión de incumplimiento).
Existe para ADA, para Dexeryl y para cada marca.

## 15-16. ANÁLISIS DE GRUPOS

Modo GRUPO/CONSOLIDADO usando la columna Grupo del LOB. Consolida ADA y Dexeryl (objetivo, actual,
año anterior, evolución, gap, previsión cierre) y cada marca. Muestra farmacias que crecen/caen,
mayor gap, mayor oportunidad, peso de cada farmacia. Navegación: GRUPO → FARMACIA → FICHA INDIVIDUAL.

Debe funcionar también sin Ficha 2026 ni Veeva, usando LOB + COMPAR históricos. Si no hay pacto oficial
de una farmacia: indicar "Objetivo de pacto individual no disponible" (nunca sustituir silenciosamente).

## 17-18. HOJAS DE PEDIDO Y CATÁLOGO

Hojas de pedido = productos realmente disponibles para vender por ciclo. Extraer: marca, gama, CN,
descripción, formato, PVL, descuento, producto héroe, novedad, condiciones, tipo de campaña.

Catálogo/tarifa estructurado por CN (identificador principal): CN, marca, gama, descripción, formato,
PVL, PVP si existe, héroe, novedad, campaña, estado activo.

## 19-20. PROPUESTA DE PEDIDO EDITABLE

Editable en: unidades (recalcula importe línea, pedido total, impacto sobre pacto, gap posterior),
descuento % (recalcula precio neto e importe), añadir producto por CN (autocompleta desde catálogo;
si no existe → "CN no identificado", permitir entrada manual, nunca inventar datos de un CN desconocido).

Cálculo: PRECIO NETO = PVL × (1 − descuento). IMPORTE LÍNEA = PRECIO NETO × unidades.
Pedido ADA = suma Avène + Ducray + A-Derma. Pedido Dexeryl = suma Dexeryl. Separación siempre mantenida.

## 21-22. IMPACTO DEL PEDIDO Y RAZONABILIDAD

Recalcular en tiempo real ANTES → PEDIDO → DESPUÉS para ambos pactos (actual proyectado, gap restante,
% cumplimiento). La propuesta debe combinar gap, evolución, previsión cierre, Veeva, rotación, TAM12M,
gama, producto, histórico, estacionalidad, hojas de pedido, campañas, novedades, héroes, chuletas,
acciones sell-out. Nunca recomendar unidades solo para rellenar el gap en euros.

## 23-24. CHULETAS Y ACCIONES SELL-OUT

Chuletas = documentación de ciclo con promociones, descuentos, rappels, condiciones, campañas, productos
prioritarios, lanzamientos, héroes, incentivos, muestras, materiales, acciones sell-out → convertir en
reglas comerciales utilizables. Acciones sell-out ya compradas por clientes se detectan automáticamente
al seleccionar cliente y refuerzan la recomendación de pedido.

## 25-26. FICHA VISUAL Y REGLA DE FACTURACIÓN GLOBAL

Ficha visual = centro de la visita: datos cliente, Pacto ADA, Pacto Dexeryl, situación por marca,
situación por gama (unidades YTD, año anterior, TAM12M, diferencia, % evolución, estado, y "unidades
que faltarían para igualar el año anterior" — indicador comercial, no pedido automático).

Estados de gama: 🟢 por encima del año anterior · 🟡 cerca · 🔴 por debajo ·
🔵 gama no trabajada/oportunidad confirmada.

**Regla aplicable en TODOS los módulos** al analizar facturación: actual, año anterior comparable,
diferencia €, evolución %, objetivo/pacto, % cumplimiento, gap actual, previsión cierre, gap previsto
al cierre. Nunca mostrar solo "actual vs objetivo" o solo "actual vs año anterior".

## 27-28. AVÈNE SOLAR Y SOLAR ADELANTADA

Unidades desde Veeva prioritariamente; evolución económica desde LOB. Si no corresponden, avisar:
usar Veeva para rotación y LOB para facturación. Solar adelantada (desde ~octubre) es palanca de cierre
económico pero el rappel Solar se determina en la comanda de campaña, NO por el cierre del año —
nunca recalcular el tramo de rappel con la solar adelantada.

## 29-30. SISTEMA PROTEGER/CONSOLIDAR/RECUPERAR Y "QUÉ HACER HOY"

🟢 PROTEGER (buen comportamiento, objetivo cumplido, tendencia positiva) ·
🟡 CONSOLIDAR (cerca del objetivo, seguimiento) ·
🔴 RECUPERAR (gap relevante, caída, previsión de incumplimiento).
Combina año anterior + pacto + tendencia.

"Qué hacer hoy": máximo 3-5 acciones prioritarias, sin saturar la pantalla.

## 31-32. PREGUNTAS COMERCIALES Y GRÁFICOS

Preguntas basadas en datos reales para el farmacéutico. Gráficos visuales, sencillos, estáticos,
pensados para iPad: barras horizontales, barras de progreso, semáforos, tendencias simples.
Evitar gráficos interactivos con zoom/movimiento.

## 33-34. GESTIÓN DE CICLO

Cada ~2,5 meses cambia el ciclo: condiciones, promociones, novedades, productos, héroes, tarifas,
hojas de pedido, chuletas, acciones sell-out. Debe poder actualizarse sin tocar código.

Documentos persistentes de ciclo: LOB actual, COMPAR (octubre 2025, junio 2026, futuros), tarifa/catálogo,
hojas de pedido, chuletas ADA y transversales, acciones sell-out, listados campañas, productos/CN, PVL,
novedades, héroes.

## 35-36. MODOS Y FLUJO DE VISITA INDIVIDUAL

Tres modos: VISITA INDIVIDUAL · GRUPO/CONSOLIDADO · GESTIÓN DE CICLO.

Flujo visita: buscar cliente → seleccionar punto de venta → adjuntar Ficha 2026 + capturas Veeva →
validar capturas → cruzar Ficha + LOB + COMPAR 2024/25/26 + Veeva + hojas pedido + tarifa + chuletas +
sell-out → Ficha Visual → Qué Hacer Hoy → Propuesta de Pedido → delegado edita (unidades, descuento,
añade CN) → recálculo (importe, pacto ADA, pacto Dexeryl, gap posterior).

## 37. VALIDACIONES OBLIGATORIAS

1. Objetivo − actual = gap (si no cuadra, mostrar inconsistencia)
2. Datos actuales vs año anterior
3. Actual vs pacto
4. Proyección cierre vs pacto
5. No mezclar euros y unidades
6. OCR falla en Veeva → mostrar "Error de lectura Veeva", nunca "0 gamas"
7. No inventar oportunidades por ausencia de lectura
8. No inventar CN
9. No inventar PVL
10. Cada cifra debe conocer: valor, unidad, fuente, período

## 38. ARQUITECTURA DE DATOS RECOMENDADA

CLIENTE (identificación, punto de venta físico, grupo, titulares/CPV históricos) ·
PACTO ADA / PACTO DEXERYL (objetivo, actual, año anterior, gap, tendencia, previsión cierre) ·
MARCAS (Avène, Ducray, A-Derma, Dexeryl) ·
GAMAS (marca, gama, YTD actual, año anterior, TAM12M, diferencia, unidades para igualar año anterior,
tendencia) ·
PRODUCTOS (CN, descripción, formato, marca, gama, PVL, héroe, novedad) ·
HISTÓRICO (mayo 2024, mayo 2025, junio 2026, futuros COMPAR) ·
CICLO (condiciones, promociones, sell-out, hojas pedido, chuletas) ·
PEDIDO (CN, producto, unidades, PVL, descuento, precio neto, importe, pacto afectado).

## 39. ORDEN DE DESARROLLO (NO SALTAR FASES SIN VALIDAR LA ANTERIOR)

1. Modelo de datos
2. Leer y validar LOB
3. Leer y validar COMPAR 2024/2025/2026
4. Leer y validar Ficha 2026
5. Leer y validar Veeva
6. Normalizar marcas/gamas/productos
7. Motor de comparación (año anterior + pacto + tendencia)
8. Proyección de cierre 2026
9. Ficha visual
10. Hojas de pedido / catálogo / CN
11. Propuesta editable
12. Grupos

## 40. CRITERIO FINAL DE ÉXITO

El delegado, 5 minutos antes de entrar en la farmacia, debe poder responder: cómo está el cliente
respecto a 2024/2025, cómo está 2026 respecto al año anterior, cómo está respecto al pacto ADA,
cómo está Dexeryl, si cumplirá al ritmo actual, qué marca/gama explica el problema, cuántas unidades
faltan en esa gama, qué dice Veeva/LOB/histórico COMPAR, qué promociones y sell-out puede usar,
qué productos puede proponer, si puede añadir un CN y que se identifique automáticamente, si puede
cambiar unidades y descuento, cuál es el importe del pedido, cómo queda el gap ADA y Dexeryl después.

**REGLA FINAL: primero validar los datos, después compararlos, después interpretarlos, y solo entonces
recomendar y proponer un pedido. Nunca inventar información para que la ficha parezca completa.**
