# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
{
    "name": "Punto de Venta: Reglas de Descuento por Horario",
    "summary": "Aplicar descuentos automáticos en el punto de venta según franjas horarias configurables.",
    "license": "LGPL-3",
    "description": """
                * Nuevo modelo de configuración para definir reglas con campos como: name , hour_from , hour_to , discount_percentage.
                * Aplicación automática del descuento en una orden de pos.order cuando la venta se registre dentro del horario
                    definido.
                * Validación para evitar que se apliquen múltiples descuentos incompatibles sobre la misma orden.
                * Vista de configuración accesible desde el menú de punto de venta.
                * Prueba que valide órdenes con y sin descuento, incluyendo casos límite (ej. orden fuera del rango horario o reglas
                `   solapadas).
    """,
    "author": "Jamie Escalante",
    "website": "mailto:jamie.escalante7@gmail.com",
    "category": "Sales/Point of Sale",
    "version": "17.0.1.0.0",
    "depends": [
        "base",
        "point_of_sale",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/pos_discount_rule_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_discount_rules/static/src/js/pos_happy_hour.js",
        ],
    },
    "installable": True,
    "application": True,
}