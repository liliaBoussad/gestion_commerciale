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
    conditionnement_gica = fields.Selection(
        related='product_id.conditionnement_gica',
        string='Conditionnement',
        readonly=True,
        store=True,
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
    gica_client_id = fields.Many2one(
        'gica.client',
        string='Client GICA',
        related='commande_globale_id.client_id',
        store=True,
        readonly=True,
    )
    gica_contrat_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat GICA',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
    )
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
    scan_bc_client = fields.Binary(
        string='Scan BC client',
        attachment=True,
    )
    scan_bc_client_filename = fields.Char(string='Nom du fichier')

    quantity_total_tonne = fields.Float(
        string='Quantité totale (T)',
        compute='_compute_quantity_total_tonne',
        store=True,
    )

    circulation_line_ids = fields.One2many(
        'gica.circulation.line',
        'sale_order_id',
        string='Rotations',
    )
    bon_circulation_ids = fields.One2many(
        'gica.bon.circulation',
        'sale_order_id',
        string='Bons de Circulation',
    )
    bon_circulation_count = fields.Integer(
        compute='_compute_bon_circulation_count',
        string='Bons Circulation',
    )

    @api.depends('bon_circulation_ids')
    def _compute_bon_circulation_count(self):
        for rec in self:
            rec.bon_circulation_count = len(rec.bon_circulation_ids)

    @api.depends('order_line.product_uom_qty')
    def _compute_quantity_total_tonne(self):
        for rec in self:
            rec.quantity_total_tonne = sum(
                rec.order_line.mapped('product_uom_qty')
            )

    def action_generer_bons_circulation(self):
        self.ensure_one()
        if self.circulation_line_ids:
            raise ValidationError('Les bons de circulation ont déjà été générés.')

        planif_line = self.env['gica.planification.client.line'].search([
            ('sale_order_id', '=', self.id),
        ], limit=1)

        if not planif_line:
            raise ValidationError('Aucune ligne de planification liée à ce BC.')

        qte = planif_line.quantity_tonne / planif_line.rotation if planif_line.rotation else planif_line.quantity_tonne
        paquets = planif_line.nbr_paquets // planif_line.rotation if planif_line.rotation else planif_line.nbr_paquets

        lines = [{
            'sale_order_id':         self.id,
            'planification_line_id': planif_line.id,
            'numero_rotation':       i + 1,
            'product_id':            planif_line.product_id.id,
            'quantite':              qte,
            'nbr_paquets':           paquets,
            'state':                 'planifie',
        } for i in range(planif_line.rotation)]

        self.env['gica.circulation.line'].create(lines)
        self.message_post(body=f'🚛 {planif_line.rotation} rotation(s) créée(s).')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bons de Circulation',
                'message': f'{planif_line.rotation} rotation(s) créée(s).',
                'type': 'success',
            }
        }

    def action_voir_bons_circulation(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Circulation',
            'res_model': 'gica.bon.circulation',
            'view_mode': 'list,form',
            'domain':    [('sale_order_id', '=', self.id)],
        }

    def action_marquer_enleve(self):
        for rec in self:
            rec.write({'date_reelle_enlevement': fields.Date.today()})
            if rec.commande_globale_id:
                rec.commande_globale_id._check_cloture_automatique()
            rec.message_post(body=f'📦 Marchandise enlevée le {fields.Date.today()}.')