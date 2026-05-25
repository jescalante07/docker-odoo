# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountRetentionLine(models.Model):
    """
    Líneas del comprobante de retención fiscal.
    """
    _name = 'account.retention.line'
    _description = 'Línea de Retención Fiscal'
    _order = 'sequence asc, id asc'

    # ------------------------------------------------------------------
    # Relación con la cabecera
    # ------------------------------------------------------------------
    retention_id = fields.Many2one(
        comodel_name='account.retention',
        string='Retención',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ------------------------------------------------------------------
    # Identificación de la línea
    # ------------------------------------------------------------------
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de visualización dentro del comprobante.',
    )

    name = fields.Char(
        string='Descripción',
        required=True,
        help='Descripción del concepto de retención.',
    )

    # ------------------------------------------------------------------
    # Regla de origen
    # ------------------------------------------------------------------
    rule_id = fields.Many2one(
        comodel_name='account.retention.rule',
        string='Regla Aplicada',
        readonly=True,
        help='Regla de retención que originó esta línea.',
    )

    fiscal_profile = fields.Selection(
        related='retention_id.fiscal_profile',
        string='Perfil Fiscal',
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Impuesto origen (referencia)
    # ------------------------------------------------------------------
    tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Impuesto Retenido',
        help='Impuesto sobre el cual se calculó la retención.',
    )

    retention_basis = fields.Selection(
        selection=[
            ('tax_amount', 'Sobre Impuesto'),
            ('subtotal', 'Sobre Subtotal'),
            ('total', 'Sobre Total'),
        ],
        string='Base de Cálculo',
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Montos
    # ------------------------------------------------------------------
    currency_id = fields.Many2one(
        related='retention_id.currency_id',
        string='Moneda',
        readonly=True,
    )

    base_amount = fields.Monetary(
        string='Base',
        currency_field='currency_id',
        help='Monto base sobre el cual se calculó la retención.',
    )

    percentage = fields.Float(
        string='Porcentaje (%)',
        digits=(5, 4),
        help='Porcentaje de retención aplicado.',
    )

    amount = fields.Monetary(
        string='Monto Retenido',
        currency_field='currency_id',
        required=True,
        help='Monto total retenido en esta línea.',
    )

    # ------------------------------------------------------------------
    # Cuenta contable
    # ------------------------------------------------------------------
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta Contable',
        required=True,
        domain="[('deprecated', '=', False)]",
        help='Cuenta contable donde se registra esta línea de retención.',
    )

    # ------------------------------------------------------------------
    # Estado derivado de la cabecera
    # ------------------------------------------------------------------
    state = fields.Selection(
        related='retention_id.state',
        string='Estado',
        readonly=True,
        store=True,
    )

    partner_id = fields.Many2one(
        related='retention_id.partner_id',
        string='Partner',
        readonly=True,
        store=True,
    )

    date = fields.Date(
        related='retention_id.date',
        string='Fecha',
        readonly=True,
        store=True,
    )

    invoice_id = fields.Many2one(
        related='retention_id.invoice_id',
        string='Factura',
        readonly=True,
        store=True,
    )

    company_id = fields.Many2one(
        related='retention_id.company_id',
        string='Compañía',
        readonly=True,
        store=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(
                    _('El monto retenido no puede ser negativo en la línea "%s".') % line.name
                )

    @api.constrains('percentage')
    def _check_percentage(self):
        for line in self:
            if line.percentage and not (0 < line.percentage <= 100):
                raise ValidationError(
                    _('El porcentaje debe estar entre 0 y 100 en la línea "%s".') % line.name
                )

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------
    @api.onchange('base_amount', 'percentage')
    def _onchange_compute_amount(self):
        """Recalcula el monto cuando cambia la base o el porcentaje."""
        for line in self:
            if line.base_amount and line.percentage:
                line.amount = line.currency_id.round(
                    line.base_amount * (line.percentage / 100.0)
                )

    @api.onchange('rule_id')
    def _onchange_rule_id(self):
        """Rellena campos automáticamente al seleccionar una regla."""
        for line in self:
            if line.rule_id:
                line.account_id = line.rule_id.account_id
                line.percentage = line.rule_id.percentage
                line.retention_basis = line.rule_id.retention_basis
                if not line.name:
                    line.name = line.rule_id.description or line.rule_id.name
