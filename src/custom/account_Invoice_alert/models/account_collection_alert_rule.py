# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountCollectionAlertRule(models.Model):
    _name = 'account.collection.alert.rule'
    _description = 'Regla de Alerta de Cobro'
    _order = 'days_overdue asc, amount_min asc'

    name = fields.Char(
        string='Nombre de la Regla',
        required=True,
        help='Nombre descriptivo de la regla de riesgo de cobro',
    )
    days_overdue = fields.Integer(
        string='Días de Atraso',
        required=True,
        default=0,
        help='Número mínimo de días de atraso para aplicar esta regla',
    )
    amount_min = fields.Float(
        string='Monto Mínimo',
        required=True,
        default=0.0,
        help='Monto mínimo pendiente de cobro para aplicar esta regla',
    )
    risk_level = fields.Selection(
        selection=[
            ('low', 'Bajo'),
            ('medium', 'Medio'),
            ('high', 'Alto'),
        ],
        string='Nivel de Riesgo',
        required=True,
        default='low',
        help='Nivel de riesgo asignado cuando se cumplen los criterios de esta regla',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
    )
    description = fields.Text(
        string='Descripción',
        help='Descripción adicional de la regla',
    )
    alert_count = fields.Integer(
        string='Facturas en Alerta',
        compute='_compute_alert_count',
        help='Número de facturas actualmente clasificadas con este nivel de riesgo',
    )

    @api.depends('risk_level')
    def _compute_alert_count(self):
        for rule in self:
            rule.alert_count = self.env['account.collection.alert'].search_count([
                ('rule_id', '=', rule.id),
                ('state', '=', 'open'),
            ])

    @api.constrains('days_overdue')
    def _check_days_overdue(self):
        for rule in self:
            if rule.days_overdue < 0:
                raise ValidationError('Los días de atraso no pueden ser negativos.')

    @api.constrains('amount_min')
    def _check_amount_min(self):
        for rule in self:
            if rule.amount_min < 0:
                raise ValidationError('El monto mínimo no puede ser negativo.')

    def name_get(self):
        result = []
        risk_labels = {'low': 'Bajo', 'medium': 'Medio', 'high': 'Alto'}
        for rule in self:
            label = risk_labels.get(rule.risk_level, rule.risk_level)
            result.append((rule.id, f'{rule.name} [{label}]'))
        return result
