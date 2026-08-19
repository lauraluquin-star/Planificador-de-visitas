# Smart Visit Planner · V2.4

Versión centrada en dos pantallas de trabajo:

1. **Ficha de visita visual**
2. **Propuesta de pedido editable + simulación del gap posterior**

## Cambios clave

- Mantiene el objetivo principal desde la Ficha 2026.
- Corrige específicamente el problema por el que Avène podía desaparecer del gap:
  - se valida la fila `AVÈNE SIN SOLAR` de la tabla financiera;
  - si el parser de Evolución Pacto no reconstruye Avène, se añade como respaldo con referencia anual vs YTD actual;
  - no se inventa el dato.
- El resumen visual usa **PROTEGER / CONSOLIDAR / RECUPERAR**.
- Los gráficos de la ficha son estáticos para que no se desplacen al tocarlos.
- **Avène Solar usa Veeva como fuente operativa de unidades**.
- LOB Solar se muestra como contraste económico y la app avisa cuando la evolución en euros no corresponde directamente con la rotación en unidades.
- Solar no reduce el gap del acuerdo principal.
- El pedido es editable por:
  - Unidades
  - Descuento %
- La app calcula:
  - pedido bruto,
  - contribución estimada al acuerdo,
  - gap antes,
  - gap después,
  - simulación de gap por marca.
- Avène + Ducray + A-Derma se imputan al acuerdo principal.
- Dexeryl y Klorane se presentan como objetivos independientes cuando aparecen en la ficha.
- La propuesta sigue usando Veeva + catálogo y mantiene límites conservadores de unidades.

## Actualización en GitHub

Sustituir únicamente:

- `app.py`
- `README.md`
- `requirements.txt`
- `packages.txt`

No borrar LOB, COMPAR, `product_catalog.csv`, hojas de pedido, chuletas ni SELL_OUT.

## Prueba recomendada

Usar FONT SOLER PILAR con la misma Ficha 2026 y las mismas capturas Veeva ya utilizadas.
La ficha debe mostrar Avène aunque el OCR de Evolución Pacto no reconstruya su fila, y la propuesta debe recalcular el gap al editar unidades/descuento.
