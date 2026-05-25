# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """
    Extensión de res.partner para añadir el perfil fiscal
    """
    _inherit = 'res.partner'

    # ------------------------------------------------------------------
    # Campo principal: Perfil Fiscal
    # ------------------------------------------------------------------
    fiscal_profile = fields.Selection(
        selection=[
            ('standard', 'Estándar'),
            ('retention_agent', 'Agente de Retención'),
            ('exempt', 'Exento'),
            ('simplified', 'Régimen Simplificado'),
            ('special', 'Régimen Especial'),
        ],
        string='Perfil Fiscal',
        default='standard',
        index=True,
        tracking=True,
        help=(
            'Perfil fiscal del contacto que determina qué retenciones aplican:\n'
            '• Estándar: cliente/proveedor normal sin obligaciones especiales.\n'
            '• Agente de Retención: obligado a retener impuestos en la fuente.\n'
            '• Exento: no sujeto a retenciones fiscales.\n'
            '• Régimen Simplificado: régimen tributario simplificado.\n'
            '• Régimen Especial: régimen tributario especial con reglas propias.'
        ),
    )

    fiscal_profile_note = fields.Text(
        string='Notas Fiscales',
        help='Observaciones adicionales sobre el perfil fiscal del contacto.',
    )

    retention_rule_ids = fields.Many2many(
        comodel_name='account.retention.rule',
        relation='partner_retention_rule_rel',
        column1='partner_id',
        column2='rule_id',
        string='Reglas de Retención Específicas',
        help='Reglas de retención exclusivas para este contacto. '
             'Si se definen aquí, tienen prioridad sobre las del perfil fiscal.',
    )

    retention_count = fields.Integer(
        string='Retenciones',
        compute='_compute_retention_count',
        help='Número de retenciones emitidas o recibidas para este contacto.',
    )

    # ------------------------------------------------------------------
    # Métodos computados
    # ------------------------------------------------------------------
    @api.depends('fiscal_profile')
    def _compute_retention_count(self):
        for partner in self:
            partner.retention_count = self.env['account.retention'].search_count([
                ('partner_id', 'in', [partner.id] + partner.child_ids.ids),
            ])

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_view_retentions(self):
        """Abre las retenciones del contacto."""
        self.ensure_one()
        return {
            'name': _('Retenciones de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.retention',
            'view_mode': 'list,form',
            'domain': [('partner_id', 'in', [self.id] + self.child_ids.ids)],
        }

    def _get_applicable_retention_rules(self, move_type):
        """
        Retorna las reglas de retención aplicables a este partner
        según su perfil fiscal y el tipo de movimiento contable.

        Prioridad:
        1. Reglas específicas del partner.
        2. Reglas genéricas del perfil fiscal.

        :param move_type: tipo de account.move ('out_invoice', 'in_invoice', etc.)
        :return: recordset de account.retention.rule
        """
        self.ensure_one()

        # Perfil exento: no aplica ninguna retención
        if self.fiscal_profile == 'exempt':
            return self.env['account.retention.rule'].browse()

        # Determinar el tipo de retención según el tipo de factura
        if move_type in ('out_invoice', 'out_refund'):
            retention_types = ['sale']
        elif move_type in ('in_invoice', 'in_refund'):
            retention_types = ['purchase']
        else:
            return self.env['account.retention.rule'].browse()

        base_domain = [
            ('active', '=', True),
            ('retention_type', 'in', retention_types),
        ]

        # 1. Reglas específicas del partner (máxima prioridad)
        if self.retention_rule_ids:
            return self.retention_rule_ids.filtered(
                lambda r: r.active and r.retention_type in retention_types
            )

        # 2. Reglas por perfil fiscal
        if self.fiscal_profile:
            profile_rules = self.env['account.retention.rule'].search(
                base_domain + [('fiscal_profile', '=', self.fiscal_profile)],
                order='sequence asc',
            )
            if profile_rules:
                return profile_rules

        return self.env['account.retention.rule'].browse()
