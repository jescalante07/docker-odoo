# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AssignOperationTagWizard(models.TransientModel):
    """
    Wizard de acción rápida para asignar o remover etiquetas operativas
    a un producto sin necesidad de abrir el formulario completo.
    """
    _name = 'stock.operation.tag.wizard'
    _description = 'Asignar Etiquetas Operativas'

    product_id = fields.Many2one(
        comodel_name='product.template',
        string='Producto',
        required=True,
        readonly=True,
        ondelete='cascade',
    )

    product_name = fields.Char(
        related='product_id.name',
        string='Nombre del Producto',
        readonly=True,
    )

    tag_ids = fields.Many2many(
        comodel_name='stock.operation.tag',
        relation='wizard_operation_tag_rel',
        column1='wizard_id',
        column2='tag_id',
        string='Etiquetas Operativas',
        domain=[('active', '=', True)],
        help='Selecciona las etiquetas operativas a asignar al producto.',
    )

    # Filtros por tipo para facilitar selección masiva
    filter_operation_type = fields.Selection(
        selection=[
            ('all', 'Todas'),
            ('picking', 'Picking / Recolección'),
            ('storage', 'Almacenamiento'),
            ('dispatch', 'Despacho / Salida'),
            ('reception', 'Recepción / Entrada'),
            ('quality', 'Control de Calidad'),
            ('other', 'Otro'),
        ],
        string='Filtrar por Tipo',
        default='all',
    )

    available_tag_ids = fields.Many2many(
        comodel_name='stock.operation.tag',
        relation='wizard_available_tag_rel',
        column1='wizard_id',
        column2='tag_id',
        string='Etiquetas Disponibles',
        compute='_compute_available_tags',
    )

    notes = fields.Text(
        string='Notas',
        help='Notas internas sobre la asignación de etiquetas.',
    )

    @api.depends('filter_operation_type')
    def _compute_available_tags(self):
        for wizard in self:
            domain = [('active', '=', True)]
            if wizard.filter_operation_type and wizard.filter_operation_type != 'all':
                domain.append(('operation_type', '=', wizard.filter_operation_type))
            wizard.available_tag_ids = self.env['stock.operation.tag'].search(domain)

    def action_apply(self):
        """Aplica las etiquetas seleccionadas al producto."""
        self.ensure_one()
        self.product_id.operation_tag_ids = [(6, 0, self.tag_ids.ids)]
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Etiquetas actualizadas',
                'message': f'Se asignaron {len(self.tag_ids)} etiqueta(s) a "{self.product_id.name}".',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_add_by_type(self):
        """Agrega todas las etiquetas del tipo filtrado seleccionado."""
        self.ensure_one()
        if self.filter_operation_type and self.filter_operation_type != 'all':
            tags_of_type = self.env['stock.operation.tag'].search([
                ('operation_type', '=', self.filter_operation_type),
                ('active', '=', True),
            ])
            self.tag_ids = [(4, tag.id) for tag in tags_of_type]

    def action_clear_tags(self):
        """Limpia todas las etiquetas seleccionadas en el wizard."""
        self.ensure_one()
        self.tag_ids = [(5, 0, 0)]
