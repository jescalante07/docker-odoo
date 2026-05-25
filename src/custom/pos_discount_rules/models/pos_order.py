# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime
import pytz


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, draft=False, existing_order=False):
        """
        Extendemos el procesamiento de la orden para aplicar el descuento por horario
        antes de que se cree formalmente el registro en la base de datos.
        """
        pos_order_data = order.get('data', {})
        date_order_str = pos_order_data.get('name')  # El PoS suele mandar la fecha formateada o en date_order

        # Obtenemos la hora actual en base a la fecha de la orden (o la del servidor si falla)
        # Nota: En un entorno de producción real, es crucial manejar la zona horaria del PoS Config
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        now_local = datetime.now(user_tz)
        float_time = now_local.hour + now_local.minute / 60.0

        # Buscar si aplica alguna regla
        rule = self.env['pos.discount.rule'].search([
            ('hour_from', '<=', float_time),
            ('hour_to', '>=', float_time)
        ], limit=1)  # El constraint evita que haya más de una válida

        if rule and pos_order_data.get('lines'):
            for line_wrapper in pos_order_data['lines']:
                line = line_wrapper[2]  # Formato comando Odoo (0, 0, dict_valores)

                # Validación para evitar múltiples descuentos incompatibles
                # Si la línea ya trae un descuento del frontend (ej. un descuento manual), lo respetamos o lo ignoramos
                if not line.get('discount') or line.get('discount') == 0.0:
                    line['discount'] = rule.discount_percentage

        return super(PosOrder, self)._process_order(order, draft, existing_order)