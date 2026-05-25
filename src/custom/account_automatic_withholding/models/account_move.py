# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """
    Extensión de account.move para aplicar retenciones automáticas
    al confirmar/validar facturas según el perfil fiscal del partner.
    """
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Campos de retención en la factura
    # ------------------------------------------------------------------
    retention_ids = fields.One2many(
        comodel_name='account.retention',
        inverse_name='invoice_id',
        string='Retenciones',
        readonly=True,
        copy=False,
    )

    retention_count = fields.Integer(
        string='Nº Retenciones',
        compute='_compute_retention_count',
    )

    total_retention_amount = fields.Monetary(
        string='Total Retenido',
        compute='_compute_total_retention_amount',
        currency_field='currency_id',
        help='Suma de todos los montos retenidos en las retenciones asociadas.',
    )

    has_retention = fields.Boolean(
        string='Tiene Retención',
        compute='_compute_retention_count',
        store=True,
    )

    skip_auto_retention = fields.Boolean(
        string='Omitir Retención Automática',
        copy=False,
        help='Si está marcado, no se aplicarán retenciones automáticas al validar.',
    )

    # ------------------------------------------------------------------
    # Computados
    # ------------------------------------------------------------------
    @api.depends('retention_ids')
    def _compute_retention_count(self):
        for move in self:
            count = len(move.retention_ids)
            move.retention_count = count
            move.has_retention = count > 0

    @api.depends('retention_ids.amount_total')
    def _compute_total_retention_amount(self):
        for move in self:
            move.total_retention_amount = sum(
                r.amount_total for r in move.retention_ids
            )

    # ------------------------------------------------------------------
    # Override de action_post: aplicar retenciones al confirmar
    # ------------------------------------------------------------------
    def action_post(self):
        """
        Sobrescribe el método de confirmación de factura.
        Después de contabilizar la factura, aplica retenciones automáticas
        según el perfil fiscal del partner.
        """
        # Llamar al método original primero
        result = super().action_post()

        # Aplicar retenciones en facturas recién confirmadas
        for move in self:
            if move._should_apply_auto_retention():
                move._apply_auto_retention()

        return result

    # ------------------------------------------------------------------
    # Lógica de retención automática
    # ------------------------------------------------------------------
    def _should_apply_auto_retention(self):
        """
        Determina si debe aplicarse retención automática a esta factura.
        Condiciones:
        - Es una factura (no pago, ni asiento manual).
        - Tiene partner con perfil fiscal definido.
        - El perfil no es 'exento'.
        - No tiene ya retenciones generadas.
        - No está marcada para omitir retención.
        - Está en estado 'posted'.
        """
        self.ensure_one()

        if self.skip_auto_retention:
            return False

        if self.move_type not in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
            return False

        if self.state != 'posted':
            return False

        if not self.partner_id:
            return False

        if self.partner_id.fiscal_profile == 'exempt':
            _logger.info(
                'Factura %s: partner %s es exento, sin retención.',
                self.name, self.partner_id.name,
            )
            return False

        if not self.partner_id.fiscal_profile:
            _logger.info(
                'Factura %s: partner %s sin perfil fiscal, sin retención.',
                self.name, self.partner_id.name,
            )
            return False

        # No duplicar si ya tiene retenciones
        if self.retention_ids:
            _logger.info(
                'Factura %s: ya tiene %d retención(es), omitiendo.',
                self.name, len(self.retention_ids),
            )
            return False

        return True

    def _apply_auto_retention(self):
        """
        Aplica las retenciones automáticas a la factura según
        las reglas configuradas para el perfil fiscal del partner.
        """
        self.ensure_one()
        partner = self.partner_id
        rules = partner._get_applicable_retention_rules(self.move_type)

        if not rules:
            _logger.info(
                'Factura %s: no hay reglas de retención para perfil "%s".',
                self.name, partner.fiscal_profile,
            )
            return

        # Filtrar reglas que aplican a esta factura específica
        applicable_rules = rules.filtered(lambda r: r.matches_invoice(self))

        if not applicable_rules:
            _logger.info(
                'Factura %s: ninguna regla coincide con los impuestos de la factura.',
                self.name,
            )
            return

        # Construir líneas de retención
        retention_lines = []
        for rule in applicable_rules:
            amount = rule.compute_retention_amount(self)
            if amount <= 0:
                _logger.debug(
                    'Regla %s: monto calculado = 0, omitiendo.', rule.name
                )
                continue

            # Calcular base para referencia
            if rule.retention_basis == 'tax_amount':
                base = abs(sum(
                    line.amount_currency
                    for line in self.line_ids
                    if line.tax_line_id and (
                        not rule.tax_ids or line.tax_line_id in rule.tax_ids
                    )
                ))
            elif rule.retention_basis == 'subtotal':
                base = self.amount_untaxed
            else:
                base = self.amount_total

            line_vals = {
                'name': rule.description or rule.name,
                'rule_id': rule.id,
                'account_id': rule.account_id.id,
                'base_amount': base,
                'percentage': rule.percentage,
                'amount': amount,
                'retention_basis': rule.retention_basis,
                'sequence': rule.sequence,
            }
            # Asociar impuesto si la regla lo tiene
            if rule.tax_ids:
                # Tomar el primer impuesto coincidente en la factura
                invoice_taxes = self.invoice_line_ids.mapped('tax_ids')
                matching_tax = (rule.tax_ids & invoice_taxes)[:1]
                if matching_tax:
                    line_vals['tax_id'] = matching_tax.id

            retention_lines.append((0, 0, line_vals))

        if not retention_lines:
            _logger.info('Factura %s: todas las retenciones calcularon monto 0.', self.name)
            return

        # Determinar tipo de retención
        retention_type = (
            'sale' if self.move_type in ('out_invoice', 'out_refund') else 'purchase'
        )

        # Determinar diario
        journal = (
            applicable_rules[0].journal_id
            or self.journal_id
        )

        # Crear la retención
        retention_vals = {
            'partner_id': partner.id,
            'invoice_id': self.id,
            'date': self.invoice_date or fields.Date.context_today(self),
            'retention_type': retention_type,
            'currency_id': self.currency_id.id,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'line_ids': retention_lines,
            'notes': _(
                'Retención generada automáticamente al confirmar la factura %s '
                'para el partner %s (perfil: %s).'
            ) % (self.name, partner.name, partner.fiscal_profile),
        }

        retention = self.env['account.retention'].create(retention_vals)

        # Contabilizar la retención automáticamente
        try:
            retention.action_post()
            _logger.info(
                'Retención %s creada y validada para factura %s.',
                retention.name, self.name,
            )
        except Exception as e:
            _logger.error(
                'Error al validar retención para factura %s: %s', self.name, e
            )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_view_retentions(self):
        """Abre las retenciones asociadas a esta factura."""
        self.ensure_one()
        return {
            'name': _('Retenciones de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.retention',
            'view_mode': 'list,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {
                'default_invoice_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }

    def action_apply_retention_manual(self):
        """
        Acción manual para aplicar retenciones en facturas ya confirmadas.
        Útil cuando se cambió el perfil fiscal después de confirmar.
        """
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(
                _('Solo se pueden aplicar retenciones a facturas confirmadas (Posted).')
            )
        if self.retention_ids:
            raise UserError(
                _('Esta factura ya tiene retenciones aplicadas. '
                  'Cancele las retenciones existentes antes de volver a aplicar.')
            )
        self._apply_auto_retention()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Retención Aplicada'),
                'message': _(
                    'Se aplicaron %d retención(es) a la factura.'
                ) % len(self.retention_ids),
                'type': 'success',
                'sticky': False,
            },
        }
