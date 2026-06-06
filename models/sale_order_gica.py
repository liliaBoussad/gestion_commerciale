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
        string='Nb BCs',
        compute='_compute_bon_circulation_count',
    )

    @api.depends('bon_circulation_ids')
    def _compute_bon_circulation_count(self):
        for rec in self:
            rec.bon_circulation_count = len(rec.bon_circulation_ids)

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

    @api.depends('order_line.product_uom_qty')
    def _compute_quantity_total_tonne(self):
        for rec in self:
            rec.quantity_total_tonne = sum(
                rec.order_line.mapped('product_uom_qty')
            )

    def action_voir_bons_circulation(self):
        """Ouvre la liste des bons de circulation lies"""
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Circulation',
            'res_model': 'gica.bon.circulation',
            'view_mode': 'list,form',
            'domain':    [('sale_order_id', '=', self.id)],
        }