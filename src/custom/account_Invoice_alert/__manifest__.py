# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
{
    "name": "Contabilidad: Alertas de Facturas con Riesgo de Cobro",
    "summary": "Crear un tablero simple para identificar facturas con alto riesgo de atraso en el cobro.",
    "license": "LGPL-3",
    "description": """
                * Nuevo modelo account.collection.alert.rule con campos: name , days_overdue , amount_min , risk_level .
                * Evaluación automática de facturas vencidas según los días de atraso y el monto pendiente.
                * Vista tablero con agrupación por nivel de riesgo (bajo, medio, alto).
                * Configuración accesible desde el menú de contabilidad para definir reglas de riesgo.
                * Prueba que valide la clasificación de facturas en el nivel de riesgo correcto y la visualización en el tablero.
    """,
    "author": "Jamie Escalante",
    "website": "mailto:jamie.escalante7@gmail.com",
    "category": "Accounting/Accounting",
    "version": "17.0.1.0.0",
    "depends": [
        "base",
        "account",
    ],

    "data": [
        "security/ir.model.access.csv",
        "data/collection_alert_rule_data.xml",
        "views/account_collection_alert_rule_views.xml",
        "views/account_collection_alert_views.xml",
        "views/account_collection_alert_menus.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
    },
    "installable": True,
    "application": True,
}