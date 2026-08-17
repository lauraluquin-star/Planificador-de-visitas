# Smart Visit Planner NEW · V1.0

Reinicio limpio. No depende de app.py/svp_core.py de V5.

## Fuentes y jerarquía
- LOB: objetivo y facturación oficial en euros.
- COMPAR: contraste YTD26 vs YTD25 por marca.
- Veeva: unidades por marca/gama/producto. Nunca se comparten datos entre gamas o marcas.
- Ficha 2026: acuerdo/rappel/condiciones del cliente (documento de apoyo).
- Hojas de pedido/tarifa: referencias reales para construir pedido.
- Chuletas + campañas compradas: palancas sell-out.

## Regla de seguridad
Si no existe dato Veeva de una gama, la app NO inventa histórico ni objetivo de unidades. Muestra "Dato Veeva no disponible".

## Instalación Streamlit Cloud
Subir TODO el contenido de esta carpeta a un repositorio NUEVO. Main file: app.py.
