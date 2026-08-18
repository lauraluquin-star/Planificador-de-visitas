# Smart Visit Planner · V2

Versión nueva centrada en la pregunta: **¿qué tengo que hacer hoy en esta visita?**

## Reglas de negocio incorporadas

1. **Objetivo de la visita = acuerdo de la Ficha 2026.**
   - El LOB NO sustituye al objetivo del acuerdo.
   - Si la app no puede confirmar el objetivo de la ficha, muestra "Pendiente".

2. **LOB / COMPAR = contraste económico.**
   - Sirven para evolución, facturación y contexto.
   - En grupos sin fichas individuales, el objetivo LOB puede usarse como referencia operativa, claramente etiquetado como "Objetivo LOB", nunca como acuerdo.

3. **Veeva = unidades y gamas reales.**
   - Las capturas se leen automáticamente con OCR.
   - No se copian datos entre marcas o gamas.
   - Ducray DCC-CHUTE DE CHEVEUX = Anticaída.
   - PFD = Dexeryl.

4. **Oportunidad / gama no trabajada.**
   - Se considera oportunidad confirmada cuando Veeva muestra 0 YTD y 0 TAM12M para esa gama.
   - Si no existe captura suficiente, se marca como no confirmada; no se inventa.

5. **Cambio de titular / razón social / CPV.**
   - La identidad primaria es el punto de venta físico: dirección + CP + población.
   - Los CPV son etapas administrativas.
   - La app consolida registros coincidentes por ubicación.

6. **Grupos de farmacias.**
   - Se analizan desde LOB/COMPAR aunque no exista Ficha o Veeva.
   - El ranking prioriza caída YTD vs YTD-1 y gap LOB.
   - Se consolida por ubicación física.

7. **Cambio de ciclo cada ~2,5 meses.**
   - En "Gestión de ciclo" se cargan nuevo LOB, COMPAR, tarifa/catálogo, hojas de pedido y chuletas/campañas.
   - No hace falta modificar `app.py`.
   - En Streamlit Community Cloud los uploads de sesión no son persistentes tras un reinicio. Para dejar un ciclo permanente, se debe sustituir el pack de archivos en el repositorio `/data`.

8. **Propuesta de pedido.**
   - Conservadora: evita pedidos desproporcionados.
   - Prioriza surtido, héroes y novedades.
   - Cuando existe Veeva usa YTD/TAM12M como contexto de rotación.
   - Las unidades se pueden ajustar durante la visita.

## Instalación en GitHub + Streamlit

Sube al repositorio:
- `app.py`
- `requirements.txt`
- `packages.txt`
- carpeta `data/` con `lob_master.csv`
- este `README.md`

En Streamlit:
- Repository: tu repositorio
- Branch: `main`
- Main file path: `app.py`

## Primer test recomendado

1. Seleccionar un cliente.
2. Adjuntar la Ficha 2026 como PDF o captura.
3. Adjuntar varias capturas Veeva (marca/gama/producto si están disponibles).
4. Validar primero:
   - Objetivo acuerdo.
   - Actual acuerdo.
   - Gap por marca.
   - Unidades YTD/TAM12M.
   - Que no mezcle Avène/Ducray ni gamas parecidas.
5. Cargar el ciclo actual en "Gestión de ciclo" para activar acciones y propuesta de pedido.
