==========
Contabilidad: Alertas de Facturas con Riesgo de Cobro
==========

Objetivo: Crear un tablero simple para identificar facturas con alto riesgo de atraso en el cobro. Criterios de Aceptación:
--------------------------------------

1. Nuevo modelo account.collection.alert.rule con campos: name , days_overdue , amount_min , risk_level.
2. Evaluación automática de facturas vencidas según los días de atraso y el monto pendiente.
3. Vista tablero con agrupación por nivel de riesgo (bajo, medio, alto).
4. Configuración accesible desde el menú de contabilidad para definir reglas de riesgo.
5. Prueba que valide la clasificación de facturas en el nivel de riesgo correcto y la visualización en el tablero.
