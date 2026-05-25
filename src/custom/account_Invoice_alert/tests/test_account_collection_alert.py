# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestAccountCollectionAlert(TransactionCase):
    """Suite de pruebas para alertas de cobro."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Empresa y diario
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        # Cuentas contables
        cls.account_receivable = cls.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        cls.account_revenue = cls.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        # Partner de prueba
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente de Prueba',
            'company_type': 'company',
        })

        # Limpiar reglas existentes para tests controlados
        cls.env['account.collection.alert.rule'].search([]).unlink()
        cls.env['account.collection.alert'].search([]).unlink()

    def _create_rule(self, name, days_overdue, amount_min, risk_level):
        """Helper para crear reglas de riesgo."""
        return self.env['account.collection.alert.rule'].create({
            'name': name,
            'days_overdue': days_overdue,
            'amount_min': amount_min,
            'risk_level': risk_level,
        })

    def _create_overdue_invoice(self, amount, days_overdue):
        """
        Helper para crear una factura vencida.
        Crea la factura con fecha de vencimiento en el pasado y la confirma.
        """
        due_date = date.today() - timedelta(days=days_overdue)
        invoice_date = due_date - timedelta(days=30)

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'invoice_date': invoice_date,
            'invoice_date_due': due_date,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio de prueba',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.account_revenue.id,
            })],
        })
        invoice.action_post()
        return invoice

    # ----------------------------------------------------------
    # TEST 1: Clasificación correcta – Riesgo BAJO
    # ----------------------------------------------------------
    def test_01_classification_low_risk(self):
        """Una factura con 5 días de atraso y monto 50 debe ser nivel BAJO."""
        rule_low = self._create_rule('Bajo Test', 1, 0.01, 'low')
        self._create_rule('Medio Test', 15, 100.0, 'medium')
        self._create_rule('Alto Test', 30, 500.0, 'high')

        invoice = self._create_overdue_invoice(amount=50.0, days_overdue=5)

        count = self.env['account.collection.alert'].evaluate_invoices()
        self.assertGreater(count, 0, 'Debe crear al menos una alerta')

        alert = self.env['account.collection.alert'].search([
            ('invoice_id', '=', invoice.id),
            ('state', '=', 'open'),
        ])
        self.assertEqual(len(alert), 1, 'Debe existir exactamente una alerta para la factura')
        self.assertEqual(alert.risk_level, 'low',
                         f'Riesgo esperado: low, obtenido: {alert.risk_level}')

    # ----------------------------------------------------------
    # TEST 2: Clasificación correcta – Riesgo MEDIO
    # ----------------------------------------------------------
    def test_02_classification_medium_risk(self):
        """Una factura con 20 días de atraso y monto 200 debe ser nivel MEDIO."""
        self._create_rule('Bajo Test', 1, 0.01, 'low')
        self._create_rule('Medio Test', 15, 100.0, 'medium')
        self._create_rule('Alto Test', 30, 500.0, 'high')

        invoice = self._create_overdue_invoice(amount=200.0, days_overdue=20)

        self.env['account.collection.alert'].evaluate_invoices()

        alert = self.env['account.collection.alert'].search([
            ('invoice_id', '=', invoice.id),
            ('state', '=', 'open'),
        ])
        self.assertEqual(alert.risk_level, 'medium',
                         f'Riesgo esperado: medium, obtenido: {alert.risk_level}')

    # ----------------------------------------------------------
    # TEST 3: Clasificación correcta – Riesgo ALTO
    # ----------------------------------------------------------
    def test_03_classification_high_risk(self):
        """Una factura con 45 días de atraso y monto 1000 debe ser nivel ALTO."""
        self._create_rule('Bajo Test', 1, 0.01, 'low')
        self._create_rule('Medio Test', 15, 100.0, 'medium')
        self._create_rule('Alto Test', 30, 500.0, 'high')

        invoice = self._create_overdue_invoice(amount=1000.0, days_overdue=45)

        self.env['account.collection.alert'].evaluate_invoices()

        alert = self.env['account.collection.alert'].search([
            ('invoice_id', '=', invoice.id),
            ('state', '=', 'open'),
        ])
        self.assertEqual(alert.risk_level, 'high',
                         f'Riesgo esperado: high, obtenido: {alert.risk_level}')

    # ----------------------------------------------------------
    # TEST 4: Sin reglas coincidentes – debe asignar 'low' por defecto
    # ----------------------------------------------------------
    def test_04_no_matching_rule_defaults_to_low(self):
        """
        Con regla de alto riesgo exigiendo 1000+ de monto,
        una factura de 50 con 40 días no debe alcanzar nivel alto.
        """
        self._create_rule('Alto Exclusivo', 30, 1000.0, 'high')

        invoice = self._create_overdue_invoice(amount=50.0, days_overdue=40)

        self.env['account.collection.alert'].evaluate_invoices()

        alert = self.env['account.collection.alert'].search([
            ('invoice_id', '=', invoice.id),
            ('state', '=', 'open'),
        ])
        # 50 < 1000 (monto mínimo de la única regla), así que cae al default 'low'
        self.assertEqual(alert.risk_level, 'low',
                         'Sin regla aplicable, debe asignarse nivel low por defecto')

    # ----------------------------------------------------------
    # TEST 5: Idempotencia – no crea alertas duplicadas
    # ----------------------------------------------------------
    def test_05_no_duplicate_alerts(self):
        """Evaluar dos veces no debe crear alertas duplicadas."""
        self._create_rule('Bajo Test', 1, 0.01, 'low')

        invoice = self._create_overdue_invoice(amount=100.0, days_overdue=10)

        self.env['account.collection.alert'].evaluate_invoices()
        self.env['account.collection.alert'].evaluate_invoices()

        alerts = self.env['account.collection.alert'].search([
            ('invoice_id', '=', invoice.id),
            ('state', '=', 'open'),
        ])
        self.assertEqual(len(alerts), 1, 'No deben crearse alertas duplicadas para la misma factura')

    # ----------------------------------------------------------
    # TEST 6: Tablero – agrupación por nivel de riesgo
    # ----------------------------------------------------------
    def test_06_dashboard_grouping_by_risk_level(self):
        """
        El tablero debe poder agrupar alertas por risk_level
        y mostrar los tres niveles correctamente.
        """
        self._create_rule('Bajo', 1, 0.01, 'low')
        self._create_rule('Medio', 15, 100.0, 'medium')
        self._create_rule('Alto', 30, 500.0, 'high')

        inv_low = self._create_overdue_invoice(amount=50.0, days_overdue=5)
        inv_med = self._create_overdue_invoice(amount=200.0, days_overdue=20)
        inv_high = self._create_overdue_invoice(amount=1000.0, days_overdue=35)

        self.env['account.collection.alert'].evaluate_invoices()

        # Verificar agrupación usando read_group (simula el tablero)
        groups = self.env['account.collection.alert'].read_group(
            domain=[('state', '=', 'open')],
            fields=['risk_level', 'amount_residual:sum'],
            groupby=['risk_level'],
        )

        risk_levels_found = {g['risk_level'] for g in groups}
        self.assertIn('low', risk_levels_found, 'Debe existir grupo de riesgo bajo')
        self.assertIn('medium', risk_levels_found, 'Debe existir grupo de riesgo medio')
        self.assertIn('high', risk_levels_found, 'Debe existir grupo de riesgo alto')

        # Verificar que los conteos son correctos
        for group in groups:
            if group['risk_level'] == 'high':
                self.assertGreaterEqual(
                    group['risk_level_count'], 1,
                    'Debe haber al menos 1 alerta de riesgo alto'
                )

    # ----------------------------------------------------------
    # TEST 7: Validación de campos negativos en reglas
    # ----------------------------------------------------------
    def test_07_rule_validation_negative_days(self):
        """No debe permitir días de atraso negativos."""
        with self.assertRaises(ValidationError):
            self._create_rule('Regla Inválida', -5, 100.0, 'low')

    def test_08_rule_validation_negative_amount(self):
        """No debe permitir monto mínimo negativo."""
        with self.assertRaises(ValidationError):
            self._create_rule('Regla Inválida', 5, -100.0, 'low')

    # ----------------------------------------------------------
    # TEST 9: Acciones de estado de alerta
    # ----------------------------------------------------------
    def test_09_alert_state_transitions(self):
        """Las acciones de resolver/ignorar/reabrir deben cambiar el estado correctamente."""
        self._create_rule('Bajo', 1, 0.01, 'low')
        invoice = self._create_overdue_invoice(amount=100.0, days_overdue=5)
        self.env['account.collection.alert'].evaluate_invoices()

        alert = self.env['account.collection.alert'].search([
            ('invoice_id', '=', invoice.id),
        ], limit=1)

        self.assertEqual(alert.state, 'open')

        alert.action_resolve()
        self.assertEqual(alert.state, 'resolved')

        alert.action_reopen()
        self.assertEqual(alert.state, 'open')

        alert.action_ignore()
        self.assertEqual(alert.state, 'ignored')

    # ----------------------------------------------------------
    # TEST 10: Cálculo de días_overdue
    # ----------------------------------------------------------
    def test_10_days_overdue_calculation(self):
        """Los días de atraso deben calcularse correctamente."""
        self._create_rule('Bajo', 1, 0.01, 'low')
        expected_days = 10
        invoice = self._create_overdue_invoice(amount=100.0, days_overdue=expected_days)
        self.env['account.collection.alert'].evaluate_invoices()

        alert = self.env['account.collection.alert'].search([
            ('invoice_id', '=', invoice.id),
        ], limit=1)

        self.assertEqual(
            alert.days_overdue, expected_days,
            f'Días esperados: {expected_days}, obtenidos: {alert.days_overdue}'
        )
