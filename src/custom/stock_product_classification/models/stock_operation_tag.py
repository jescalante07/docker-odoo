# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StockOperationTag(models.Model):
    """
    Etiquetas operativas para clasificar productos en inventario.
    Permite agrupar productos por tipo de operación para optimizar
    picking, almacenamiento y despacho.
    """
    _name = 'stock.operation.tag'
    _description = 'Etiqueta Operativa de Stock'
    _order = 'operation_type, name'
    _rec_name = 'name'

    # ─── Campos principales ───────────────────────────────────────────────────

    name = fields.Char(
        string='Nombre',
        required=True,
        translate=True,
        help='Nombre descriptivo de la etiqueta operativa.',
    )

    color = fields.Integer(
        string='Color',
        default=0,
        help='Índice de color para identificación visual (0-11).',
    )

    description = fields.Text(
        string='Descripción',
        translate=True,
        help='Descripción detallada del uso y propósito de esta etiqueta.',
    )

    operation_type = fields.Selection(
        selection=[
            ('picking', 'Picking / Recolección'),
            ('storage', 'Almacenamiento'),
            ('dispatch', 'Despacho / Salida'),
            ('reception', 'Recepción / Entrada'),
            ('quality', 'Control de Calidad'),
            ('other', 'Otro'),
        ],
        string='Tipo de Operación',
        required=True,
        default='picking',
        index=True,
        help='Categoría operativa principal a la que pertenece esta etiqueta.',
    )

    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desactivado, la etiqueta no aparecerá en las vistas activas.',
    )

    # ─── Campos relacionales ──────────────────────────────────────────────────

    product_ids = fields.Many2many(
        comodel_name='product.template',
        relation='product_template_stock_operation_tag_rel',
        column1='tag_id',
        column2='product_template_id',
        string='Productos',
        help='Productos que tienen asignada esta etiqueta operativa.',
    )

    # ─── Campos computados ────────────────────────────────────────────────────

    product_count = fields.Integer(
        string='Nº Productos',
        compute='_compute_product_count',
        store=True,
        help='Número de productos que tienen asignada esta etiqueta.',
    )

    # ─── Métodos computados ───────────────────────────────────────────────────

    @api.depends('product_ids')
    def _compute_product_count(self):
        for tag in self:
            tag.product_count = len(tag.product_ids)

    # ─── Constraints ─────────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'name_operation_type_unique',
            'UNIQUE(name, operation_type)',
            'Ya existe una etiqueta con ese nombre para el mismo tipo de operación.',
        ),
    ]

    @api.constrains('color')
    def _check_color_range(self):
        for tag in self:
            if not (0 <= tag.color <= 11):
                raise ValidationError(
                    'El color debe ser un índice entre 0 y 11.'
                )

    # ─── Métodos de negocio ───────────────────────────────────────────────────

    def action_view_products(self):
        """Acción para ver todos los productos asociados a esta etiqueta."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Productos - {self.name}',
            'res_model': 'product.template',
            'view_mode': 'kanban,list,form',
            'domain': [('operation_tag_ids', 'in', self.ids)],
            'context': {
                'default_operation_tag_ids': [(4, self.id)],
                'search_default_operation_tag_ids': self.id,
            },
        }

    def get_operation_type_label(self):
        """Retorna el label legible del tipo de operación."""
        self.ensure_one()
        selection_dict = dict(self._fields['operation_type'].selection)
        return selection_dict.get(self.operation_type, self.operation_type)
