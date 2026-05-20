# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GicaPesee(models.Model):
    _name        = 'gica.pesee'
    _description = 'Historique des Pesées GICA'
    _order       = 'date_pesee desc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
    )

    bon_circulation_id = fields.Many2one(
        'gica.bon.circulation',
        string='Bon de Circulation',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        related='bon_circulation_id.sale_order_id',
        string='Commande de Vente',
        store=True,
        readonly=True,
    )

    # ── client_id pointe vers res.partner ────────────────────────────────
    client_id = fields.Many2one(
        'res.partner',
        related='bon_circulation_id.client_id',
        string='Client',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        related='bon_circulation_id.product_id',
        string='Produit',
        store=True,
        readonly=True,
    )
    conditionnement = fields.Selection(
        related='bon_circulation_id.conditionnement',
        string='Conditionnement',
        store=True,
        readonly=True,
    )
    matricule = fields.Char(
        related='bon_circulation_id.matricule',
        string='Matricule',
        store=True,
        readonly=True,
    )
    chauffeur = fields.Char(
        related='bon_circulation_id.chauffeur',
        string='Chauffeur',
        store=True,
        readonly=True,
    )

    type_pesee = fields.Selection([
        ('vide',   'Pesée à vide — P1 (Tare)'),
        ('charge', 'Pesée en charge — P2 (Brut)'),
    ], string='Type de Pesée', required=True, readonly=True)

    poids = fields.Float(string='Poids (T)', readonly=True)
    note  = fields.Char(string='Observation', readonly=True)

    date_pesee = fields.Datetime(
        string='Date de pesée',
        default=fields.Datetime.now,
        readonly=True,
    )

    agent_pesage_id = fields.Many2one(
        'res.users',
        string='Agent Pesage',
        default=lambda self: self.env.user,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.pesee'
                ) or 'Nouveau'
        return super().create(vals_list)