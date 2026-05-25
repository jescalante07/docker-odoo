# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'stock_operation_tag')
class TestStockOperationTag(TransactionCase):
    """Suite de pruebas para el modelo stock.operation.tag."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.OperationTag = cls.env['stock.operation.tag']
        cls.ProductTemplate = cls.env['product.template']

        # ── Crear etiquetas de prueba ─────────────────────────────────────────
        cls.tag_picking = cls.OperationTag.create({
            'name': 'Test Picking Rápido',
            'color': 10,
            'operation_type': 'picking',
            'description': 'Etiqueta de prueba para picking.',
        })

        cls.tag_storage = cls.OperationTag.create({
            'name': 'Test Almacén Alto',
            'color': 2,
            'operation_type': 'storage',
            'description': 'Etiqueta de prueba para almacenamiento.',
        })

        cls.tag_dispatch = cls.OperationTag.create({
            'name': 'Test Despacho Express',
            'color': 7,
            'operation_type': 'dispatch',
            'description': 'Etiqueta de prueba para despacho.',
        })

        cls.tag_quality = cls.OperationTag.create({
            'name': 'Test Control Calidad',
            'color': 5,
            'operation_type': 'quality',
        })

        # ── Crear productos de prueba ─────────────────────────────────────────
        cls.product_a = cls.ProductTemplate.create({
            'name': 'Producto Test A',
            'type': 'consu',
        })

        cls.product_b = cls.ProductTemplate.create({
            'name': 'Producto Test B',
            'type': 'consu',
        })

        cls.product_c = cls.ProductTemplate.create({
            'name': 'Producto Test C - Sin Etiquetas',
            'type': 'consu',
        })

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. CREACIÓN DE ETIQUETAS
    # ═══════════════════════════════════════════════════════════════════════════

    def test_01_tag_creation_basic(self):
        """Valida que se puede crear una etiqueta con campos mínimos requeridos."""
        tag = self.OperationTag.create({
            'name': 'Etiqueta Básica',
            'operation_type': 'reception',
        })
        self.assertTrue(tag.id, 'La etiqueta debe tener un ID válido.')
        self.assertEqual(tag.name, 'Etiqueta Básica')
        self.assertEqual(tag.operation_type, 'reception')
        self.assertTrue(tag.active, 'Las etiquetas nuevas deben estar activas por defecto.')
        self.assertEqual(tag.color, 0, 'El color por defecto debe ser 0.')

    def test_02_tag_creation_all_fields(self):
        """Valida la creación con todos los campos configurados."""
        tag = self.OperationTag.create({
            'name': 'Etiqueta Completa',
            'color': 8,
            'operation_type': 'dispatch',
            'description': 'Descripción detallada de la etiqueta.',
            'active': True,
        })
        self.assertEqual(tag.color, 8)
        self.assertEqual(tag.description, 'Descripción detallada de la etiqueta.')
        self.assertEqual(tag.operation_type, 'dispatch')

    def test_03_tag_all_operation_types(self):
        """Valida que se pueden crear etiquetas para todos los tipos de operación."""
        operation_types = ['picking', 'storage', 'dispatch', 'reception', 'quality', 'other']
        for op_type in operation_types:
            tag = self.OperationTag.create({
                'name': f'Tag Test {op_type}',
                'operation_type': op_type,
            })
            self.assertEqual(
                tag.operation_type, op_type,
                f'El tipo de operación debe ser "{op_type}"'
            )

    def test_04_tag_unique_constraint(self):
        """Valida que no se pueden crear dos etiquetas con el mismo nombre y tipo."""
        self.OperationTag.create({
            'name': 'Etiqueta Única',
            'operation_type': 'picking',
        })
        with self.assertRaises(Exception, msg='Debe lanzar error por nombre duplicado en el mismo tipo'):
            self.OperationTag.create({
                'name': 'Etiqueta Única',
                'operation_type': 'picking',
            })

    def test_05_tag_same_name_different_type(self):
        """Valida que el mismo nombre puede usarse en tipos de operación distintos."""
        tag1 = self.OperationTag.create({
            'name': 'Prioridad Alta',
            'operation_type': 'picking',
        })
        tag2 = self.OperationTag.create({
            'name': 'Prioridad Alta',
            'operation_type': 'dispatch',
        })
        self.assertNotEqual(tag1.id, tag2.id, 'Deben ser registros distintos.')
        self.assertEqual(tag1.name, tag2.name)
        self.assertNotEqual(tag1.operation_type, tag2.operation_type)

    def test_06_tag_color_validation(self):
        """Valida que el color debe estar en rango 0-11."""
        with self.assertRaises(ValidationError, msg='Color 12 debe fallar validación'):
            self.OperationTag.create({
                'name': 'Color Inválido',
                'operation_type': 'other',
                'color': 12,
            })

    def test_07_tag_color_boundary_values(self):
        """Valida los valores límite del color (0 y 11)."""
        tag_min = self.OperationTag.create({
            'name': 'Color Mínimo',
            'operation_type': 'other',
            'color': 0,
        })
        tag_max = self.OperationTag.create({
            'name': 'Color Máximo',
            'operation_type': 'other',
            'color': 11,
        })
        self.assertEqual(tag_min.color, 0)
        self.assertEqual(tag_max.color, 11)

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. ASIGNACIÓN DE ETIQUETAS A PRODUCTOS
    # ═══════════════════════════════════════════════════════════════════════════

    def test_10_assign_single_tag_to_product(self):
        """Valida la asignación de una sola etiqueta a un producto."""
        self.product_a.operation_tag_ids = [(4, self.tag_picking.id)]
        self.assertIn(
            self.tag_picking,
            self.product_a.operation_tag_ids,
            'La etiqueta debe estar asignada al producto.'
        )

    def test_11_assign_multiple_tags_to_product(self):
        """Valida la asignación de múltiples etiquetas a un producto."""
        self.product_b.operation_tag_ids = [
            (6, 0, [self.tag_picking.id, self.tag_storage.id, self.tag_dispatch.id])
        ]
        self.assertEqual(
            len(self.product_b.operation_tag_ids), 3,
            'El producto debe tener exactamente 3 etiquetas.'
        )
        self.assertIn(self.tag_picking, self.product_b.operation_tag_ids)
        self.assertIn(self.tag_storage, self.product_b.operation_tag_ids)
        self.assertIn(self.tag_dispatch, self.product_b.operation_tag_ids)

    def test_12_remove_tag_from_product(self):
        """Valida la remoción de una etiqueta específica de un producto."""
        self.product_a.operation_tag_ids = [
            (6, 0, [self.tag_picking.id, self.tag_quality.id])
        ]
        self.assertEqual(len(self.product_a.operation_tag_ids), 2)

        # Remover solo una etiqueta
        self.product_a.operation_tag_ids = [(3, self.tag_picking.id)]
        self.assertEqual(len(self.product_a.operation_tag_ids), 1)
        self.assertNotIn(self.tag_picking, self.product_a.operation_tag_ids)
        self.assertIn(self.tag_quality, self.product_a.operation_tag_ids)

    def test_13_remove_all_tags_from_product(self):
        """Valida la remoción de todas las etiquetas usando action_remove_all_tags."""
        self.product_a.operation_tag_ids = [
            (6, 0, [self.tag_picking.id, self.tag_storage.id])
        ]
        self.assertTrue(len(self.product_a.operation_tag_ids) > 0)

        result = self.product_a.action_remove_all_tags()
        self.assertEqual(len(self.product_a.operation_tag_ids), 0, 'No deben quedar etiquetas.')
        self.assertEqual(result['type'], 'ir.actions.client', 'Debe retornar notificación.')

    def test_14_many2many_bidirectional(self):
        """Valida la relación bidireccional many2many."""
        self.product_a.operation_tag_ids = [(4, self.tag_picking.id)]
        self.product_b.operation_tag_ids = [(4, self.tag_picking.id)]

        self.assertIn(self.product_a, self.tag_picking.product_ids)
        self.assertIn(self.product_b, self.tag_picking.product_ids)

    def test_15_product_count_in_tag(self):
        """Valida el conteo de productos en una etiqueta."""
        # Crear etiqueta nueva para evitar interferencia con otros tests
        tag_count_test = self.OperationTag.create({
            'name': 'Tag Count Test',
            'operation_type': 'other',
        })
        self.assertEqual(tag_count_test.product_count, 0)

        self.product_a.operation_tag_ids = [(4, tag_count_test.id)]
        self.assertEqual(tag_count_test.product_count, 1)

        self.product_b.operation_tag_ids = [(4, tag_count_test.id)]
        self.assertEqual(tag_count_test.product_count, 2)

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. TIPO DE OPERACIÓN PRIMARIO COMPUTADO
    # ═══════════════════════════════════════════════════════════════════════════

    def test_20_primary_type_unclassified(self):
        """Producto sin etiquetas → tipo 'unclassified'."""
        # Asegurar que el producto no tiene etiquetas
        self.product_c.operation_tag_ids = [(5, 0, 0)]
        self.assertEqual(
            self.product_c.primary_operation_type, 'unclassified',
            'Sin etiquetas, el tipo primario debe ser "unclassified".'
        )

    def test_21_primary_type_single_type(self):
        """Producto con etiquetas de un solo tipo → ese tipo."""
        self.product_a.operation_tag_ids = [(4, self.tag_picking.id)]
        self.assertEqual(
            self.product_a.primary_operation_type, 'picking',
            'Con solo etiquetas de picking, el tipo primario debe ser "picking".'
        )

    def test_22_primary_type_mixed(self):
        """Producto con etiquetas de múltiples tipos → 'mixed'."""
        self.product_b.operation_tag_ids = [
            (6, 0, [self.tag_picking.id, self.tag_storage.id])
        ]
        self.assertEqual(
            self.product_b.primary_operation_type, 'mixed',
            'Con etiquetas de distintos tipos, el tipo primario debe ser "mixed".'
        )

    def test_23_primary_type_updates_on_tag_change(self):
        """Valida que el tipo primario se recalcula al modificar etiquetas."""
        self.product_a.operation_tag_ids = [(6, 0, [self.tag_picking.id])]
        self.assertEqual(self.product_a.primary_operation_type, 'picking')

        # Agregar etiqueta de otro tipo → debe cambiar a 'mixed'
        self.product_a.operation_tag_ids = [(4, self.tag_dispatch.id)]
        self.assertEqual(self.product_a.primary_operation_type, 'mixed')

        # Quitar el tag de dispatch → debe volver a 'picking'
        self.product_a.operation_tag_ids = [(3, self.tag_dispatch.id)]
        self.assertEqual(self.product_a.primary_operation_type, 'picking')

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. ARCHIVADO / DESARCHIVADO
    # ═══════════════════════════════════════════════════════════════════════════

    def test_30_archive_tag(self):
        """Valida el archivado de una etiqueta."""
        tag = self.OperationTag.create({
            'name': 'Etiqueta a Archivar',
            'operation_type': 'other',
        })
        self.assertTrue(tag.active)
        tag.active = False
        self.assertFalse(tag.active, 'La etiqueta debe estar archivada.')

    def test_31_archived_tag_not_in_active_search(self):
        """Valida que las etiquetas archivadas no aparecen en búsquedas normales."""
        tag = self.OperationTag.create({
            'name': 'Etiqueta Archivada Búsqueda',
            'operation_type': 'other',
        })
        tag.active = False

        found = self.OperationTag.search([('name', '=', 'Etiqueta Archivada Búsqueda')])
        self.assertFalse(found, 'Las etiquetas archivadas no deben aparecer en búsquedas activas.')

        found_with_archived = self.OperationTag.with_context(active_test=False).search(
            [('name', '=', 'Etiqueta Archivada Búsqueda')]
        )
        self.assertTrue(found_with_archived, 'Con active_test=False, debe encontrarse la etiqueta archivada.')

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. WIZARD DE ACCIÓN RÁPIDA
    # ═══════════════════════════════════════════════════════════════════════════

    def test_40_quick_assign_action_opens_wizard(self):
        """Valida que la acción rápida retorna la apertura del wizard."""
        result = self.product_a.action_quick_assign_tags()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'stock.operation.tag.wizard')
        self.assertEqual(result['target'], 'new')
        self.assertEqual(result['context']['default_product_id'], self.product_a.id)

    def test_41_wizard_apply_tags(self):
        """Valida que el wizard aplica correctamente las etiquetas."""
        wizard = self.env['stock.operation.tag.wizard'].create({
            'product_id': self.product_c.id,
            'tag_ids': [(6, 0, [self.tag_picking.id, self.tag_quality.id])],
        })
        wizard.action_apply()

        self.assertIn(self.tag_picking, self.product_c.operation_tag_ids)
        self.assertIn(self.tag_quality, self.product_c.operation_tag_ids)
        self.assertEqual(len(self.product_c.operation_tag_ids), 2)

    def test_42_wizard_clear_tags(self):
        """Valida que el wizard limpia las etiquetas seleccionadas."""
        wizard = self.env['stock.operation.tag.wizard'].create({
            'product_id': self.product_a.id,
            'tag_ids': [(6, 0, [self.tag_picking.id, self.tag_storage.id])],
        })
        self.assertEqual(len(wizard.tag_ids), 2)

        wizard.action_clear_tags()
        self.assertEqual(len(wizard.tag_ids), 0, 'El wizard debe quedar sin etiquetas seleccionadas.')

    def test_43_wizard_add_by_type(self):
        """Valida que el wizard puede añadir todas las etiquetas de un tipo."""
        wizard = self.env['stock.operation.tag.wizard'].create({
            'product_id': self.product_a.id,
            'filter_operation_type': 'picking',
        })

        all_picking_tags = self.OperationTag.search([('operation_type', '=', 'picking')])
        wizard.action_add_by_type()

        for tag in all_picking_tags:
            self.assertIn(tag, wizard.tag_ids, f'La etiqueta {tag.name} debe estar en el wizard.')

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. VISUALIZACIÓN / AGRUPACIÓN KANBAN
    # ═══════════════════════════════════════════════════════════════════════════

    def test_50_group_by_operation_tags(self):
        """Valida la agrupación de productos por etiquetas operativas."""
        # Asignar etiquetas
        self.product_a.operation_tag_ids = [(6, 0, [self.tag_picking.id])]
        self.product_b.operation_tag_ids = [(6, 0, [self.tag_storage.id])]

        # Leer productos agrupados por etiquetas
        groups = self.ProductTemplate.read_group(
            domain=[('id', 'in', [self.product_a.id, self.product_b.id])],
            fields=['operation_tag_ids'],
            groupby=['operation_tag_ids'],
        )
        self.assertTrue(len(groups) > 0, 'Debe haber al menos un grupo.')
        group_tag_ids = [g.get('operation_tag_ids') for g in groups]
        self.assertIn(self.tag_picking.id, group_tag_ids)
        self.assertIn(self.tag_storage.id, group_tag_ids)

    def test_51_group_by_primary_operation_type(self):
        """Valida la agrupación de productos por tipo de operación primario."""
        self.product_a.operation_tag_ids = [(6, 0, [self.tag_picking.id])]
        self.product_b.operation_tag_ids = [(6, 0, [self.tag_dispatch.id])]

        groups = self.ProductTemplate.read_group(
            domain=[('id', 'in', [self.product_a.id, self.product_b.id])],
            fields=['primary_operation_type'],
            groupby=['primary_operation_type'],
        )
        group_types = [g.get('primary_operation_type') for g in groups]
        self.assertIn('picking', group_types)
        self.assertIn('dispatch', group_types)

    def test_52_filter_by_operation_type(self):
        """Valida el filtro de productos por tipo de operación a través de etiquetas."""
        self.product_a.operation_tag_ids = [(6, 0, [self.tag_picking.id])]
        self.product_b.operation_tag_ids = [(6, 0, [self.tag_storage.id])]

        picking_products = self.ProductTemplate.search([
            ('operation_tag_ids.operation_type', '=', 'picking'),
            ('id', 'in', [self.product_a.id, self.product_b.id]),
        ])
        self.assertIn(self.product_a, picking_products)
        self.assertNotIn(self.product_b, picking_products)

    def test_53_filter_unclassified_products(self):
        """Valida el filtro de productos sin etiquetas operativas."""
        self.product_a.operation_tag_ids = [(4, self.tag_picking.id)]
        self.product_c.operation_tag_ids = [(5, 0, 0)]  # Sin etiquetas

        unclassified = self.ProductTemplate.search([
            ('operation_tag_ids', '=', False),
            ('id', 'in', [self.product_a.id, self.product_c.id]),
        ])
        self.assertIn(self.product_c, unclassified)
        self.assertNotIn(self.product_a, unclassified)

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. ACCIÓN PARA VER PRODUCTOS DESDE ETIQUETA
    # ═══════════════════════════════════════════════════════════════════════════

    def test_60_tag_action_view_products(self):
        """Valida que la acción view_products retorna la acción correcta."""
        self.product_a.operation_tag_ids = [(4, self.tag_picking.id)]

        result = self.tag_picking.action_view_products()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'product.template')
        self.assertIn('operation_tag_ids', str(result['domain']))

    def test_61_tag_count_auto_updates(self):
        """Valida que el conteo de etiquetas del producto se actualiza automáticamente."""
        self.product_a.operation_tag_ids = [(5, 0, 0)]  # Limpiar
        self.assertEqual(self.product_a.operation_tag_count, 0)

        self.product_a.operation_tag_ids = [(4, self.tag_picking.id)]
        self.assertEqual(self.product_a.operation_tag_count, 1)

        self.product_a.operation_tag_ids = [(4, self.tag_storage.id)]
        self.assertEqual(self.product_a.operation_tag_count, 2)


@tagged('post_install', '-at_install', 'stock_operation_tag')
class TestStockOperationTagIntegration(TransactionCase):
    """Tests de integración del módulo con el inventario de Odoo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.OperationTag = cls.env['stock.operation.tag']
        cls.ProductTemplate = cls.env['product.template']

    def test_integration_complete_workflow(self):
        """
        Test de integración que valida el flujo completo:
        1. Crear etiquetas por tipo de operación
        2. Crear productos
        3. Asignar etiquetas mediante wizard
        4. Verificar visualización kanban (agrupación)
        5. Remover etiquetas
        """
        # 1. Crear etiquetas
        tag_p = self.OperationTag.create({'name': 'Integración Picking', 'operation_type': 'picking', 'color': 10})
        tag_s = self.OperationTag.create({'name': 'Integración Storage', 'operation_type': 'storage', 'color': 2})
        tag_d = self.OperationTag.create({'name': 'Integración Dispatch', 'operation_type': 'dispatch', 'color': 7})

        # 2. Crear productos
        prod_1 = self.ProductTemplate.create({'name': 'Producto Integración 1', 'type': 'consu'})
        prod_2 = self.ProductTemplate.create({'name': 'Producto Integración 2', 'type': 'consu'})

        # 3. Asignar via wizard
        wizard_1 = self.env['stock.operation.tag.wizard'].create({
            'product_id': prod_1.id,
            'tag_ids': [(6, 0, [tag_p.id])],
        })
        wizard_1.action_apply()

        wizard_2 = self.env['stock.operation.tag.wizard'].create({
            'product_id': prod_2.id,
            'tag_ids': [(6, 0, [tag_s.id, tag_d.id])],
        })
        wizard_2.action_apply()

        # 4. Verificar asignaciones
        self.assertIn(tag_p, prod_1.operation_tag_ids)
        self.assertEqual(prod_1.primary_operation_type, 'picking')

        self.assertIn(tag_s, prod_2.operation_tag_ids)
        self.assertIn(tag_d, prod_2.operation_tag_ids)
        self.assertEqual(prod_2.primary_operation_type, 'mixed')

        # 5. Verificar agrupación kanban por etiquetas
        groups = self.ProductTemplate.read_group(
            domain=[('id', 'in', [prod_1.id, prod_2.id])],
            fields=['operation_tag_ids'],
            groupby=['operation_tag_ids'],
        )
        self.assertTrue(len(groups) >= 2, 'Debe haber al menos 2 grupos.')

        # 6. Remover etiquetas
        prod_1.action_remove_all_tags()
        self.assertEqual(len(prod_1.operation_tag_ids), 0)
        self.assertEqual(prod_1.primary_operation_type, 'unclassified')
