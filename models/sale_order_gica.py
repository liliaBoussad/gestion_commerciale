# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    quantity_tonne = fields.Float(
        string='Quantite (T)',
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

    @api.depends(
        'order_id.commande_globale_id',
        'order_id.commande_globale_id.line_ids',
        'product_id',
    )
    def _compute_quantity_disponible(self):
        for rec in self:
            disponible = 0.0
            bcg = rec.order_id.commande_globale_id
            if bcg and rec.product_id:
                bcg_line = bcg.line_ids.filtered(
                    lambda l: l.product_tmpl_id == rec.product_id.product_tmpl_id
                )
                if bcg_line:
                    disponible = bcg_line[0].quantity_restante
            rec.quantity_disponible = disponible


class GicaSaleOrder(models.Model):
    _inherit = 'sale.order'

    # Lien vers BCG
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale (BCG)',
        ondelete='restrict',
        tracking=True,
        readonly=True,
    )

    # Lien vers Planification Client
    planification_id = fields.Many2one(
        'gica.planification.client',
        string='Planification Client',
        ondelete='restrict',
        tracking=True,
        readonly=True,
    )

    # One2many vers N bons de circulation
    bon_circulation_ids = fields.One2many(
        'gica.bon.circulation',
        'sale_order_id',
        string='Bons de Circulation',
        readonly=True,
    )

    bon_circulation_count = fields.Integer(
        string='Nb Rotations',
        compute='_compute_rotations_stats',
    )

    rotations_terminees = fields.Integer(
        string='Rotations terminees',
        compute='_compute_rotations_stats',
    )

    toutes_rotations_terminees = fields.Boolean(
        string='Toutes rotations terminees',
        compute='_compute_rotations_stats',
    )

    @api.depends('bon_circulation_ids', 'bon_circulation_ids.state')
    def _compute_rotations_stats(self):
        for rec in self:
            bcs = rec.bon_circulation_ids.filtered(
                lambda b: b.state != 'annule'
            )
            termines = bcs.filtered(lambda b: b.state == 'termine')
            rec.bon_circulation_count      = len(bcs)
            rec.rotations_terminees        = len(termines)
            rec.toutes_rotations_terminees = (
                len(bcs) > 0 and len(bcs) == len(termines)
            )

    # Client GICA
    gica_client_id = fields.Many2one(
        'res.partner',
        string='Client GICA',
        related='commande_globale_id.client_id',
        store=True,
        readonly=True,
    )

    # Contrat GICA
    gica_contrat_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat GICA',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
    )

    # Date enlevement prevue
    date_prevue_enlevement = fields.Date(
        string="Date prevue d'enlevement",
        related='planification_id.date_enlevement',
        store=True,
        readonly=True,
        tracking=True,
    )

    # Date reelle enlevement
    date_reelle_enlevement = fields.Date(
        string="Date reelle d'enlevement",
        readonly=True,
        tracking=True,
    )

    # Source
    source = fields.Selection([
        ('portail',    'Portail Client'),
        ('commercial', 'Commercial'),
    ], string='Source', default='commercial', readonly=True)

    # Numero BC papier
    numero_bc_papier = fields.Char(
        string='Numero BC papier',
        tracking=True,
    )

    # Scan BC client
    scan_bc_client = fields.Binary(
        string='Scan BC client',
        attachment=True,
    )
    scan_bc_client_filename = fields.Char(string='Nom du fichier')

    # Quantite totale en tonnes
    quantity_total_tonne = fields.Float(
        string='Quantite totale (T)',
        compute='_compute_quantity_total_tonne',
        store=True,
    )

    # Quantite reelle livree (somme des poids nets)
    quantity_livree = fields.Float(
        string='Quantite livree (T)',
        compute='_compute_quantity_livree',
        store=True,
    )

    @api.depends('order_line.product_uom_qty')
    def _compute_quantity_total_tonne(self):
        for rec in self:
            rec.quantity_total_tonne = sum(
                rec.order_line.mapped('product_uom_qty')
            )

    @api.depends('bon_circulation_ids.poids_net', 'bon_circulation_ids.state')
    def _compute_quantity_livree(self):
        for rec in self:
            rec.quantity_livree = sum(
                b.poids_net
                for b in rec.bon_circulation_ids
                if b.state == 'termine'
            )

    def action_voir_bons_circulation(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Circulation',
            'res_model': 'gica.bon.circulation',
            'view_mode': 'list,form',
            'domain':    [('sale_order_id', '=', self.id)],
        }

    def action_creer_facture_groupee(self):
        """
        Genere une facture groupee basee sur tous les BLs
        des rotations terminees.
        Utilise le mecanisme natif Odoo.
        """
        self.ensure_one()

        if not self.toutes_rotations_terminees:
            raise ValidationError(
                f'Toutes les rotations ne sont pas encore terminees.\n'
                f'Terminees : {self.rotations_terminees}/{self.bon_circulation_count}'
            )

        # Utiliser le mecanisme natif Odoo pour creer la facture
        # depuis le bon de commande
        return self._create_invoices()