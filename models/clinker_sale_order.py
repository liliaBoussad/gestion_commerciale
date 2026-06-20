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

    # ── Stats bons de circulation (identique ciment) ──────────────────────

    @api.depends('bon_circulation_ids.state')
    def _compute_rotations_stats(self):
        for rec in self:
            bcs      = rec.bon_circulation_ids.filtered(lambda b: b.state != 'annule')
            termines = bcs.filtered(lambda b: b.state == 'termine')
            rec.bon_circulation_count      = len(bcs)
            rec.rotations_terminees        = len(termines)
            rec.toutes_rotations_terminees = len(bcs) > 0 and len(bcs) == len(termines)

    # bon_circulation_count, rotations_terminees, toutes_rotations_terminees
    # et quantity_livree sont deja definis dans sale_order_gica.py (GicaSaleOrder)
    # Pas besoin de les redefinir ici.

    # ── La mise a jour quantite_livree clinker et la cloture BCG Clinker ──
    # sont gerees dans gica_bon_circulation._finaliser_terminer()
    # apres chaque pesee terminee a la bascule.
    # action_marquer_clinker_livre supprime — devenu inutile.