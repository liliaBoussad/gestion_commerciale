# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ── Quantité en tonnes ────────────────────────────────────────────────
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
            # On considère product_uom_qty comme étant en tonnes
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
                    qty_bcg = bcg_line[0].quantity_tonne
                    autres_bc = bcg.bon_commande_ids.filtered(
                        lambda bc: bc.id != rec.order_id.id
                        and bc.state != 'cancel'
                    )
                    qty_prise = sum(
                        l.product_uom_qty
                        for bc in autres_bc
                        for l in bc.order_line
                        if l.product_id == rec.product_id
                    )
                    disponible = qty_bcg - qty_prise
            rec.quantity_disponible = disponible

    @api.constrains('product_id', 'order_id')
    def _check_produit_dans_bcg(self):
        for rec in self:
            bcg = rec.order_id.commande_globale_id
            if not bcg:
                continue
            bcg_line = bcg.line_ids.filtered(
                lambda l: l.product_id == rec.product_id
            )
            if not bcg_line:
                raise ValidationError(
                    f'❌ Le produit "{rec.product_id.display_name}" '
                    f'n\'existe pas dans la commande globale {bcg.name}.\n\n'
                    f'Veuillez choisir uniquement les produits du contrat.'
                )

    @api.constrains('product_uom_qty', 'product_id', 'order_id')
    def _check_quantite_disponible(self):
        for rec in self:
            if rec.product_uom_qty <= 0:
                raise ValidationError('❌ La quantité doit être supérieure à 0.')
            bcg = rec.order_id.commande_globale_id
            if not bcg or not rec.product_id:
                continue
            bcg_line = bcg.line_ids.filtered(
                lambda l: l.product_id == rec.product_id
            )
            if not bcg_line:
                continue

            qty_bcg = bcg_line[0].quantity_tonne
            autres_bc = bcg.bon_commande_ids.filtered(
                lambda bc: bc.id != rec.order_id.id and bc.state != 'cancel'
            )
            qty_prise = sum(
                l.product_uom_qty
                for bc in autres_bc
                for l in bc.order_line
                if l.product_id == rec.product_id
            )
            qty_totale = qty_prise + rec.product_uom_qty

            if qty_totale > qty_bcg:
                raise ValidationError(
                    f'❌ Quantité dépassée pour {rec.product_id.display_name} :\n\n'
                    f'  📦 Quantité BCG totale  : {qty_bcg:.2f} T\n'
                    f'  ✅ Déjà commandé        : {qty_prise:.2f} T\n'
                    f'  🛒 Ce bon de commande   : {rec.product_uom_qty:.2f} T\n'
                    f'  ⚠️  Total               : {qty_totale:.2f} T\n\n'
                    f'  👉 Quantité disponible  : {qty_bcg - qty_prise:.2f} T'
                )


class GicaSaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Lien vers BCG ─────────────────────────────────────────────────────
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale (BCG)',
        ondelete='restrict',
        tracking=True,
        domain="[('state', 'in', ['nouveau', 'en_cours'])]",
    )

    # ── Client GICA ───────────────────────────────────────────────────────
    gica_client_id = fields.Many2one(
        'gica.client',
        string='Client GICA',
        related='commande_globale_id.client_id',
        store=True,
        readonly=True,
    )

    # ── Contrat GICA ──────────────────────────────────────────────────────
    gica_contrat_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat GICA',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
    )

    # ── Dates enlèvement ──────────────────────────────────────────────────
    date_prevue_enlevement = fields.Date(
        string="Date prévue d'enlèvement",
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

    # ── Lien Bon de Circulation — activé quand le modèle sera créé ─────
    # bon_circulation_id = fields.Many2one(
    #     'gica.bon.circulation',
    #     string='Bon de Circulation',
    #     readonly=True,
    # )

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

    @api.constrains('commande_globale_id')
    def _check_commande_globale_active(self):
        for rec in self:
            if rec.commande_globale_id and rec.commande_globale_id.state not in ('nouveau', 'en_cours'):
                raise ValidationError(
                    '❌ Impossible de créer un BC sur une commande globale clôturée ou annulée.'
                )

    @api.constrains('date_prevue_enlevement')
    def _check_date_enlevement(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_prevue_enlevement and rec.date_prevue_enlevement < today:
                raise ValidationError(
                    f'❌ La date d\'enlèvement ({rec.date_prevue_enlevement}) '
                    f'ne peut pas être dans le passé.\n\n'
                    f'👉 Choisir une date à partir du {today}.'
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