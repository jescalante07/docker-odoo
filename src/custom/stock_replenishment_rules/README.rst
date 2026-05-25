==========
Inventario: Reglas de Reabastecimiento por Prioridad
==========

Objetivo: Automatizar la priorización de productos para reabastecimiento interno según criticidad operativa. Criterios de Aceptación:
--------------------------------------

1. Campo “prioridad de reabastecimiento” en product.template (ejemplo: baja, media, alta).
2. Campo “stock objetivo” en product.template.
3. Acción automática que identifique productos con qty_available por debajo del stock objetivo y genere unaactividad ( mail.activity ) para el responsable del almacén.
4. Vista de lista o tablero en inventario que muestre los productos pendientes de reabastecimiento, agrupados por prioridad.
5. Prueba que valide la creación de actividades para productos por debajo del stock objetivo y que no se creen duplicados innecesarios para el mismo producto.
