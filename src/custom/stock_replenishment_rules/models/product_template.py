# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

_MODULE_NAME = 'stock_replenishment_rules'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    replenishment_priority = fields.Selection(
        selection=[
            ('low', 'Baja'),
            ('medium', 'Media'),
            ('high', 'Alta'),
        ],
        string='Prioridad de Reabastecimiento',
        default='low',
        required=True,
        tracking=True,
        help='Define la criticidad operativa del producto para su reabastecimiento. '
             'Alta: producto crítico para operaciones; Media: importante pero no crítico; '
             'Baja: puede esperar reabastecimiento normal.',
    )

    target_stock = fields.Float(
        string='Stock Objetivo',
        default=0.0,
        digits='Product Unit of Measure',
        tracking=True,
        help='Cantidad mínima que debe mantenerse en stock. Cuando el stock disponible '
             'cae por debajo de este valor, se genera una actividad de reabastecimiento.',
    )

    needs_replenishment = fields.Boolean(
        string='Necesita Reabastecimiento',
        compute='_compute_needs_replenishment',
        store=True,
        help='Indica si el producto necesita reabastecimiento basado en el stock disponible '
             'vs el stock objetivo.',
    )

    replenishment_activity_count = fields.Integer(
        string='Actividades de Reabastecimiento',
        compute='_compute_replenishment_activity_count',
        help='Número de actividades de reabastecimiento pendientes para este producto.',
    )

    @api.depends('qty_available', 'target_stock', 'type')
    def _compute_needs_replenishment(self):
        """Calcula si el producto necesita reabastecimiento comparando
        el stock disponible con el stock objetivo."""
        for product in self:
            if product.type != 'service' and product.target_stock > 0:
                product.needs_replenishment = product.qty_available < product.target_stock
            else:
                product.needs_replenishment = False

    def _compute_replenishment_activity_count(self):
        """Cuenta las actividades de reabastecimiento pendientes por producto."""
        activity_type = self.env.ref(
            f'{_MODULE_NAME}.mail_activity_type_replenishment',
            raise_if_not_found=False,
        )
        for product in self:
            if activity_type:
                count = self.env['mail.activity'].search_count([
                    ('res_model', '=', 'product.template'),
                    ('res_id', '=', product.id),
                    ('activity_type_id', '=', activity_type.id),
                ])
                product.replenishment_activity_count = count
            else:
                product.replenishment_activity_count = 0

    @api.constrains('target_stock')
    def _check_target_stock(self):
        """Valida que el stock objetivo no sea negativo."""
        for product in self:
            if product.target_stock < 0:
                raise ValidationError(
                    _('El stock objetivo no puede ser negativo para el producto "%s".') % product.name
                )

    def action_view_replenishment_activities(self):
        """Abre la vista de actividades de reabastecimiento del producto."""
        self.ensure_one()
        activity_type = self.env.ref(
            f'{_MODULE_NAME}.mail_activity_type_replenishment',
            raise_if_not_found=False,
        )
        domain = [
            ('res_model', '=', 'product.template'),
            ('res_id', '=', self.id),
        ]
        if activity_type:
            domain.append(('activity_type_id', '=', activity_type.id))

        return {
            'name': _('Actividades de Reabastecimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.activity',
            'view_mode': 'list,form',
            'domain': domain,
        }
