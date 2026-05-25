# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
{
    "name": "Inventario: Reglas de Reabastecimiento por Prioridad",
    "summary": "Automatizar la priorización de productos para reabastecimiento interno según criticidad operativa.",
    "license": "LGPL-3",
    "description": """
                * Campo “prioridad de reabastecimiento” en product.template (ejemplo: baja, media, alta).
                * Campo “stock objetivo” en product.template.
                * Acción automática que identifique productos con qty_available por debajo del stock objetivo y genere una
                    actividad ( mail.activity ) para el responsable del almacén.
                * Vista de lista o tablero en inventario que muestre los productos pendientes de reabastecimiento, agrupados por prioridad.
                * Prueba que valide la creación de actividades para productos por debajo del stock objetivo y que no se creen duplicados
                    innecesarios para el mismo producto.
    """,
    "author": "Jamie Escalante",
    "website": "mailto:jamie.escalante7@gmail.com",
    "category": "Inventory/Inventory",
    "version": "17.0.1.0.0",
    "depends": [
        "base",
        "product",
        "stock",
        "mail",
    ],

    "data": [
        "security/ir.model.access.csv",
        "data/mail_activity_type_data.xml",
        "data/ir_cron_data.xml",
        "views/product_template_views.xml",
        "views/stock_replenishment_views.xml",
        "views/menu_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
    },
    "installable": True,
    "application": True,
}
