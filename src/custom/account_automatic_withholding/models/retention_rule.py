# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountRetentionRule(models.Model):
    """
    Tabla de configuración de reglas de retención. Tambien se podria utilizar el maestro de impuestos
    """
    _name = 'account.retention.rule'
    _description = 'Regla de Retención Fiscal'
    _order = 'sequence asc, fiscal_profile asc, name asc'
    _rec_name = 'name'

    # ------------------------------------------------------------------
    # Campos de identificación
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Nombre',
        required=True,
        translate=True,
        index=True,
        help='Nombre descriptivo de la regla de retención.',
    )

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de evaluación. Menor número = mayor prioridad.',
    )

    active = fields.Boolean(
        string='Activo',
        default=True,
    )

    # ------------------------------------------------------------------
    # Configuración de aplicación
    # ------------------------------------------------------------------
    fiscal_profile = fields.Selection(
        selection=[
            ('standard', 'Estándar'),
            ('retention_agent', 'Agente de Retención'),
            ('exempt', 'Exento'),
            ('simplified', 'Régimen Simplificado'),
            ('special', 'Régimen Especial'),
        ],
        string='Perfil Fiscal Aplicable',
        required=True,
        index=True,
        help='Perfil fiscal del partner al que aplica esta regla.',
    )

    retention_type = fields.Selection(
        selection=[
            ('sale', 'Ventas'),
            ('purchase', 'Compras'),
        ],
        string='Tipo de Retención',
        required=True,
        default='sale',
        help='Indica si aplica en facturas de venta o de compra.',
    )

    retention_basis = fields.Selection(
        selection=[
            ('tax_amount', 'Sobre el Monto del Impuesto'),
            ('subtotal', 'Sobre el Subtotal (Base Imponible)'),
            ('total', 'Sobre el Total de la Factura'),
        ],
        string='Base de Cálculo',
        required=True,
        default='tax_amount',
        help=(
            '• Sobre el impuesto: % aplicado sobre el monto de IVA/impuesto.\n'
            '• Sobre el subtotal: % aplicado sobre la base imponible.\n'
            '• Sobre el total: % aplicado sobre el total de la factura.'
        ),
    )

    # ------------------------------------------------------------------
    # Porcentaje y cuenta contable
    # ------------------------------------------------------------------
    percentage = fields.Float(
        string='Porcentaje (%)',
        required=True,
        digits=(5, 4),
        help='Porcentaje de retención a aplicar (ej: 15.00 para 15%).',
    )

    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        relation='retention_rule_tax_rel',
        column1='rule_id',
        column2='tax_id',
        string='Impuestos Aplicables',
        help='Si se especifican impuestos, la retención solo aplica '
             'cuando la factura contenga alguno de ellos. '
             'Si se deja vacío, aplica a todas las facturas.',
    )

    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta Contable de Retención',
        required=True,
        domain="[('deprecated', '=', False)]",
        help='Cuenta contable donde se registra el asiento de retención.',
    )

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario',
        domain="[('type', 'in', ['general', 'sale', 'purchase'])]",
        help='Diario contable para los asientos de retención. '
             'Si no se define, se usará el diario de la factura.',
    )

    # ------------------------------------------------------------------
    # Descripción generada automáticamente
    # ------------------------------------------------------------------
    description = fields.Char(
        string='Descripción en Retención',
        translate=True,
        help='Texto que aparecerá en las líneas de retención generadas.',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        index=True,
    )

    # ------------------------------------------------------------------
    # Campos computados de resumen
    # ------------------------------------------------------------------
    partner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='partner_retention_rule_rel',
        column1='rule_id',
        column2='partner_id',
        string='Partners Específicos',
        help='Partners que tienen esta regla asignada directamente.',
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('percentage')
    def _check_percentage(self):
        for rule in self:
            if not (0 < rule.percentage <= 100):
                raise ValidationError(
                    _('El porcentaje debe estar entre 0.01 y 100. '
                      'Valor recibido: %s') % rule.percentage
                )

    # ------------------------------------------------------------------
    # Métodos de negocio
    # ------------------------------------------------------------------
    def compute_retention_amount(self, invoice):
        """
        Calcula el monto de retención para una factura
        """
        self.ensure_one()

        base_amount = 0.0

        if self.retention_basis == 'tax_amount':
            # Solo sobre impuestos coincidentes
            if self.tax_ids:
                base_amount = sum(
                    line.amount_currency
                    for line in invoice.line_ids
                    if line.tax_line_id and line.tax_line_id in self.tax_ids
                )
            else:
                base_amount = sum(
                    line.amount_currency
                    for line in invoice.line_ids
                    if line.tax_line_id
                )
            # El monto de impuesto viene en negativo en facturas de venta
            base_amount = abs(base_amount)

        elif self.retention_basis == 'subtotal':
            if self.tax_ids:
                # Subtotal de líneas que contengan los impuestos especificados
                base_amount = sum(
                    line.price_subtotal
                    for line in invoice.invoice_line_ids
                    if any(t in self.tax_ids for t in line.tax_ids)
                )
            else:
                base_amount = invoice.amount_untaxed

        elif self.retention_basis == 'total':
            base_amount = invoice.amount_total

        retention_amount = base_amount * (self.percentage / 100.0)
        return self.env.company.currency_id.round(retention_amount)

    def matches_invoice(self, invoice):
        """
        Verifica si esta regla aplica a la factura
        """
        self.ensure_one()
        # Si no hay filtro por impuesto, aplica siempre
        if not self.tax_ids:
            return True
        # Verificar que la factura tenga alguno de los impuestos de la regla
        invoice_taxes = invoice.invoice_line_ids.mapped('tax_ids')
        return bool(self.tax_ids & invoice_taxes)

    def name_get(self):
        result = []
        profile_map = dict(
            self._fields['fiscal_profile'].selection
        )
        type_map = dict(self._fields['retention_type'].selection)
        for rule in self:
            label = (
                f'{rule.name} '
                f'[{profile_map.get(rule.fiscal_profile, "")} | '
                f'{type_map.get(rule.retention_type, "")} | '
                f'{rule.percentage}%]'
            )
            result.append((rule.id, label))
        return result
