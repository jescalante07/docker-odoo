/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.discount_rules = loadedData["pos.discount.rule"] || [];
    },

    getActiveDiscountRule() {
        if (!this.discount_rules || this.discount_rules.length === 0) {
            return null;
        }
        const now = new Date();
        const floatTime = now.getHours() + now.getMinutes() / 60.0;

        return (
            this.discount_rules.find(
                (rule) => floatTime >= rule.hour_from && floatTime <= rule.hour_to
            ) || null
        );
    },
});

patch(Orderline.prototype, {
    set_quantity(quantity, keep_price) {
        super.set_quantity(...arguments);
        this._applyHappyHourDiscount();
    },

    _applyHappyHourDiscount() {
        // Necesitamos que el POS esté inicializado con reglas
        if (!this.pos || typeof this.pos.getActiveDiscountRule !== "function") {
            return;
        }

        const activeRule = this.pos.getActiveDiscountRule();
        const currentDiscount = this.get_discount(); // porcentaje actual de la línea

        if (activeRule) {
            const isRuleDiscount = this.pos.discount_rules.some((r) =>
                // Normalizar a número para evitar fallos de comparación por tipo
                parseFloat(r.discount_percentage) === parseFloat(currentDiscount)
            );

            if (currentDiscount === 0 || isRuleDiscount) {
                if (parseFloat(currentDiscount) !== parseFloat(activeRule.discount_percentage)) {
                    this.set_discount(activeRule.discount_percentage);
                    this._notifyDiscountApplied(activeRule);
                }
            }
        } else {
            if (currentDiscount !== 0) {
                const wasAutoDiscount = this.pos.discount_rules.some((r) =>
                    parseFloat(r.discount_percentage) === parseFloat(currentDiscount)
                );
                if (wasAutoDiscount) {
                    this.set_discount(0);
                }
            }
        }
    },

    _notifyDiscountApplied(rule) {
        try {
            const productName =
                (this.product && this.product.display_name) || "Producto";
            const message =
                `🎉 Happy Hour activo: "${rule.name}" — ` +
                `${rule.discount_percentage}% de descuento aplicado a ${productName}.`;

            if (this.pos.env && this.pos.env.services && this.pos.env.services.notification) {
                this.pos.env.services.notification.add(message, {
                    type: "success",
                    sticky: false,
                    title: "Descuento por Horario",
                });
            }
        } catch (_e) {
        }
    },
});
