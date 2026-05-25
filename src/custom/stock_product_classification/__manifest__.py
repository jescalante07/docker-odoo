# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
{
    "name": "Inventario: Clasificación Operativa de Productos",
    "summary": "Permitir clasificar productos con etiquetas operativas para optimizar picking, almacenamiento y despacho.",
    "license": "LGPL-3",
    "description": """
                * Nuevo modelo stock.operation.tag con campos: name , color , description , operation_type .
                    Relación many2many entre product.template y stock.operation.tag .
                * Vista kanban en inventario que muestre productos agrupados por etiquetas operativas o tipo de operación.
                * Acción rápida en la vista de producto para asignar o remover etiquetas sin abrir el formulario completo.
                * Prueba que valide la creación de etiquetas, su asignación a productos y su visualización en la vista kanban.
    """,
    "author": "Jamie Escalante",
    "website": "mailto:jamie.escalante7@gmail.com",
    "category": "Inventory/Inventory",
    "version": "17.0.1.0.0",
    "depends": [
        "base",
        "product",
        "stock",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/stock_operation_tag_views.xml",
        "views/product_template_views.xml",
        "views/product_kanban_views.xml",
        # "wizard/assign_operation_tag_views.xml",
    ],
    "demo": [
        "demo/stock_operation_tag_demo.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
    },
    "installable": True,
    "application": True,
}
