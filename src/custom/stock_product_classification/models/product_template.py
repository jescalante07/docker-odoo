# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    """
    Extensión de product.template para añadir la relación
    many2many con stock.operation.tag.
    """
    _inherit = 'product.template'

    # ─── Relación many2many con etiquetas operativas ──────────────────────────

    operation_tag_ids = fields.Many2many(
        comodel_name='stock.operation.tag',
        relation='product_template_stock_operation_tag_rel',
        column1='product_template_id',
        column2='tag_id',
        string='Etiquetas Operativas',
        domain=[('active', '=', True)],
        help='Etiquetas operativas asignadas a este producto para clasificación '
             'en picking, almacenamiento y despacho.',
    )

    operation_tag_count = fields.Integer(
        string='Nº Etiquetas',
        compute='_compute_operation_tag_count',
        store=True,
    )

    primary_operation_type = fields.Selection(
        selection=[
            ('picking', 'Picking / Recolección'),
            ('storage', 'Almacenamiento'),
            ('dispatch', 'Despacho / Salida'),
            ('reception', 'Recepción / Entrada'),
            ('quality', 'Control de Calidad'),
            ('other', 'Otro'),
            ('mixed', 'Mixto'),
            ('unclassified', 'Sin Clasificar'),
        ],
        string='Tipo de Operación Principal',
        compute='_compute_primary_operation_type',
        store=True,
        help='Tipo de operación predominante basado en las etiquetas asignadas.',
    )

    # ─── Métodos computados ───────────────────────────────────────────────────

    @api.depends('operation_tag_ids')
    def _compute_operation_tag_count(self):
        for product in self:
            product.operation_tag_count = len(product.operation_tag_ids)

    @api.depends('operation_tag_ids', 'operation_tag_ids.operation_type')
    def _compute_primary_operation_type(self):
        """
        Calcula el tipo de operación predominante.
        Si hay un único tipo → ese tipo.
        Si hay múltiples tipos distintos → 'mixed'.
        Si no hay etiquetas → 'unclassified'.
        """
        for product in self:
            tags = product.operation_tag_ids
            if not tags:
                product.primary_operation_type = 'unclassified'
                continue

            op_types = set(tags.mapped('operation_type'))
            if len(op_types) == 1:
                product.primary_operation_type = op_types.pop()
            else:
                product.primary_operation_type = 'mixed'

    # ─── Acciones rápidas ─────────────────────────────────────────────────────

    def action_quick_assign_tags(self):
        """
        Acción rápida para asignar/remover etiquetas operativas
        sin abrir el formulario completo del producto.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Etiquetas Operativas — {self.name}',
            'res_model': 'stock.operation.tag.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': self.id,
                'default_tag_ids': [(6, 0, self.operation_tag_ids.ids)],
            },
        }

    def action_remove_all_tags(self):
        """Acción rápida para remover todas las etiquetas operativas del producto."""
        for product in self:
            product.operation_tag_ids = [(5, 0, 0)]
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Etiquetas removidas',
                'message': f'Se removieron todas las etiquetas operativas de {len(self)} producto(s).',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_operation_tags(self):
        """Acción para ver las etiquetas operativas del producto."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Etiquetas Operativas',
            'res_model': 'stock.operation.tag',
            'view_mode': 'list,form',
            'domain': [('product_ids', 'in', self.ids)],
        }
