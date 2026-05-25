# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    """
    Modelo de Retención Fiscal (cabecera).
    """
    _name = 'account.retention'
    _description = 'Retención Fiscal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'
    _rec_name = 'name'

    # ------------------------------------------------------------------
    # Identificación
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Número de Retención',
        readonly=True,
        copy=False,
        default='/',
        index=True,
        tracking=True,
        help='Número secuencial del comprobante de retención.',
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('posted', 'Validado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )

    retention_type = fields.Selection(
        selection=[
            ('sale', 'Retención en Venta'),
            ('purchase', 'Retención en Compra'),
        ],
        string='Tipo de Retención',
        required=True,
        tracking=True,
        help='Indica si la retención aplica sobre una factura de venta o compra.',
    )

    # ------------------------------------------------------------------
    # Fechas
    # ------------------------------------------------------------------
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        copy=False,
    )

    # ------------------------------------------------------------------
    # Referencias
    # ------------------------------------------------------------------
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto',
        required=True,
        tracking=True,
        index=True,
        help='Cliente o proveedor al que aplica la retención.',
    )

    fiscal_profile = fields.Selection(
        related='partner_id.fiscal_profile',
        string='Perfil Fiscal',
        store=True,
        readonly=True,
    )

    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Factura Origen',
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
        help='Factura sobre la cual se calculó esta retención.',
    )

    invoice_name = fields.Char(
        related='invoice_id.name',
        string='Nº Factura',
        readonly=True,
    )

    invoice_date = fields.Date(
        related='invoice_id.invoice_date',
        string='Fecha Factura',
        readonly=True,
    )

    invoice_amount_total = fields.Monetary(
        related='invoice_id.amount_total',
        string='Total Factura',
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Importes
    # ------------------------------------------------------------------
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )

    amount_total = fields.Monetary(
        string='Total Retenido',
        compute='_compute_amount_total',
        store=True,
        currency_field='currency_id',
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Contabilidad
    # ------------------------------------------------------------------
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario',
        domain="[('type', 'in', ['general', 'sale', 'purchase'])]",
        tracking=True,
    )

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Asiento Contable',
        readonly=True,
        copy=False,
        help='Asiento contable generado para esta retención.',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ------------------------------------------------------------------
    # Líneas
    # ------------------------------------------------------------------
    line_ids = fields.One2many(
        comodel_name='account.retention.line',
        inverse_name='retention_id',
        string='Líneas de Retención',
        copy=True,
    )

    # ------------------------------------------------------------------
    # Notas
    # ------------------------------------------------------------------
    notes = fields.Text(
        string='Notas Internas',
        help='Observaciones adicionales sobre esta retención.',
    )

    # ------------------------------------------------------------------
    # Métodos computados
    # ------------------------------------------------------------------
    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        for retention in self:
            retention.amount_total = sum(retention.line_ids.mapped('amount'))

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('line_ids')
    def _check_lines(self):
        for retention in self:
            if retention.state == 'posted' and not retention.line_ids:
                raise ValidationError(
                    _('La retención "%s" debe tener al menos una línea.') % retention.name
                )

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'account.retention'
                ) or '/'
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = '/'
        default['state'] = 'draft'
        default['move_id'] = False
        return super().copy(default)

    # ------------------------------------------------------------------
    # Acciones de flujo
    # ------------------------------------------------------------------
    def action_post(self):
        """
        Valida la retención:
        1. Asigna número secuencial.
        2. Genera el asiento contable.
        3. Cambia el estado a 'posted'.
        """
        for retention in self:
            if retention.state != 'draft':
                raise UserError(
                    _('Solo se pueden validar retenciones en estado Borrador.')
                )
            if not retention.line_ids:
                raise UserError(
                    _('La retención "%s" no tiene líneas. '
                      'Agregue al menos una línea antes de validar.') % retention.name
                )

            # Generar asiento contable
            move = retention._create_accounting_entry()
            if move:
                retention.move_id = move

            retention.state = 'posted'
            _logger.info('Retención %s validada.', retention.name)

    def action_draft(self):
        """Regresa la retención a borrador (solo si el asiento no está contabilizado)."""
        for retention in self:
            if retention.state == 'cancel':
                raise UserError(_('No se puede reabrir una retención cancelada.'))
            if retention.move_id and retention.move_id.state == 'posted':
                raise UserError(
                    _('El asiento contable ya está contabilizado. '
                      'Primero cancele el asiento para regresar a borrador.')
                )
            if retention.move_id:
                retention.move_id.button_cancel()
                retention.move_id.unlink()
                retention.move_id = False
            retention.state = 'draft'

    def action_cancel(self):
        """Cancela la retención y reversa el asiento si existe."""
        for retention in self:
            if retention.state == 'cancel':
                continue
            if retention.move_id and retention.move_id.state == 'posted':
                # Crear reverso del asiento
                reversal = retention.move_id._reverse_moves(
                    default_values_list=[{'ref': _('Cancelación: %s') % retention.name}]
                )
                reversal.action_post()
            elif retention.move_id:
                retention.move_id.button_cancel()
                retention.move_id.unlink()
                retention.move_id = False
            retention.state = 'cancel'
            _logger.info('Retención %s cancelada.', retention.name)

    def _create_accounting_entry(self):
        """
        Genera el asiento contable de la retención.
        Débito: cuenta de retención (por cada línea).
        Crédito: cuenta por pagar/cobrar del partner.
        """
        self.ensure_one()
        if not self.line_ids:
            return False

        # Determinar diario
        journal = self.journal_id
        if not journal:
            if self.retention_type == 'sale':
                journal = self.env['account.journal'].search(
                    [('type', '=', 'sale'), ('company_id', '=', self.company_id.id)],
                    limit=1
                )
            else:
                journal = self.env['account.journal'].search(
                    [('type', '=', 'purchase'), ('company_id', '=', self.company_id.id)],
                    limit=1
                )

        if not journal:
            journal = self.env['account.journal'].search(
                [('type', '=', 'general'), ('company_id', '=', self.company_id.id)],
                limit=1
            )

        if not journal:
            _logger.warning('No se encontró diario para la retención %s.', self.name)
            return False

        # Construir líneas del asiento
        move_lines = []
        total_debit = 0.0

        for line in self.line_ids:
            if not line.account_id:
                continue
            debit = line.amount if self.retention_type == 'purchase' else 0.0
            credit = line.amount if self.retention_type == 'sale' else 0.0
            total_debit += line.amount

            move_lines.append((0, 0, {
                'name': line.name or self.name,
                'account_id': line.account_id.id,
                'debit': debit,
                'credit': credit,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
            }))

        # Línea de contrapartida (cuenta de partner)
        if self.invoice_id:
            # Usar la cuenta de la línea de pago del partner en la factura
            counterpart_account = (
                self.invoice_id.line_ids
                .filtered(lambda l: l.account_id.account_type in (
                    'asset_receivable', 'liability_payable'
                ))
                .mapped('account_id')[:1]
            )
        else:
            counterpart_account = self.env['account.account'].browse()

        if not counterpart_account:
            _logger.warning(
                'No se encontró cuenta de contrapartida para la retención %s.', self.name
            )
            return False

        counter_debit = 0.0 if self.retention_type == 'purchase' else total_debit
        counter_credit = total_debit if self.retention_type == 'purchase' else 0.0

        move_lines.append((0, 0, {
            'name': _('Retención aplicada: %s') % self.name,
            'account_id': counterpart_account.id,
            'debit': counter_debit,
            'credit': counter_credit,
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
        }))

        move_vals = {
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.name,
            'company_id': self.company_id.id,
            'line_ids': move_lines,
        }

        move = self.env['account.move'].create(move_vals)
        try:
            move.action_post()
        except Exception as e:
            _logger.error('Error al contabilizar asiento de retención %s: %s', self.name, e)

        return move

    def action_view_accounting_entry(self):
        """Abre el asiento contable generado."""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('Esta retención no tiene asiento contable generado.'))
        return {
            'name': _('Asiento Contable'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }

    def action_view_invoice(self):
        """Abre la factura origen."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('Esta retención no tiene factura origen.'))
        return {
            'name': _('Factura'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }
