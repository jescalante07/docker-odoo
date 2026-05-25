==========
Contabilidad: Retenciones Automáticas por Perfil Fiscal
==========

Objetivo: Aplicar retenciones automáticas en facturas según el perfil fiscal del cliente. Criterios de Aceptación:
--------------------------------------

1. Campo “perfil fiscal” en res.partner (ejemplo: estándar, agente de retención, exento).
2. Configuración de retenciones mediante una tabla de reglas.
3. Aplicación automática de la retención en la factura ( account.move ) al confirmar o validar el documento.
4. Vista de configuración accesible desde el menú de contabilidad.
5. Prueba que valide facturas con y sin retención, incluyendo casos límite (ej. cliente sin perfil fiscal definido o sin regla asociada).
