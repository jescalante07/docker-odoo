# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PosDiscountRule(models.Model):
    _name = 'pos.discount.rule'

    name = fields.Char(string='Nombre de la Regla', required=True)
    hour_from = fields.Float(string='Hora Desde', required=True, help="Formato flotante, ej. 14.5 para las 14:30")
    hour_to = fields.Float(string='Hora Hasta', required=True, help="Formato flotante, ej. 18.0 para las 18:00")
    discount_percentage = fields.Float(string='Porcentaje de Descuento', required=True)

    @api.constrains('hour_from', 'hour_to', 'discount_percentage')
    def _check_values(self):
        for rule in self:
            if rule.hour_from < 0 or rule.hour_from >= 24 or rule.hour_to < 0 or rule.hour_to >= 24:
                raise ValidationError("Las horas deben estar en el rango de 0 a 24.")
            if rule.hour_from >= rule.hour_to:
                raise ValidationError("La hora de inicio debe ser menor que la hora de fin.")
            if rule.discount_percentage <= 0 or rule.discount_percentage > 100:
                raise ValidationError("El porcentaje de descuento debe ser mayor que 0 y menor o igual a 100.")

    @api.constrains('hour_from', 'hour_to')
    def _check_overlapping_rules(self):
        for rule in self:
            # Buscar reglas que se solapen en el horario
            overlapping_rule = self.search([
                ('id', '!=', rule.id),
                ('hour_from', '<', rule.hour_to),
                ('hour_to', '>', rule.hour_from),
            ], limit=1)
            if overlapping_rule:
                raise ValidationError(
                    f"La regla se solapa con una regla existente: '{overlapping_rule.name}' "
                    f"({overlapping_rule.hour_from} - {overlapping_rule.hour_to})."
                )