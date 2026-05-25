# Copyright (C) 2026 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

_MODULE_NAME = 'stock_replenishment_rules'


class StockReplenishmentRule(models.Model):
    _name = 'stock.replenishment.rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Regla de Reabastecimiento por Prioridad'
    _order = 'priority_order asc, product_id asc'


    @api.depends('product_id', 'product_id.name')
    def _compute_name(self):
        for rule in self:
            if rule.product_id:
                priority_label = dict(
                    rule.product_id._fields['replenishment_priority'].selection
                ).get(rule.product_id.replenishment_priority, '')
                rule.name = f'[{priority_label}] {rule.product_id.name}'
            else:
                rule.name = _('Nueva Regla')

    @api.depends('replenishment_priority')
    def _compute_priority_order(self):
        priority_map = {'high': 1, 'medium': 2, 'low': 3}
        for rule in self:
            rule.priority_order = priority_map.get(rule.replenishment_priority, 99)

    @api.depends('qty_available', 'target_stock')
    def _compute_shortage(self):
        for rule in self:
            rule.shortage = max(0.0, rule.target_stock - rule.qty_available)

    def _compute_warehouse_responsible(self):
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        responsible = self.env.user
        for rule in self:
            rule.warehouse_responsible_id = self.env.user

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )

    product_id = fields.Many2one(
        comodel_name='product.template',
        string='Producto',
        required=True,
        ondelete='cascade',
        index=True,
    )

    replenishment_priority = fields.Selection(
        related='product_id.replenishment_priority',
        string='Prioridad',
        store=True,
        readonly=True,
    )

    priority_order = fields.Integer(
        string='Orden de Prioridad',
        compute='_compute_priority_order',
        store=True,
        help='Valor numérico para ordenar por prioridad (1=Alta, 2=Media, 3=Baja).',
    )

    qty_available = fields.Float(
        string='Cantidad Disponible',
        related='product_id.qty_available',
        readonly=True,
    )

    target_stock = fields.Float(
        related='product_id.target_stock',
        string='Stock Objetivo',
        readonly=True,
    )

    shortage = fields.Float(
        string='Déficit',
        compute='_compute_shortage',
        store=True,
        help='Diferencia entre el stock objetivo y el stock disponible.',
    )

    activity_id = fields.Many2one(
        comodel_name='mail.activity',
        string='Actividad Generada',
        readonly=True,
        ondelete='set null',
    )

    state = fields.Selection(
        selection=[
            ('pending', 'Pendiente'),
            ('in_progress', 'En Proceso'),
            ('done', 'Completado'),
        ],
        string='Estado',
        default='pending',
        tracking=True,
    )

    warehouse_responsible_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsable del Almacén',
        default=lambda self: self.env.user,
        store=True,
    )


    # -------------------------------------------------------------------------
    # Métodos de negocio principales
    # -------------------------------------------------------------------------

    @api.model
    def run_replenishment_check(self):
        """
        Método principal llamado por el cron job.
        Identifica productos bajo stock objetivo y genera/actualiza actividades.
        Evita crear actividades duplicadas para el mismo producto.
        """
        _logger.info('Iniciando verificación de reabastecimiento por prioridad...')

        self_sudo = self.sudo()

        activity_type = self_sudo._get_replenishment_activity_type()
        if not activity_type:
            _logger.warning('Tipo de actividad de reabastecimiento no encontrado.')
            return

        # Buscar productos que necesitan reabastecimiento
        products_needing = self.env['product.template'].sudo().search([
            ('type', '!=', 'service'),
            ('target_stock', '>', 0),
            #('needs_replenishment', '=', True),
        ])

        _logger.info(f'Productos que necesitan reabastecimiento: {len(products_needing)}')

        created_count = 0
        skipped_count = 0

        for product in products_needing:
            result = self_sudo._process_product_replenishment(product, activity_type)
            if result == 'created':
                created_count += 1
            elif result == 'skipped':
                skipped_count += 1

        # Limpiar reglas de productos que ya no necesitan reabastecimiento
        self_sudo._cleanup_resolved_rules(products_needing)

        _logger.info(
            f'Verificación completada. Actividades creadas: {created_count}, '
            f'omitidas (duplicados): {skipped_count}'
        )
        """Obtiene el tipo de actividad de reabastecimiento.
        FIX: Nombre de módulo corregido a 'stock_replenishment_rules'.
        """

    def _process_product_replenishment(self, product, activity_type):
        """
        Procesa un producto individual para reabastecimiento.
        Retorna 'created', 'skipped' o 'updated' según la acción tomada.
        """
        # Verificar si ya existe una actividad pendiente para este producto
        existing_activity = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'product.template'),
            ('res_id', '=', product.id),
            ('activity_type_id', '=', activity_type.id),
        ], limit=1)

        if existing_activity:
            _logger.debug(
                f'Actividad ya existe para producto "{product.name}" (ID: {product.id}). '
                f'Omitiendo creación duplicada.'
            )
            return 'skipped'

        # Determinar responsable del almacén
        #responsible = self._get_warehouse_responsible()

        # Crear o actualizar la regla de reabastecimiento
        rule = self.search([('product_id', '=', product.id)], limit=1)
        responsible = rule.warehouse_responsible_id
        if not rule:
            rule = self.create({'product_id': product.id})

        # Generar la actividad
        shortage = max(0.0, product.target_stock - product.qty_available)
        priority_label = dict(
            product._fields['replenishment_priority'].selection
        ).get(product.replenishment_priority, 'Sin prioridad')

        note = _(
            '<p>El producto <strong>%(product)s</strong> requiere reabastecimiento urgente.</p>'
            '<ul>'
            '<li>Prioridad: <strong>%(priority)s</strong></li>'
            '<li>Stock disponible: <strong>%(available).2f %(uom)s</strong></li>'
            '<li>Stock objetivo: <strong>%(target).2f %(uom)s</strong></li>'
            '<li>Déficit: <strong>%(shortage).2f %(uom)s</strong></li>'
            '</ul>'
        ) % {
            'product': product.name,
            'priority': priority_label,
            'available': product.qty_available,
            'target': product.target_stock,
            'shortage': shortage,
            'uom': product.uom_id.name if product.uom_id else '',
        }

        activity_vals = {
            'activity_type_id': activity_type.id,
            'res_model_id': self.env['ir.model']._get_id('product.template'),
            'res_id': product.id,
            'user_id': responsible.id,
            'note': note,
            'summary': _(
                '[%(priority)s] Reabastecimiento requerido: %(product)s (déficit: %(shortage).1f)'
            ) % {
                'priority': priority_label.upper(),
                'product': product.name,
                'shortage': shortage,
            },
        }

        new_activity = self.env['mail.activity'].sudo().create(activity_vals)
        rule.write({
            'activity_id': new_activity.id,
            'state': 'pending',
            'warehouse_responsible_id': responsible.id,
        })

        _logger.info(
            f'Actividad creada para producto "{product.name}" '
            f'(prioridad: {priority_label}, déficit: {shortage:.2f})'
        )
        return 'created'

    def _get_replenishment_activity_type(self):
        return self.env.ref(
            f'{_MODULE_NAME}.mail_activity_type_replenishment',
            raise_if_not_found=False,
        )

    def _get_warehouse_responsible(self):
        """
        Obtiene el usuario responsable del almacén.
        Fallback al usuario administrador si no hay responsable configurado.
        """
        warehouse = self.env['stock.warehouse'].sudo().search([], limit=1)
        if warehouse and warehouse.lot_stock_id and warehouse.lot_stock_id.company_id:
            company = warehouse.lot_stock_id.company_id
            if company.user_id:
                return company.user_id

        # Fallback: buscar usuario con grupo de gestor de inventario
        stock_manager_group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
        if stock_manager_group and stock_manager_group.users:
            return stock_manager_group.users[0]

        return self.env.ref('base.user_admin')

    def _cleanup_resolved_rules(self, products_needing_replenishment):
        """
        Limpia reglas de productos que ya no necesitan reabastecimiento.
        Marca las reglas como completadas cuando el stock se normaliza.
        """
        resolved_rules = self.search([
            ('product_id', 'not in', products_needing_replenishment.ids),
            ('state', 'in', ['pending', 'in_progress']),
        ])
        if resolved_rules:
            resolved_rules.write({'state': 'done'})
            _logger.info(f'Reglas resueltas (stock normalizado): {len(resolved_rules)}')

    def action_mark_in_progress(self):
        """Marca la regla como en proceso."""
        self.write({'state': 'in_progress'})

    def action_mark_done(self):
        """Marca la regla como completada y cierra la actividad asociada."""
        for rule in self:
            if rule.activity_id:
                rule.activity_id.action_feedback(
                    feedback=_('Reabastecimiento completado para %s.') % rule.product_id.name
                )
            rule.write({'state': 'done', 'activity_id': False})

    def action_view_product(self):
        """Abre la ficha del producto."""
        self.ensure_one()
        return {
            'name': _('Producto'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.product_id.id,
            'view_mode': 'form',
        }
