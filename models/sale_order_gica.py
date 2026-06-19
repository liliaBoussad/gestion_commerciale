# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GicaSaleOrder(models.Model):
    _inherit = 'sale.order'

    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale (BCG)',
        ondelete='restrict',
        tracking=True,
        readonly=True,
    )

    planification_id = fields.Many2one(
        'gica.planification.client',
        string='Planification Client',
        ondelete='restrict',
        tracking=True,
        readonly=True,
    )

    bon_circulation_ids = fields.One2many(
        'gica.bon.circulation',
        'sale_order_id',
        string='Bons de Circulation',
    )

    bon_circulation_count = fields.Integer(
        compute='_compute_rotations_stats',
        string='Total rotations',
    )
    rotations_terminees = fields.Integer(
        compute='_compute_rotations_stats',
        string='Rotations terminees',
    )
    toutes_rotations_terminees = fields.Boolean(
        compute='_compute_rotations_stats',
    )

    @api.depends('bon_circulation_ids.state')
    def _compute_rotations_stats(self):
        for rec in self:
            bcs      = rec.bon_circulation_ids.filtered(lambda b: b.state != 'annule')
            termines = bcs.filtered(lambda b: b.state == 'termine')
            rec.bon_circulation_count      = len(bcs)
            rec.rotations_terminees        = len(termines)
            rec.toutes_rotations_terminees = len(bcs) > 0 and len(bcs) == len(termines)

    gica_client_id = fields.Many2one(
        'res.partner',
        related='commande_globale_id.client_id',
        store=True,
        readonly=True,
        string='Client GICA',
    )
    gica_contrat_id = fields.Many2one(
        'gica.client.contract',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
        string='Contrat GICA',
    )
    date_prevue_enlevement = fields.Date(
        related='planification_id.date_enlevement',
        store=True,
        readonly=True,
        tracking=True,
        string="Date prevue d'enlevement",
    )
    date_reelle_enlevement = fields.Date(
        string="Date reelle d'enlevement",
        readonly=True,
        tracking=True,
    )
    quantity_livree = fields.Float(
        string='Quantite livree (T)',
        compute='_compute_quantity_livree',
        store=True,
    )

    @api.depends('bon_circulation_ids.poids_net', 'bon_circulation_ids.state')
    def _compute_quantity_livree(self):
        for rec in self:
            rec.quantity_livree = sum(
                b.poids_net for b in rec.bon_circulation_ids
                if b.state == 'termine'
            )