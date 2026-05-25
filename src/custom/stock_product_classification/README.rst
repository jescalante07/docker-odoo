==========
Inventario: Clasificación Operativa de Productos
==========

Objetivo: Permitir clasificar productos con etiquetas operativas para optimizar picking, almacenamiento y despacho. Criterios de Aceptación:
--------------------------------------

1. Nuevo modelo stock.operation.tag con campos: name , color , description , operation_type .
2. Relación many2many entre product.template y stock.operation.tag.
3. Vista kanban en inventario que muestre productos agrupados por etiquetas operativas o tipo de operación.
4. Acción rápida en la vista de producto para asignar o remover etiquetas sin abrir el formulario completo.
5. Prueba que valide la creación de etiquetas, su asignación a productos y su visualización en la vista kanban.
