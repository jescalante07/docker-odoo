==========
Punto de Venta: Reglas de Descuento por Horario
==========

Objetivo: Aplicar descuentos automáticos en el punto de venta según franjas horarias configurables. Criterios de Aceptación:
--------------------------------------

1. Nuevo modelo de configuración para definir reglas con campos como: name , hour_from , hour_to , discount_percentage .
2. Aplicación automática del descuento en una orden de pos.order cuando la venta se registre dentro del horario definido.
3. Validación para evitar que se apliquen múltiples descuentos incompatibles sobre la misma orden.
4. Vista de configuración accesible desde el menú de punto de venta.
5. Prueba que valide órdenes con y sin descuento, incluyendo casos límite (ej. orden fuera del rango horario o reglas solapadas).
