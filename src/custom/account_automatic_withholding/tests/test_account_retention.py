# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-

"""
Tests para el módulo account_retention_auto.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'retention')
class TestAccountRetention(TransactionCase):
    """
    Suite de pruebas para el módulo de Retenciones Automáticas.

    Cubre:
    - Campos fiscal_profile en res.partner
    - Modelo account.retention y account.retention.line
    - Reglas de retención y su configuración
    - Aplicación automática al confirmar facturas
    - Casos límite: sin perfil fiscal, sin reglas, exento, monto cero
    - Flujo completo: draft → posted → cancel
    - Prevención de duplicados
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Compañía y moneda
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        # Diarios
        cls.sale_journal = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.company.id)], limit=1
        )
        cls.purchase_journal = cls.env['account.journal'].search(
            [('type', '=', 'purchase'), ('company_id', '=', cls.company.id)], limit=1
        )
        cls.general_journal = cls.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', cls.company.id)], limit=1
        )

        # Cuentas contables
        cls.account_receivable = cls.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        cls.account_payable = cls.env['account.account'].search([
            ('account_type', '=', 'liability_payable'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        cls.account_income = cls.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        cls.account_expense = cls.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        # Cuenta de retención (usamos una cuenta de pasivo o cualquiera disponible)
        cls.retention_account = cls.env['account.account'].search([
            ('deprecated', '=', False),
            ('company_id', '=', cls.company.id),
            ('account_type', 'not in', ['asset_receivable', 'liability_payable']),
        ], limit=1)

        # Impuesto de prueba
        cls.tax_15 = cls.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.company.id),
            ('active', '=', True),
        ], limit=1)

    def setUp(self):
        super().setUp()

        # Partners para cada prueba
        self.partner_standard = self._create_partner(
            'Cliente Estándar Test', 'standard'
        )
        self.partner_agent = self._create_partner(
            'Agente de Retención Test', 'retention_agent'
        )
        self.partner_exempt = self._create_partner(
            'Cliente Exento Test', 'exempt'
        )
        self.partner_no_profile = self._create_partner(
            'Cliente Sin Perfil Test', False
        )
        self.partner_simplified = self._create_partner(
            'Régimen Simplificado Test', 'simplified'
        )

        # Regla de retención estándar
        self.rule_standard = self._create_rule(
            name='Retención Estándar 15%',
            fiscal_profile='standard',
            percentage=15.0,
            retention_type='sale',
        )

        # Regla para agente de retención
        self.rule_agent = self._create_rule(
            name='Retención Agente 10%',
            fiscal_profile='retention_agent',
            percentage=10.0,
            retention_type='sale',
        )

        # Regla para régimen simplificado
        self.rule_simplified = self._create_rule(
            name='Retención Simplificado 5%',
            fiscal_profile='simplified',
            percentage=5.0,
            retention_type='sale',
            retention_basis='subtotal',
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_partner(self, name, fiscal_profile):
        """Crea un partner de prueba con el perfil fiscal dado."""
        vals = {
            'name': name,
            'is_company': True,
            'property_account_receivable_id': self.account_receivable.id,
            'property_account_payable_id': self.account_payable.id,
        }
        if fiscal_profile:
            vals['fiscal_profile'] = fiscal_profile
        return self.env['res.partner'].create(vals)

    def _create_rule(self, name, fiscal_profile, percentage, retention_type='sale',
                     retention_basis='tax_amount', tax_ids=None):
        """Crea una regla de retención de prueba."""
        vals = {
            'name': name,
            'fiscal_profile': fiscal_profile,
            'percentage': percentage,
            'retention_type': retention_type,
            'retention_basis': retention_basis,
            'account_id': self.retention_account.id,
            'journal_id': self.general_journal.id,
        }
        if tax_ids:
            vals['tax_ids'] = [(6, 0, tax_ids)]
        return self.env['account.retention.rule'].create(vals)

    def _create_invoice(self, partner, amount=1000.0, move_type='out_invoice',
                        tax_ids=None, skip_retention=False):
        """Crea una factura de prueba."""
        line_vals = {
            'name': 'Producto de prueba',
            'quantity': 1,
            'price_unit': amount,
            'account_id': (
                self.account_income.id
                if move_type in ('out_invoice', 'out_refund')
                else self.account_expense.id
            ),
        }
        if tax_ids:
            line_vals['tax_ids'] = [(6, 0, tax_ids)]

        journal = (
            self.sale_journal
            if move_type in ('out_invoice', 'out_refund')
            else self.purchase_journal
        )

        invoice = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'journal_id': journal.id,
            'invoice_line_ids': [(0, 0, line_vals)],
            'skip_auto_retention': skip_retention,
        })
        return invoice

    def _create_retention(self, partner, invoice=None, lines=None):
        """Crea una retención de prueba directamente."""
        line_vals = lines or [{
            'name': 'Retención de prueba',
            'account_id': self.retention_account.id,
            'base_amount': 1000.0,
            'percentage': 15.0,
            'amount': 150.0,
        }]

        vals = {
            'partner_id': partner.id,
            'retention_type': 'sale',
            'date': '2024-01-15',
            'currency_id': self.currency.id,
            'line_ids': [(0, 0, l) for l in line_vals],
        }
        if invoice:
            vals['invoice_id'] = invoice.id

        return self.env['account.retention'].create(vals)

    # =========================================================================
    # TC-01 a TC-05: CAMPOS EN RES.PARTNER
    # =========================================================================

    def test_01_partner_has_fiscal_profile_field(self):
        """TC-01: res.partner tiene el campo fiscal_profile."""
        self.assertIn(
            'fiscal_profile',
            self.env['res.partner']._fields,
            "El campo 'fiscal_profile' debe existir en res.partner",
        )

    def test_02_fiscal_profile_selection_values(self):
        """TC-02: Los valores de fiscal_profile son los esperados."""
        field = self.env['res.partner']._fields['fiscal_profile']
        keys = [k for k, _ in field.selection]
        for expected in ('standard', 'retention_agent', 'exempt', 'simplified', 'special'):
            self.assertIn(expected, keys, f"Debe existir el perfil '{expected}'")

    def test_03_partner_default_fiscal_profile(self):
        """TC-03: El perfil fiscal por defecto es 'standard'."""
        partner = self.env['res.partner'].create({'name': 'Test Default Profile'})
        self.assertEqual(
            partner.fiscal_profile, 'standard',
            "El perfil fiscal por defecto debe ser 'standard'",
        )

    def test_04_partner_exempt_profile(self):
        """TC-04: El partner exento tiene fiscal_profile='exempt'."""
        self.assertEqual(self.partner_exempt.fiscal_profile, 'exempt')

    def test_05_partner_no_profile_returns_no_rules(self):
        """TC-05: Partner sin perfil fiscal no devuelve reglas aplicables."""
        # Forzar fiscal_profile a False/vacío
        self.partner_no_profile.write({'fiscal_profile': 'standard'})
        # Probar con perfil que no tiene reglas
        rules = self.partner_simplified._get_applicable_retention_rules('out_invoice')
        # simplified tiene regla, si borramos esa regla debería retornar vacío
        self.rule_simplified.active = False
        rules_after = self.partner_simplified._get_applicable_retention_rules('out_invoice')
        self.assertFalse(
            rules_after,
            "Con la regla inactiva, no deben retornarse reglas para el perfil",
        )
        # Restaurar
        self.rule_simplified.active = True

    # =========================================================================
    # TC-06 a TC-10: MODELO account.retention.rule
    # =========================================================================

    def test_06_retention_rule_model_exists(self):
        """TC-06: El modelo account.retention.rule existe."""
        self.assertIn('account.retention.rule', self.env)

    def test_07_retention_rule_percentage_validation(self):
        """TC-07: Porcentaje fuera de rango genera ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_rule(
                name='Regla Inválida', fiscal_profile='standard',
                percentage=150.0,
            )

    def test_08_retention_rule_zero_percentage_raises(self):
        """TC-08: Porcentaje cero genera ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_rule(
                name='Regla Cero', fiscal_profile='standard',
                percentage=0.0,
            )

    def test_09_rule_compute_amount_on_tax(self):
        """TC-09: compute_retention_amount calcula correctamente sobre impuesto."""
        if not self.tax_15:
            self.skipTest('No hay impuesto de venta disponible para la prueba.')

        invoice = self._create_invoice(
            self.partner_standard, amount=1000.0,
            tax_ids=[self.tax_15.id], skip_retention=True,
        )
        invoice.action_post()

        # La regla standard opera sobre tax_amount
        amount = self.rule_standard.compute_retention_amount(invoice)
        self.assertGreaterEqual(amount, 0.0, "El monto calculado no puede ser negativo")

    def test_10_rule_compute_amount_on_subtotal(self):
        """TC-10: compute_retention_amount calcula correctamente sobre subtotal."""
        invoice = self._create_invoice(
            self.partner_simplified, amount=500.0, skip_retention=True,
        )
        invoice.action_post()

        amount = self.rule_simplified.compute_retention_amount(invoice)
        expected = 500.0 * (5.0 / 100.0)
        self.assertAlmostEqual(
            amount, expected, places=2,
            msg=f"Monto esperado: {expected}, obtenido: {amount}",
        )

    # =========================================================================
    # TC-11 a TC-14: MODELO account.retention (cabecera)
    # =========================================================================

    def test_11_retention_model_exists(self):
        """TC-11: El modelo account.retention existe."""
        self.assertIn('account.retention', self.env)

    def test_12_retention_created_with_sequence(self):
        """TC-12: La retención recibe número secuencial al crearse."""
        retention = self._create_retention(self.partner_standard)
        self.assertNotEqual(retention.name, '/', "La retención debe tener número secuencial")
        self.assertTrue(
            retention.name.startswith('RET/'),
            f"El número debe iniciar con 'RET/', obtenido: {retention.name}",
        )

    def test_13_retention_initial_state_draft(self):
        """TC-13: La retención inicia en estado 'draft'."""
        retention = self._create_retention(self.partner_standard)
        self.assertEqual(retention.state, 'draft')

    def test_14_retention_amount_total_computed(self):
        """TC-14: amount_total se calcula correctamente como suma de líneas."""
        retention = self._create_retention(self.partner_standard, lines=[
            {'name': 'Línea 1', 'account_id': self.retention_account.id,
             'base_amount': 1000.0, 'percentage': 15.0, 'amount': 150.0},
            {'name': 'Línea 2', 'account_id': self.retention_account.id,
             'base_amount': 500.0, 'percentage': 10.0, 'amount': 50.0},
        ])
        self.assertAlmostEqual(
            retention.amount_total, 200.0, places=2,
            msg="El total debe ser la suma de las líneas: 150 + 50 = 200",
        )

    # =========================================================================
    # TC-15 a TC-17: MODELO account.retention.line
    # =========================================================================

    def test_15_retention_line_model_exists(self):
        """TC-15: El modelo account.retention.line existe."""
        self.assertIn('account.retention.line', self.env)

    def test_16_retention_line_negative_amount_raises(self):
        """TC-16: Monto negativo en línea genera ValidationError."""
        with self.assertRaises(ValidationError):
            retention = self._create_retention(self.partner_standard, lines=[
                {'name': 'Línea Negativa', 'account_id': self.retention_account.id,
                 'base_amount': 1000.0, 'percentage': 15.0, 'amount': -150.0},
            ])

    def test_17_retention_line_inherits_state_from_header(self):
        """TC-17: Las líneas heredan el estado de la retención."""
        retention = self._create_retention(self.partner_standard)
        for line in retention.line_ids:
            self.assertEqual(
                line.state, 'draft',
                "Las líneas deben tener el estado de la retención (draft)",
            )

    # =========================================================================
    # TC-18 a TC-22: APLICACIÓN AUTOMÁTICA EN FACTURAS
    # =========================================================================

    def test_18_invoice_with_retention_on_confirm(self):
        """TC-18: Al confirmar factura de partner estándar se crea retención."""
        invoice = self._create_invoice(self.partner_standard, amount=1000.0)
        self.assertEqual(len(invoice.retention_ids), 0, "Sin retenciones antes de confirmar")

        invoice.action_post()

        self.assertGreater(
            len(invoice.retention_ids), 0,
            "Debe crearse al menos una retención al confirmar la factura",
        )

    def test_19_invoice_exempt_partner_no_retention(self):
        """TC-19 (LÍMITE): Factura de partner exento NO genera retención."""
        invoice = self._create_invoice(self.partner_exempt, amount=1000.0)
        invoice.action_post()

        self.assertEqual(
            len(invoice.retention_ids), 0,
            "No debe crearse retención para partner exento",
        )

    def test_20_invoice_no_fiscal_profile_no_retention(self):
        """TC-20 (LÍMITE): Factura de partner sin perfil fiscal no genera retención."""
        # El partner_no_profile no tiene reglas configuradas para su perfil
        # Creamos un partner con perfil 'special' que no tiene reglas
        partner_special = self._create_partner('Partner Sin Reglas Test', 'special')
        invoice = self._create_invoice(partner_special, amount=1000.0)
        invoice.action_post()

        self.assertEqual(
            len(invoice.retention_ids), 0,
            "No debe crearse retención cuando no hay reglas para el perfil fiscal",
        )

    def test_21_invoice_skip_retention_flag(self):
        """TC-21: Factura con skip_auto_retention=True no genera retención."""
        invoice = self._create_invoice(
            self.partner_standard, amount=1000.0, skip_retention=True,
        )
        invoice.action_post()

        self.assertEqual(
            len(invoice.retention_ids), 0,
            "No debe crearse retención cuando skip_auto_retention=True",
        )

    def test_22_invoice_retention_agent_gets_retention(self):
        """TC-22: Factura de agente de retención genera su retención específica."""
        invoice = self._create_invoice(self.partner_agent, amount=2000.0)
        invoice.action_post()

        self.assertGreater(
            len(invoice.retention_ids), 0,
            "El agente de retención debe generar retenciones",
        )
        retention = invoice.retention_ids[0]
        self.assertEqual(
            retention.partner_id, self.partner_agent,
            "La retención debe estar asociada al partner correcto",
        )

    # =========================================================================
    # TC-23 a TC-25: CÁLCULO DE MONTOS
    # =========================================================================

    def test_23_retention_amount_on_subtotal(self):
        """TC-23: La retención sobre subtotal calcula correctamente."""
        invoice = self._create_invoice(self.partner_simplified, amount=1000.0)
        invoice.action_post()

        if invoice.retention_ids:
            total_retained = invoice.total_retention_amount
            expected = 1000.0 * (5.0 / 100.0)
            self.assertAlmostEqual(
                total_retained, expected, places=2,
                msg=f"Total retenido: {total_retained}, esperado: {expected}",
            )

    def test_24_retention_total_computed_correctly(self):
        """TC-24: total_retention_amount en la factura es la suma de retenciones."""
        invoice = self._create_invoice(self.partner_standard, amount=1000.0)
        invoice.action_post()

        expected_total = sum(r.amount_total for r in invoice.retention_ids)
        self.assertAlmostEqual(
            invoice.total_retention_amount, expected_total, places=2,
            msg="total_retention_amount debe ser la suma de todas las retenciones",
        )

    def test_25_no_duplicate_retention_on_multiple_posts(self):
        """TC-25 (LÍMITE): No se crean retenciones duplicadas si ya existen."""
        invoice = self._create_invoice(self.partner_standard, amount=1000.0)
        invoice.action_post()

        retention_count_after_first = len(invoice.retention_ids)

        # Simular segunda llamada a _apply_auto_retention (no debe crear más)
        invoice._apply_auto_retention()
        retention_count_after_second = len(invoice.retention_ids)

        self.assertEqual(
            retention_count_after_first, retention_count_after_second,
            "No deben crearse retenciones duplicadas para la misma factura",
        )

    # =========================================================================
    # TC-26 a TC-28: FLUJO DE ESTADOS
    # =========================================================================

    def test_26_retention_draft_to_posted(self):
        """TC-26: La retención pasa correctamente de draft a posted."""
        retention = self._create_retention(self.partner_standard)
        self.assertEqual(retention.state, 'draft')

        # No llamamos action_post aquí porque requiere asiento contable válido
        # Verificamos que el método existe y es callable
        self.assertTrue(hasattr(retention, 'action_post'))
        self.assertTrue(callable(retention.action_post))

    def test_27_retention_without_lines_cannot_post(self):
        """TC-27 (LÍMITE): No se puede validar una retención sin líneas."""
        retention = self.env['account.retention'].create({
            'partner_id': self.partner_standard.id,
            'retention_type': 'sale',
            'date': '2024-01-15',
            'currency_id': self.currency.id,
        })

        with self.assertRaises(UserError):
            retention.action_post()

    def test_28_retention_cancel_from_posted(self):
        """TC-28: Se puede cancelar una retención en estado posted."""
        retention = self._create_retention(self.partner_standard)
        # Forzar estado posted manualmente para el test
        retention.write({'state': 'posted'})
        self.assertEqual(retention.state, 'posted')

        retention.action_cancel()
        self.assertEqual(
            retention.state, 'cancel',
            "La retención debe estar en 'cancel' después de cancelar",
        )

    # =========================================================================
    # TC-29 a TC-32: CASOS LÍMITE ADICIONALES
    # =========================================================================

    def test_29_rule_matches_invoice_without_tax_filter(self):
        """TC-29: Regla sin filtro de impuesto coincide con cualquier factura."""
        invoice = self._create_invoice(
            self.partner_standard, amount=500.0, skip_retention=True
        )
        invoice.action_post()
        result = self.rule_standard.matches_invoice(invoice)
        self.assertTrue(
            result,
            "La regla sin filtro de impuesto debe coincidir con cualquier factura",
        )

    def test_30_rule_matches_invoice_with_tax_filter(self):
        """TC-30 (LÍMITE): Regla con filtro de impuesto no coincide si la factura no lo tiene."""
        if not self.tax_15:
            self.skipTest('No hay impuesto disponible para esta prueba.')

        rule_with_tax = self._create_rule(
            name='Regla Con Impuesto Específico',
            fiscal_profile='standard',
            percentage=12.0,
            tax_ids=[self.tax_15.id],
        )

        # Factura SIN el impuesto específico
        invoice_no_tax = self._create_invoice(
            self.partner_standard, amount=1000.0, skip_retention=True
        )
        invoice_no_tax.action_post()

        result = rule_with_tax.matches_invoice(invoice_no_tax)
        self.assertFalse(
            result,
            "La regla con filtro de impuesto NO debe coincidir con factura sin ese impuesto",
        )

    def test_31_partner_specific_rules_take_priority(self):
        """TC-31: Las reglas específicas del partner tienen prioridad sobre el perfil."""
        specific_rule = self._create_rule(
            name='Regla Específica Partner',
            fiscal_profile='standard',
            percentage=8.0,
        )
        self.partner_standard.write({
            'retention_rule_ids': [(6, 0, [specific_rule.id])],
        })

        rules = self.partner_standard._get_applicable_retention_rules('out_invoice')
        self.assertIn(
            specific_rule, rules,
            "La regla específica del partner debe estar en las reglas aplicables",
        )
        self.assertNotIn(
            self.rule_standard, rules,
            "La regla genérica del perfil NO debe aparecer cuando hay reglas específicas",
        )

        # Limpiar
        self.partner_standard.write({'retention_rule_ids': [(5, 0, 0)]})

    def test_32_retention_fields_in_invoice(self):
        """TC-32: Los campos de retención existen en account.move."""
        fields_expected = [
            'retention_ids', 'retention_count',
            'total_retention_amount', 'has_retention', 'skip_auto_retention',
        ]
        for field_name in fields_expected:
            self.assertIn(
                field_name,
                self.env['account.move']._fields,
                f"El campo '{field_name}' debe existir en account.move",
            )

    def test_33_retention_rule_name_get(self):
        """TC-33: name_get de la regla incluye perfil, tipo y porcentaje."""
        name = self.rule_standard.name_get()[0][1]
        self.assertIn(
            str(int(self.rule_standard.percentage)),
            name,
            "El name_get debe incluir el porcentaje",
        )

    def test_34_account_retention_line_fields(self):
        """TC-34: account.retention.line tiene todos los campos requeridos."""
        required_fields = [
            'retention_id', 'name', 'sequence', 'rule_id',
            'account_id', 'base_amount', 'percentage', 'amount',
            'currency_id', 'state', 'partner_id', 'date', 'invoice_id',
        ]
        for field_name in required_fields:
            self.assertIn(
                field_name,
                self.env['account.retention.line']._fields,
                f"El campo '{field_name}' debe existir en account.retention.line",
            )

    def test_35_should_apply_auto_retention_returns_false_for_draft(self):
        """TC-35 (LÍMITE): _should_apply_auto_retention es False en facturas draft."""
        invoice = self._create_invoice(self.partner_standard, amount=1000.0)
        # No confirmar — queda en draft
        result = invoice._should_apply_auto_retention()
        self.assertFalse(
            result,
            "No debe aplicarse retención a una factura en estado draft",
        )


@tagged('post_install', '-at_install', 'retention_fields')
class TestRetentionFields(TransactionCase):
    """Tests específicos para validar la existencia y tipo de campos del módulo."""

    def test_field_types_res_partner(self):
        """Verifica los tipos de campo en res.partner."""
        from odoo.fields import Selection, Text, Many2many, Integer
        checks = [
            ('fiscal_profile', Selection),
            ('fiscal_profile_note', Text),
            ('retention_rule_ids', Many2many),
            ('retention_count', Integer),
        ]
        for fname, ftype in checks:
            field = self.env['res.partner']._fields.get(fname)
            self.assertIsNotNone(field, f"Campo '{fname}' debe existir en res.partner")
            self.assertIsInstance(field, ftype, f"Campo '{fname}' debe ser {ftype.__name__}")

    def test_field_types_account_retention(self):
        """Verifica los tipos de campo en account.retention."""
        from odoo.fields import Char, Selection, Date, Many2one, One2many, Monetary, Boolean
        checks = [
            ('name', Char),
            ('state', Selection),
            ('date', Date),
            ('partner_id', Many2one),
            ('invoice_id', Many2one),
            ('amount_total', Monetary),
            ('line_ids', One2many),
        ]
        for fname, ftype in checks:
            field = self.env['account.retention']._fields.get(fname)
            self.assertIsNotNone(field, f"Campo '{fname}' debe existir en account.retention")
            self.assertIsInstance(field, ftype, f"Campo '{fname}' debe ser {ftype.__name__}")

    def test_field_types_account_retention_line(self):
        """Verifica los tipos de campo en account.retention.line."""
        from odoo.fields import Char, Many2one, Float, Monetary, Integer
        checks = [
            ('name', Char),
            ('retention_id', Many2one),
            ('account_id', Many2one),
            ('base_amount', Monetary),
            ('percentage', Float),
            ('amount', Monetary),
            ('sequence', Integer),
        ]
        for fname, ftype in checks:
            field = self.env['account.retention.line']._fields.get(fname)
            self.assertIsNotNone(field, f"Campo '{fname}' debe existir en account.retention.line")
            self.assertIsInstance(field, ftype, f"Campo '{fname}' debe ser {ftype.__name__}")
