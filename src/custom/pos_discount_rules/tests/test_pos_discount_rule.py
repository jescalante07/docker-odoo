# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from unittest.mock import patch
from datetime import datetime
import pytz


class TestPosDiscountRule(TransactionCase):

    def setUp(self):
        super(TestPosDiscountRule, self).setUp()
        self.pos_rule_model = self.env['pos.discount.rule']
        self.pos_order_model = self.env['pos.order']

        # Datos mínimos para simular una orden
        self.product = self.env['product.product'].create({
            'name': 'Café Expreso',
            'available_in_pos': True,
            'list_price': 2.5,
        })
        self.partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        self.pos_config = self.env['pos.config'].create({'name': 'Shop Test'})
        self.pos_session = self.env['pos.session'].create({'config_id': self.pos_config.id})
        self.pos_session.start()

    def test_01_overlapping_rules_validation(self):
        """ Valida que no se puedan crear reglas con horarios solapados """
        self.pos_rule_model.create({
            'name': 'Happy Hour Tarde',
            'hour_from': 17.0,  # 5:00 PM
            'hour_to': 19.0,  # 7:00 PM
            'discount_percentage': 15.0
        })

        # Caso límite: Intento crear regla que arranca dentro del rango de la anterior
        with self.assertRaises(ValidationError):
            self.pos_rule_model.create({
                'name': 'Descuento Nocturno Solapado',
                'hour_from': 18.0,
                'hour_to': 20.0,
                'discount_percentage': 10.0
            })

    def test_02_order_within_discount_hours(self):
        """ Valida que se aplique el descuento si la orden entra en el rango """
        self.pos_rule_model.create({
            'name': 'Happy Hour Almuerzo',
            'hour_from': 12.0,
            'hour_to': 14.0,
            'discount_percentage': 20.0
        })

        # Simulamos estructura exacta enviada por el frontend PoS
        order_payload = {
            'data': {
                'amount_paid': 2.5,
                'amount_return': 0,
                'amount_tax': 0,
                'amount_total': 2.5,
                'pos_session_id': self.pos_session.id,
                'partner_id': self.partner.id,
                'lines': [
                    [0, 0, {
                        'product_id': self.product.id,
                        'qty': 1,
                        'price_unit': 2.5,
                        'discount': 0.0,
                    }]
                ],
            }
        }

        # Forzamos que la ejecución ocurra a las 13:00 (Dentro del rango)
        mock_now = datetime.now(pytz.timezone('UTC')).replace(hour=13, minute=0)
        with patch('odoo.addons.pos_happy_hour.models.pos_order.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_now

            # Ejecutamos el método del PoS
            res = self.pos_order_model._process_order(order_payload)
            order_id = self.pos_order_model.browse(res['id'])

            # Verificaciones
            self.assertEqual(order_id.lines[0].discount, 20.0, "El descuento del 20% debió aplicarse.")

    def test_03_order_outside_discount_hours(self):
        """ Valida que NO se aplique descuento fuera del rango """
        self.pos_rule_model.create({
            'name': 'Happy Hour Almuerzo',
            'hour_from': 12.0,
            'hour_to': 14.0,
            'discount_percentage': 20.0
        })

        order_payload = {
            'data': {
                'pos_session_id': self.pos_session.id,
                'lines': [[0, 0, {'product_id': self.product.id, 'qty': 1, 'price_unit': 2.5, 'discount': 0.0}]],
            }
        }

        # Forzamos ejecución a las 16:00 (Fuera del rango)
        mock_now = datetime.now(pytz.timezone('UTC')).replace(hour=16, minute=0)
        with patch('odoo.addons.pos_happy_hour.models.pos_order.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_now

            res = self.pos_order_model._process_order(order_payload)
            order_id = self.pos_order_model.browse(res['id'])

            self.assertEqual(order_id.lines[0].discount, 0.0, "No debe aplicar descuento fuera de hora.")