# Smart Visit Planner · V2.1

Mejoras respecto a V2:
- Los archivos de ciclo que están en GitHub se cargan automáticamente al abrir la app.
- No hay que adjuntar LOB/COMPAR/tarifa cada vez.
- COMPAR admite varios archivos simultáneamente.
- LOB, COMPAR y tarifa admiten Excel normal `.xlsx`/`.xls` además de CSV.
- La pantalla Gestión de ciclo muestra qué archivos permanentes detecta en GitHub.
- La Ficha 2026 sigue siendo la fuente del objetivo del acuerdo.
- LOB/COMPAR se usan como contraste económico.
- Veeva se usa para unidades, gamas y oportunidades.
- Se mantiene la consolidación por punto de venta físico ante cambios de titular/CPV.

## Uso recomendado

### Día a día
1. Abrir la app.
2. Elegir Visita individual.
3. Buscar el punto de venta.
4. Adjuntar Ficha 2026 y capturas Veeva si están disponibles.
5. Leer Plan de visita.

### Cambio de ciclo (~cada 2,5 meses)
1. Probar los nuevos archivos en Gestión de ciclo.
2. Validar que la app los lee bien.
3. Subir a GitHub los archivos definitivos del nuevo ciclo:
   - LOB
   - uno o varios COMPAR
   - tarifa / catálogo
   - hojas de pedido
   - chuleta / condiciones
   - sell-out
4. Desde ese momento se cargan solos en cada apertura.
