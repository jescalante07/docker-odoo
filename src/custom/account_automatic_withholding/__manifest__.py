# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
{
    "name": "Contabilidad: Retenciones Automáticas por Perfil Fiscal",
    "summary": "Aplicar retenciones automáticas en facturas según el perfil fiscal del cliente.",
    "license": "LGPL-3",
    "description": """
                * Campo “perfil fiscal” en res.partner (ejemplo: estándar, agente de retención, exento).
                * Configuración de retenciones mediante una tabla de reglas.
                * Aplicación automática de la retención en la factura ( account.move ) al confirmar o validar el documento.
                * Vista de configuración accesible desde el menú de contabilidad.
                * Prueba que valide facturas con y sin retención, incluyendo casos límite (ej. cliente sin perfil fiscal definido o sin regla asociada).
    """,
    "author": "Jamie Escalante",
    "website": "mailto:jamie.escalante7@gmail.com",
    "category": "Accounting/Accounting",
    "version": "17.0.1.0.0",
    "depends": [
        "base",
        "account",
        "mail",
    ],

    "data": [
        'security/ir.model.access.csv',
        'data/account_retention_sequence_data.xml',
        'data/retention_rule_data.xml',
        'views/retention_rule_views.xml',
        'views/account_retention_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/menu_views.xml',
    ],
    "images": ["static/description/icon.png"],
    "assets": {
    },
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}