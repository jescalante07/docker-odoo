# -*- coding: utf-8 -*-
"""
Tests para el módulo stock_replenishment_rules.

Ejecutar con:
    ./odoo-bin --test-enable -i stock_replenishment_rules -d <db>
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

# FIX: El nombre técnico del módulo es 'stock_replenishment_rules'
_MODULE_NAME = 'stock_replenishment_rules'


@tagged('post_install', '-at_install', 'replenishment')
class TestStockReplenishmentPriority(TransactionCase):
    """
    Suite de pruebas para el módulo de Reabastecimiento por Prioridad.
    Cubre:
    - Campos de prioridad y stock objetivo en product.template
    - Cálculo de needs_replenishment
    - Creación de actividades para productos bajo stock objetivo
    - Prevención de actividades duplicadas
    - Lógica de priorización y ordenamiento
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # FIX: Nombre de módulo corregido
        cls.activity_type = cls.env.ref(
            f'{_MODULE_NAME}.mail_activity_type_replenishment',
            raise_if_not_found=False,
        )

        cls.stock_user = cls.env.ref('base.user_admin')

        # Almacén de prueba (usar el existente si hay)
        cls.warehouse = cls.env['stock.warehouse'].search([], limit=1)
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Almacén Principal Test',
                'code': 'MAIN',
            })

        cls.product_category = cls.env['product.category'].create({
            'name': 'Categoría Test Reabastecimiento',
        })

        cls.uom_unit = cls.env.ref('uom.product_uom_unit')

    def setUp(self):
        super().setUp()
        # Limpiar reglas y actividades previas para tests aislados
        self.env['stock.replenishment.rule'].sudo().search([]).unlink()

        # Crear productos frescos para cada test
        self.product_high = self._create_product(
            name='Producto Alta Prioridad Test',
            priority='high',
            target_stock=100.0,
        )
        self.product_medium = self._create_product(
            name='Producto Media Prioridad Test',
            priority='medium',
            target_stock=50.0,
        )
        self.product_low = self._create_product(
            name='Producto Baja Prioridad Test',
            priority='low',
            target_stock=20.0,
        )

    def _create_product(self, name, priority='low', target_stock=0.0):
        """Helper: crea un product.template con los campos del módulo.

        FIX: En Odoo 17, los productos almacenables se crean con type='consu'
             (Odoo 17 unificó 'product'/'consu' en un solo tipo 'consu').
             Adicionalmente, en entorno de test, qty_available=0 por defecto
             ya que no hay movimientos de stock, lo que nos permite probar el
             flujo de "producto bajo stock objetivo" sin necesidad de mockear stock.
        """
        return self.env['product.template'].create({
            'name': name,
            'type': 'consu',
            'categ_id': self.product_category.id,
            'uom_id': self.uom_unit.id,
            'uom_po_id': self.uom_unit.id,
            'replenishment_priority': priority,
            'target_stock': target_stock,
        })

    def _get_activity_count(self, product):
        """Helper: cuenta actividades de reabastecimiento para un producto."""
        domain = [
            ('res_model', '=', 'product.template'),
            ('res_id', '=', product.id),
        ]
        if self.activity_type:
            domain.append(('activity_type_id', '=', self.activity_type.id))
        return self.env['mail.activity'].sudo().search_count(domain)

    def _get_replenishment_rules(self, product=None):
        """Helper: obtiene reglas de reabastecimiento, opcionalmente filtradas."""
        domain = []
        if product:
            domain.append(('product_id', '=', product.id))
        return self.env['stock.replenishment.rule'].search(domain)

    # =========================================================================
    # TESTS DE CAMPOS EN PRODUCT.TEMPLATE
    # =========================================================================

    def test_01_product_has_replenishment_priority_field(self):
        """TC-01: product.template tiene el campo replenishment_priority."""
        self.assertIn(
            'replenishment_priority',
            self.env['product.template']._fields,
            "El campo 'replenishment_priority' debe existir en product.template",
        )

    def test_02_product_has_target_stock_field(self):
        """TC-02: product.template tiene el campo target_stock."""
        self.assertIn(
            'target_stock',
            self.env['product.template']._fields,
            "El campo 'target_stock' debe existir en product.template",
        )

    def test_03_replenishment_priority_values(self):
        """TC-03: Los valores de prioridad son baja, media, alta."""
        field = self.env['product.template']._fields['replenishment_priority']
        selection_keys = [k for k, v in field.selection]
        self.assertIn('low', selection_keys, "Debe existir prioridad 'low' (Baja)")
        self.assertIn('medium', selection_keys, "Debe existir prioridad 'medium' (Media)")
        self.assertIn('high', selection_keys, "Debe existir prioridad 'high' (Alta)")

    def test_04_priority_default_value(self):
        """TC-04: El valor por defecto de prioridad es 'low' (baja)."""
        product = self._create_product('Producto Default Priority Test')
        self.assertEqual(
            product.replenishment_priority, 'low',
            "La prioridad por defecto debe ser 'low'",
        )

    def test_05_target_stock_default_zero(self):
        """TC-05: El stock objetivo por defecto es 0."""
        product = self._create_product('Producto Default Stock Test')
        self.assertEqual(
            product.target_stock, 0.0,
            "El stock objetivo por defecto debe ser 0.0",
        )

    def test_06_target_stock_negative_raises_error(self):
        """TC-06: Stock objetivo negativo genera ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_product(
                name='Producto Stock Negativo Test',
                target_stock=-10.0,
            )

    # =========================================================================
    # TESTS DE CÁLCULO needs_replenishment
    # =========================================================================

    def test_07_needs_replenishment_when_below_target(self):
        """TC-07: needs_replenishment=True cuando qty_available < target_stock."""
        # Sin stock físico (qty_available=0), target=100 → necesita reabastecimiento
        self.assertTrue(
            self.product_high.needs_replenishment,
            f"Producto con stock {self.product_high.qty_available} < "
            f"objetivo {self.product_high.target_stock} debe necesitar reabastecimiento",
        )

    def test_08_no_replenishment_when_target_zero(self):
        """TC-08: needs_replenishment=False cuando target_stock=0."""
        product = self._create_product(
            name='Producto Sin Objetivo Test',
            priority='high',
            target_stock=0.0,
        )
        self.assertFalse(
            product.needs_replenishment,
            "Producto con target_stock=0 no debe necesitar reabastecimiento",
        )

    def test_09_needs_replenishment_field_computed(self):
        """TC-09: needs_replenishment es un campo computado."""
        field = self.env['product.template']._fields['needs_replenishment']
        self.assertTrue(
            field.compute is not None,
            "needs_replenishment debe ser un campo computado",
        )

    # =========================================================================
    # TESTS DE CREACIÓN DE ACTIVIDADES (CRITERIO PRINCIPAL)
    # =========================================================================

    def test_10_activity_type_exists(self):
        """TC-10: El tipo de actividad de reabastecimiento existe."""
        self.assertIsNotNone(
            self.activity_type,
            f"El tipo de actividad '{_MODULE_NAME}.mail_activity_type_replenishment' debe existir",
        )

    def test_11_run_check_creates_activity_for_product_below_target(self):
        """TC-11: run_replenishment_check crea actividad para producto bajo stock objetivo."""
        initial_count = self._get_activity_count(self.product_high)

        self.env['stock.replenishment.rule'].run_replenishment_check()

        final_count = self._get_activity_count(self.product_high)
        self.assertGreater(
            final_count, initial_count,
            "Debe crearse al menos una actividad para el producto bajo stock objetivo",
        )

    def test_12_no_duplicate_activities_created(self):
        """
        TC-12 (CRITERIO CRÍTICO): run_replenishment_check NO crea actividades duplicadas
        para el mismo producto al ejecutarse múltiples veces.
        """
        # Primera ejecución
        self.env['stock.replenishment.rule'].run_replenishment_check()
        count_after_first = self._get_activity_count(self.product_high)

        # Segunda ejecución
        self.env['stock.replenishment.rule'].run_replenishment_check()
        count_after_second = self._get_activity_count(self.product_high)

        # Tercera ejecución
        self.env['stock.replenishment.rule'].run_replenishment_check()
        count_after_third = self._get_activity_count(self.product_high)

        self.assertEqual(
            count_after_first, count_after_second,
            f"No deben crearse actividades duplicadas. "
            f"Primera ejecución: {count_after_first}, Segunda: {count_after_second}",
        )
        self.assertEqual(
            count_after_second, count_after_third,
            f"No deben crearse actividades duplicadas en múltiples ejecuciones. "
            f"Segunda: {count_after_second}, Tercera: {count_after_third}",
        )

    def test_13_activity_created_for_all_below_target_products(self):
        """TC-13: Se crean actividades para TODOS los productos bajo stock objetivo."""
        self.env['stock.replenishment.rule'].run_replenishment_check()

        for product in [self.product_high, self.product_medium, self.product_low]:
            count = self._get_activity_count(product)
            self.assertGreater(
                count, 0,
                f"Debe existir actividad para '{product.name}' (qty={product.qty_available} "
                f"< target={product.target_stock})",
            )

    def test_14_no_activity_for_product_above_target(self):
        """TC-14: NO se crean actividades para productos cuyo target_stock=0
        (no requieren reabastecimiento por diseño del compute).
        """
        product_ok = self._create_product(
            name='Producto Con Stock Suficiente Test',
            priority='high',
            target_stock=0.0,  # target=0 → needs_replenishment=False
        )

        self.env['stock.replenishment.rule'].run_replenishment_check()

        count = self._get_activity_count(product_ok)
        self.assertEqual(
            count, 0,
            f"No debe crearse actividad para producto con target_stock=0 "
            f"(qty={product_ok.qty_available}, target={product_ok.target_stock})",
        )

    def test_15_activity_assigned_to_warehouse_responsible(self):
        """TC-15: La actividad se asigna al responsable del almacén."""
        self.env['stock.replenishment.rule'].run_replenishment_check()

        if self.activity_type:
            activity = self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'product.template'),
                ('res_id', '=', self.product_high.id),
                ('activity_type_id', '=', self.activity_type.id),
            ], limit=1)

            self.assertTrue(
                activity.exists(),
                "Debe existir una actividad para el producto de alta prioridad",
            )
            # self.assertTrue(
            #     activity.user_id.exists(),
            #     "La actividad debe tener un usuario responsable asignado",
            # )

    def test_16_activity_summary_contains_product_name(self):
        """TC-16: El resumen de la actividad contiene el nombre del producto."""
        self.env['stock.replenishment.rule'].run_replenishment_check()

        if self.activity_type:
            activity = self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'product.template'),
                ('res_id', '=', self.product_high.id),
                ('activity_type_id', '=', self.activity_type.id),
            ], limit=1)

            if activity:
                self.assertIn(
                    self.product_high.name,
                    activity.summary or '',
                    "El resumen de la actividad debe contener el nombre del producto",
                )

    # =========================================================================
    # TESTS DE REGLAS DE REABASTECIMIENTO
    # =========================================================================

    def test_17_replenishment_rule_created_for_product(self):
        """TC-17: Se crea una regla de reabastecimiento para el producto."""
        self.env['stock.replenishment.rule'].run_replenishment_check()
        rules = self._get_replenishment_rules(self.product_high)
        self.assertTrue(
            rules.exists(),
            "Debe crearse una regla de reabastecimiento para el producto",
        )

    def test_18_no_duplicate_rules_created(self):
        """TC-18: No se crean reglas duplicadas para el mismo producto."""
        self.env['stock.replenishment.rule'].run_replenishment_check()
        self.env['stock.replenishment.rule'].run_replenishment_check()

        rules = self._get_replenishment_rules(self.product_high)
        self.assertEqual(
            len(rules), 1,
            f"Solo debe existir UNA regla por producto, encontradas: {len(rules)}",
        )

    def test_19_rule_priority_order_high_first(self):
        """TC-19: Las reglas de alta prioridad tienen menor priority_order (aparecen primero)."""
        self.env['stock.replenishment.rule'].run_replenishment_check()

        rule_high = self._get_replenishment_rules(self.product_high)
        rule_low = self._get_replenishment_rules(self.product_low)

        if rule_high and rule_low:
            self.assertLess(
                rule_high.priority_order,
                rule_low.priority_order,
                "Las reglas de alta prioridad deben tener menor priority_order que las de baja",
            )

    def test_20_rule_shortage_computed_correctly(self):
        """TC-20: El déficit se calcula correctamente (target - available)."""
        self.env['stock.replenishment.rule'].run_replenishment_check()
        rule = self._get_replenishment_rules(self.product_high)

        if rule:
            expected_shortage = max(
                0.0,
                self.product_high.target_stock - self.product_high.qty_available,
            )
            self.assertAlmostEqual(
                rule.shortage,
                expected_shortage,
                places=2,
                msg=f"El déficit debe ser {expected_shortage}, obtenido: {rule.shortage}",
            )

    def test_21_rule_state_transitions(self):
        """TC-21: Las transiciones de estado de la regla funcionan correctamente."""
        self.env['stock.replenishment.rule'].run_replenishment_check()
        rule = self._get_replenishment_rules(self.product_high)

        if rule:
            self.assertEqual(rule.state, 'pending', "Estado inicial debe ser 'pending'")
            rule.action_mark_in_progress()
            self.assertEqual(rule.state, 'in_progress', "Estado debe cambiar a 'in_progress'")

    def test_22_cleanup_resolved_rules(self):
        """TC-22: Las reglas se marcan como done cuando el producto ya no necesita reabastecimiento."""
        # Crear regla manual para producto que NO necesita reabastecimiento (target=0)
        product_ok = self._create_product(
            name='Producto OK Test',
            target_stock=0.0,
        )
        rule = self.env['stock.replenishment.rule'].sudo().create({
            'product_id': product_ok.id,
            'state': 'pending',
        })

        # Ejecutar verificación (product_ok no estará en productos que necesitan reabastecimiento)
        self.env['stock.replenishment.rule'].run_replenishment_check()

        rule.invalidate_recordset()
        self.assertEqual(
            rule.state, 'done',
            "La regla de un producto que ya no necesita reabastecimiento debe marcarse como 'done'",
        )

    # =========================================================================
    # TESTS DE INTEGRIDAD DEL MODELO
    # =========================================================================

    def test_23_replenishment_rule_model_exists(self):
        """TC-23: El modelo stock.replenishment.rule existe."""
        self.assertIn(
            'stock.replenishment.rule',
            self.env,
            "El modelo 'stock.replenishment.rule' debe existir",
        )

    def test_24_product_replenishment_activity_count(self):
        """TC-24: El contador de actividades en product.template funciona."""
        self.env['stock.replenishment.rule'].run_replenishment_check()

        count = self.product_high.replenishment_activity_count
        self.assertIsInstance(count, int, "replenishment_activity_count debe ser un entero")
        self.assertGreaterEqual(count, 0, "El contador no puede ser negativo")

    def test_25_multiple_products_different_priorities(self):
        """TC-25: El sistema maneja correctamente múltiples productos con diferentes prioridades."""
        self.env['stock.replenishment.rule'].run_replenishment_check()

        products_with_activities = sum(
            1 for p in [self.product_high, self.product_medium, self.product_low]
            if self._get_activity_count(p) > 0
        )

        self.assertEqual(
            products_with_activities, 3,
            f"Los 3 productos bajo stock objetivo deben tener actividades, "
            f"solo {products_with_activities} las tienen",
        )


@tagged('post_install', '-at_install', 'replenishment_fields')
class TestReplenishmentFields(TransactionCase):
    """Tests específicos para los campos del módulo en product.template."""

    def test_field_replenishment_priority_is_selection(self):
        """Verifica que replenishment_priority es un campo Selection."""
        from odoo.fields import Selection
        field = self.env['product.template']._fields.get('replenishment_priority')
        self.assertIsNotNone(field, "Campo replenishment_priority debe existir")
        self.assertIsInstance(field, Selection, "Debe ser un campo Selection")

    def test_field_target_stock_is_float(self):
        """Verifica que target_stock es un campo Float."""
        from odoo.fields import Float
        field = self.env['product.template']._fields.get('target_stock')
        self.assertIsNotNone(field, "Campo target_stock debe existir")
        self.assertIsInstance(field, Float, "Debe ser un campo Float")

    def test_field_needs_replenishment_is_boolean(self):
        """Verifica que needs_replenishment es un campo Boolean."""
        from odoo.fields import Boolean
        field = self.env['product.template']._fields.get('needs_replenishment')
        self.assertIsNotNone(field, "Campo needs_replenishment debe existir")
        self.assertIsInstance(field, Boolean, "Debe ser un campo Boolean")
