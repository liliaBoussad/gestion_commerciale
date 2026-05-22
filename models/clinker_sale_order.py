# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ClinkerSaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Champs Clinker ────────────────────────────────────────────────────
    is_clinker = fields.Boolean(
        string='Vente Clinker',
        default=False,
        tracking=True,
    )

    bcg_clinker_id = fields.Many2one(
        'clinker.global.order',
        string='BCG Clinker',
        readonly=True,
        tracking=True,
    )

    clinker_planning_id = fields.Many2one(
        'clinker.planning',
        string='Planification Clinker',
        readonly=True,
        tracking=True,
    )

    # ── Mise à jour quantité livrée à la livraison physique ───────────────
    def action_marquer_clinker_livre(self):
        for rec in self:
            if not rec.is_clinker:
                continue
            qte_livree = sum(rec.order_line.mapped('product_uom_qty'))

            # Mise à jour planification
            if rec.clinker_planning_id:
                rec.clinker_planning_id.write({
                    'quantite_livree': rec.clinker_planning_id.quantite_livree + qte_livree
                })

            # Mise à jour BCG
            if rec.bcg_clinker_id:
                for line in rec.bcg_clinker_id.line_ids:
                    line.write({
                        'quantite_livree': line.quantite_livree + qte_livree
                    })

                # Vérifier clôture automatique BCG
                rec.bcg_clinker_id._check_cloture_automatique()

            rec.message_post(
                body=f'📦 Clinker livré — {qte_livree:.2f} T le {fields.Date.today()}'
            )