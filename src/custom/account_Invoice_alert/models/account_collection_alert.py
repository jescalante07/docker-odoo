# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import date


class AccountCollectionAlert(models.Model):
    _name = 'account.collection.alert'
    _description = 'Alerta de Cobro'
    _order = 'risk_level desc, days_overdue desc'
    _rec_name = 'invoice_id'

    # -------------------------------------------------------
    # Campos principales
    # -------------------------------------------------------
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        ondelete='cascade',
        domain=[('move_type', 'in', ['out_invoice', 'out_refund']), ('payment_state', '!=', 'paid')],
        index=True,
    )
    rule_id = fields.Many2one(
        'account.collection.alert.rule',
        string='Regla Aplicada',
        ondelete='set null',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='invoice_id.partner_id',
        store=True,
        index=True,
    )
    invoice_date_due = fields.Date(
        string='Fecha de Vencimiento',
        related='invoice_id.invoice_date_due',
        store=True,
    )
    invoice_date = fields.Date(
        string='Fecha de Factura',
        related='invoice_id.invoice_date',
        store=True,
    )
    amount_residual = fields.Monetary(
        string='Saldo Pendiente',
        related='invoice_id.amount_residual',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='invoice_id.currency_id',
        store=True,
    )
    days_overdue = fields.Integer(
        string='Días de Atraso',
        compute='_compute_days_overdue',
        store=True,
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
        index=True,
    )
    risk_level_color = fields.Integer(
        string='Color de Riesgo',
        compute='_compute_risk_level_color',
    )
    state = fields.Selection(
        selection=[
            ('open', 'Abierta'),
            ('resolved', 'Resuelta'),
            ('ignored', 'Ignorada'),
        ],
        string='Estado',
        default='open',
        required=True,
        index=True,
    )
    last_evaluated = fields.Datetime(
        string='Última Evaluación',
        default=fields.Datetime.now,
    )
    notes = fields.Text(
        string='Notas',
    )
    company_id = fields.Many2one(
        'res.company',
        related='invoice_id.company_id',
        store=True,
    )
    invoice_name = fields.Char(
        string='Número de Factura',
        related='invoice_id.name',
        store=True,
    )

    # -------------------------------------------------------
    # Compute methods
    # -------------------------------------------------------
    @api.depends('invoice_date_due')
    def _compute_days_overdue(self):
        today = date.today()
        for alert in self:
            if alert.invoice_date_due:
                delta = (today - alert.invoice_date_due).days
                alert.days_overdue = max(delta, 0)
            else:
                alert.days_overdue = 0

    @api.depends('risk_level')
    def _compute_risk_level_color(self):
        color_map = {'low': 10, 'medium': 3, 'high': 1}
        for alert in self:
            alert.risk_level_color = color_map.get(alert.risk_level, 0)

    # -------------------------------------------------------
    # Métodos de acción
    # -------------------------------------------------------
    def action_resolve(self):
        self.write({'state': 'resolved'})

    def action_ignore(self):
        self.write({'state': 'ignored'})

    def action_reopen(self):
        self.write({'state': 'open'})

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def action_evaluate_all_invoices(self):
        """Acción para evaluar todas las facturas y mostrar resultado."""
        count = self.evaluate_invoices()
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Evaluación de Facturas',
                'message': f'Se han procesado {count} alerta(s). Refresca la página para ver los cambios.',
                'type': 'info' if count > 0 else 'warning',
                'sticky': False,
            },
        }
        return action

    # -------------------------------------------------------
    # Evaluación automática de facturas
    # -------------------------------------------------------
    @api.model
    def evaluate_invoices(self):
        """
        Evalúa todas las facturas vencidas y crea/actualiza alertas
        según las reglas de riesgo activas.
        Retorna el número de alertas creadas o actualizadas.
        """
        today = date.today()

        # Obtener facturas vencidas no pagadas
        overdue_invoices = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice']),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ['paid', 'reversed']),
            ('invoice_date_due', '<', fields.Date.to_string(today)),
        ])

        if not overdue_invoices:
            return 0

        # Obtener reglas activas ordenadas por prioridad (días desc, monto desc)
        rules = self.env['account.collection.alert.rule'].search(
            [('active', '=', True)],
            order='days_overdue desc, amount_min desc',
        )

        created_count = 0
        updated_count = 0

        for invoice in overdue_invoices:
            days_overdue = (today - invoice.invoice_date_due).days if invoice.invoice_date_due else 0
            amount_residual = invoice.amount_residual

            # Encontrar la regla de mayor riesgo que aplica
            matched_rule = None
            matched_risk = None
            for rule in rules:
                if days_overdue >= rule.days_overdue and amount_residual >= rule.amount_min:
                    matched_rule = rule
                    matched_risk = rule.risk_level
                    break  # La primera regla (mayor prioridad) aplica

            if not matched_rule:
                # Si no hay regla pero hay atraso, asignar bajo riesgo por defecto
                matched_risk = 'low'

            # Buscar alerta existente para esta factura
            existing_alert = self.search([
                ('invoice_id', '=', invoice.id),
                ('state', '=', 'open'),
            ], limit=1)

            if existing_alert:
                existing_alert.write({
                    'risk_level': matched_risk,
                    'rule_id': matched_rule.id if matched_rule else False,
                    'last_evaluated': fields.Datetime.now(),
                })
                updated_count += 1
            else:
                self.create({
                    'invoice_id': invoice.id,
                    'rule_id': matched_rule.id if matched_rule else False,
                    'risk_level': matched_risk,
                    'state': 'open',
                    'last_evaluated': fields.Datetime.now(),
                })
                created_count += 1

        return created_count + updated_count

    @api.model
    def _scheduled_evaluate_invoices(self):
        """Método llamado por tarea programada (cron)."""
        return self.evaluate_invoices()

    # -------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------
    _sql_constraints = [
        (
            'unique_open_invoice_alert',
            'UNIQUE(invoice_id, state)',
            'Ya existe una alerta abierta para esta factura.',
        ),
    ]
