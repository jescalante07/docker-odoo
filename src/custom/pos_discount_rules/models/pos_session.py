# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
# -*- coding: utf-8 -*-
from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    # ------------------------------------------------------------------
    # Odoo 17 usa el patrón _loader_params_<model> + _get_pos_ui_<model>
    # para exponer datos al frontend al momento de cargar la sesión.
    # ------------------------------------------------------------------

    def _loader_params_pos_discount_rule(self):
        """
        Declara qué campos del modelo pos.discount.rule se enviarán
        al navegador cuando el POS se inicia.
        """
        return {
            'search_params': {
                'domain': [],
                'fields': ['name', 'hour_from', 'hour_to', 'discount_percentage'],
            }
        }

    def _get_pos_ui_pos_discount_rule(self, params):
        """
        Ejecuta la consulta y devuelve la lista de registros que el JS
        recibirá en loadedData['pos.discount.rule'].
        """
        return self.env['pos.discount.rule'].search_read(**params['search_params'])

    def _pos_ui_models_to_load(self):
        """
        Registra el modelo en la lista de modelos que el POS debe cargar.
        Odoo 17 itera esta lista y llama automáticamente a
        _loader_params_<model> y _get_pos_ui_<model> para cada entrada.
        """
        models_to_load = super()._pos_ui_models_to_load()
        models_to_load.append('pos.discount.rule')
        return models_to_load
