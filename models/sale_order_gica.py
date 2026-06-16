# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    quantity_tonne = fields.Float(
        string='Quantité (T)',
        compute='_compute_quantity_tonne',
        store=True,
    )

    quantity_disponible = fields.Float(
        string='Disponible BCG (T)',
        compute='_compute_quantity_disponible',
    )

    @api.depends('product_uom_qty')
    def _compute_quantity_tonne(self):
        for rec in self:
            rec.quantity_tonne = rec.product_uom_qty

    @api.depends('order_id.commande_globale_id',
                 'order_id.commande_globale_id.bon_commande_ids',
                 'product_id')
    def _compute_quantity_disponible(self):
        for rec in self:
            disponible = 0.0
            bcg = rec.order_id.commande_globale_id
            if bcg and rec.product_id:
                bcg_line = bcg.line_ids.filtered(
                    lambda l: l.product_id == rec.product_id
                )
                if bcg_line:
                    disponible = bcg_line[0].quantity_restante
            rec.quantity_disponible = disponible


class GicaSaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Lien vers BCG ─────────────────────────────────────────────────────
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale (BCG)',
        ondelete='restrict',
        tracking=True,
        readonly=True,
    )

    # ── Lien vers Planification Client ────────────────────────────────────
    planification_id = fields.Many2one(
        'gica.planification.client',
        string='Planification Client',
        ondelete='restrict',
        tracking=True,
        readonly=True,
    )

    # ── Client GICA ───────────────────────────────────────────────────────
    gica_client_id = fields.Many2one(
    'gica.client',
    string='Client GICA',
    store=True,
    tracking=True,
    )
    
    @api.onchange('partner_id')
    def _onchange_partner_gica(self):
        if self.partner_id:
            client = self.env['gica.client'].search(
                [('partner_id', '=', self.partner_id.id)], limit=1
            )
            self.gica_client_id = client or False

    @api.onchange('partner_id')
    def _onchange_partner_gica(self):
        if self.partner_id:
            client = self.env['gica.client'].search(
                [('partner_id', '=', self.partner_id.id)], limit=1
            )
            self.gica_client_id = client or False

    # ── Contrat GICA ──────────────────────────────────────────────────────
    gica_contrat_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat GICA',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
    )

    # ── Date enlèvement (depuis planification) ────────────────────────────
    date_prevue_enlevement = fields.Date(
        string="Date prévue d'enlèvement",
        related='planification_id.date_enlevement',
        store=True,
        readonly=True,
        tracking=True,
    )

    date_reelle_enlevement = fields.Date(
        string="Date réelle d'enlèvement",
        readonly=True,
        tracking=True,
    )

    # ── Scan BC papier (traçabilité) ──────────────────────────────────────
    scan_bc_client = fields.Binary(
        string='Scan BC client',
        attachment=True,
    )
    scan_bc_client_filename = fields.Char(string='Nom du fichier')

    # ── Quantité totale en tonnes ─────────────────────────────────────────
    quantity_total_tonne = fields.Float(
        string='Quantité totale (T)',
        compute='_compute_quantity_total_tonne',
        store=True,
    )

    @api.depends('order_line.product_uom_qty')
    def _compute_quantity_total_tonne(self):
        for rec in self:
            rec.quantity_total_tonne = sum(
                rec.order_line.mapped('product_uom_qty')
            )

    def action_marquer_enleve(self):
        for rec in self:
            rec.write({
                'date_reelle_enlevement': fields.Date.today(),
            })
            if rec.commande_globale_id:
                rec.commande_globale_id._check_cloture_automatique()
            rec.message_post(
                body=f'📦 Marchandise enlevée le {fields.Date.today()}.'
            )