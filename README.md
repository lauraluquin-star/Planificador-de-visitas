# Smart Visit Planner

App para delegados comerciales de Avène, Ducray, A-Derma y Dexeryl (grupo Pierre Fabre): prepara
visitas a farmacias con evolución del cliente, gaps vs. pactos comerciales, propuesta de pedido
editable y simulación de impacto. Uso principal: iPad.

Ver `CLAUDE.md` y `docs/00_SPEC_MAESTRA.md` para las reglas de negocio y la spec funcional completa
-- son la fuente de verdad del proyecto.

## Estado actual

- `src/parsers/`: parsers reales sobre datos de Laura Luquin Franquet (LOB, COMPAR, catálogo/tarifa,
  Acuerdos Comerciales LIVE).
- `src/engine/comparacion.py`: motor de comparación reutilizable (consolidación por identidad física,
  evolución vs. año anterior, objetivo real de pacto, detección de pérdidas ADA/Dexeryl separadas).
- `scripts/`: generación de la Vista de Grupo (cartera consolidada, selección múltiple, ficha de
  visita por farmacia) como artefacto HTML autocontenido.
- `docs/`: datos reales de ciclo (LOB, COMPAR, catálogo, hojas de pedido, chuletas, acuerdos
  comerciales, ejemplos de Ficha Cliente 2026 y Veeva).

## Próximo paso: app multi-delegado

Este proyecto está migrando de artefactos generados a mano a una aplicación real donde cualquier
delegado pueda subir su Ficha 2026 y capturas de Veeva y tener su preparación de visita al
instante, con actualización periódica (mensual/bimensual) de LOB, condiciones comerciales y hojas
de pedido compartidas entre todos los delegados. En desarrollo.
