# Datos de Ciclo 4 (preparación) — solo cartera de Laura Luquin Franquet

Fuente: `PREPARACIÓN_CICLO_C4_2026.xlsx`, compartido por la delegada el 01/09/2026. El Excel
original tiene 4 hojas y cubre **toda la empresa** (57 delegados, 15.660 clientes) — confirmado
con la delegada que, de momento, solo se trabaja con su propia cartera (COACH = "LAURA LUQUIN
FRANQUET", 189 clientes). El resto de la empresa NUNCA se ha guardado en este repo.

Confirmado con la delegada (01/09/2026): **ya estamos en Ciclo 4**, no Ciclo 3.

**Actualización 01/09/2026**: la delegada compartió `v3_PLAN_COMERCIAL_CICLO_4_2026__enviar.pdf`
(deck comercial de 46 páginas, empresa completa), que SÍ contiene las condiciones reales de
Ciclo 4 por gama y los incentivos de delegado. Se ha extraído a dos ficheros nuevos:
- `condiciones_pacto_ciclo4.json`: condiciones de descuento al CLIENTE por gama (sustituye a
  `docs/ciclo3/condiciones_descuentos/condiciones_pacto_ciclo3.json` como fuente vigente; el
  fichero de Ciclo 3 se conserva como histórico, no se borra).
- `incentivos_delegado_ciclo4.json`: incentivos internos del delegado (€/pedido, DN, bolsa anual)
  — nunca se mezclan con el descuento que ve el cliente.

Diferencias reales encontradas frente a lo que estaba implementado (basado en Ciclo 3):
Capilar pasa de "hueco histórico" a tramo ligado a la novedad Kelual DS Sebocontrol (6uds→26%);
Anticaída sube de 28% a 30% (12uds) y añade un segundo tramo con mínimo de Anacaps 90 a partir
del 16 oct; Exomega/Atopia deja de combinarse con XeraCalm y Dexyane (en Ciclo 4 es solo A-Derma,
con su propio tramo 4+3+3/6+6+6 novedad facial+corporal); XeraCalm, Dexyane Med, Hydrance y
Esenciales pasan a contar cada una por separado (12uds→26%, antes iban combinadas); Dexeryl
cambia del tramo de novedad "3+3/6+6" a una condición única "12uds→26%" dentro de "Pedido Resto",
sin incentivo de delegado asociado; Cicalfate no cambia (24uds→24%, 48uds→26%).
Aún pendiente de aplicar a las fichas ya construidas (p.ej. Font Soler Pilar).

## Ficheros

- `ciclo4_preparacion_laura.csv` (189 filas, de la hoja "CICLO_4" del Excel): histórico por gama
  y año (2023/24/25/YTD26) de Exomega, Antiedad, XeraCalm, Esenciales, Hydrance, Anticaída,
  Dexyane, Capilar, Keracnyl -- MÁS unidades reales de novedades concretas por cliente (columnas
  con nombre de producto, ej. "SERUM LIFTING HAP 30ML AV"). Estas cantidades de novedad son
  **pedidos YA realizados** (confirmado por la delegada), no una propuesta -- nunca se deben volver
  a proponer como si fueran un hueco pendiente.
- `compar_julio26_laura.csv` (172 filas, hoja "Compar julio 26"): € por marca (Avène con/sin
  solar, Ducray, A-Derma, Dexeryl) 2025/YTD25/YTD26/evolución + oportunidad detectada
  automáticamente, por cliente.
- `leyenda.csv`: diccionario de columnas del Excel original (hoja "Leyenda").
- `condiciones_pacto_ciclo4.json`: condiciones reales de descuento al cliente por gama, Ciclo 4.
- `incentivos_delegado_ciclo4.json`: incentivos internos del delegado (€/pedido, DN), Ciclo 4.
- `chuletas/v3_PLAN_COMERCIAL_CICLO_4_2026.pdf`: deck comercial fuente (46 págs, empresa completa,
  no es dato de cliente — company-wide, seguro de guardar). De aquí se extrajeron los dos JSON
  anteriores.

## Columnas con significado aún NO confirmado del todo

- `PEDIDO EN SALESFORCE INMEDIATO DESDE 22 MAYO` (en la hoja "Detalle Clientes" aparece con el
  nombre completo "ANTIEDAD PEDIDO EN SALESFORCE INMEDIATO DESDE 22 MAYO", así que es de Antiedad).
  Confirmado que es un pedido YA realizado, no una propuesta. NO confirmado: si esta cifra ya
  incluye las unidades de las columnas de Sérum Peeling/Lifting HAP o es aparte -- para Font Soler
  Pilar (C006969): Sérum Lifting=9, Sérum Peeling=9, este campo=31. Se ha dejado anotado como
  "ya conseguido" sin sumarlo ni restarlo de nada hasta confirmarlo.
- `Micelar 2026 3 ref` (Font Soler Pilar = 48): confirmado que es un pedido ya realizado de
  Agua Micelar (probablemente en unidades, cruzando con la condición avene_cuidados_esenciales
  "12+6 micelar" de la chuleta de Ciclo 3 -- 48 no encaja limpiamente en ese tramo de 12, así que
  puede ser que la condición de Ciclo 4 sea distinta). Pendiente confirmar con chuleta de Ciclo 4.

## Discrepancias reales encontradas (no resueltas, solo anotadas)

Comparando este Excel con `docs/ejemplos_cliente/veeva_font_soler_pilar.json` (capturas de Veeva
de Font Soler Pilar usadas hasta ahora) hay pequeños desajustes en histórico YTD por gama --
p.ej. Exomega YTD 2026: 58 uds en Veeva vs 61 uds en este Excel. Nunca se ha promediado ni
elegido una fuente sobre otra en silencio; cuando afecta a un cálculo ya hecho en una ficha se
anota explícitamente cuál de las dos fuentes se está usando.
