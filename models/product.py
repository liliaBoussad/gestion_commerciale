# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaProduct(models.Model):
    """Produit principal : le type de ciment (ex: CEM I 42.5 N-LH/SR5)"""
    _name = 'gica.product'
    _description = 'Produits GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Type de ciment',
        required=True,
        tracking=True
    )

    type_ciment = fields.Selection([
        ('cem_i_425_crs', 'CEM I 42.5 N-LH/SR5'),
        ('cem_i_525',     'CEM I 52.5 N-SR5'),
        ('cem_ii_325',    'CEM II/A-L 32.5 N'),
        ('cem_ii_425_n',  'CEM II/A-L 42.5 N'),
        ('cem_ii_425_r',  'CEM II/A-L 42.5 R'),
        ('well_cement_g', 'Well Cement Class G HSR'),
    ], string='Famille', required=True, tracking=True)

    # Variantes (conditionnements) du produit
    variant_ids = fields.One2many(
        'gica.product.variant',
        'product_id',
        string='Conditionnements'
    )

    # Nombre de variantes (pour affichage dans la liste)
    variant_count = fields.Integer(
        string='Nb conditionnements',
        compute='_compute_variant_count',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id
    )

    active = fields.Boolean(default=True)

    @api.depends('variant_ids')
    def _compute_variant_count(self):
        for product in self:
            product.variant_count = len(product.variant_ids)

    _sql_constraints = [
        ('type_ciment_unique', 'unique(type_ciment)', 'Ce type de ciment existe déjà !')
    ]


class GicaProductVariant(models.Model):
    """Variante : un conditionnement avec son code, son prix et ses remises"""
    _name = 'gica.product.variant'
    _description = 'Variante produit GICA (conditionnement)'
    _order = 'product_id, packaging_type'

    product_id = fields.Many2one(
        'gica.product',
        string='Produit',
        required=True,
        ondelete='cascade'
    )

    code = fields.Char(
        string='Code',
        required=True,
        tracking=True
    )

    packaging_type = fields.Selection([
        ('sac_25kg',           'SAC 25 KG'),
        ('sac_50kg',           'SAC 50 KG'),
        ('sac_25kg_fardelise', 'SAC 25 KG FARDELISÉ'),
        ('sac_50kg_fardelise', 'SAC 50 KG FARDELISÉ'),
        ('vrac',               'VRAC'),
        ('big_bag_client',     'BIG-BAG (charge client)'),
        ('big_bag_scaek',      'BIG-BAG (charge SCAEK)'),
    ], string='Conditionnement', required=True)

    # ── Grille de prix ───────────────────────────────────────────────────────
    price_line_ids = fields.One2many(
        'gica.product.price',
        'variant_id',
        string='Grille de prix'
    )

    current_price = fields.Monetary(
        string='Prix actuel HT',
        compute='_compute_current_price',
        currency_field='currency_id',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='product_id.currency_id',
        store=True
    )

    active = fields.Boolean(default=True)

    @api.depends('price_line_ids.date_start', 'price_line_ids.date_end', 'price_line_ids.price_base')
    def _compute_current_price(self):
        today = fields.Date.today()
        for variant in self:
            active_price = self.env['gica.product.price'].search([
                ('variant_id', '=', variant.id),
                ('date_start', '<=', today),
                '|', ('date_end', '=', False), ('date_end', '>=', today),
            ], limit=1, order='date_start desc')
            variant.current_price = active_price.price_base if active_price else 0.0

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Le code produit doit être unique !')
    ]

    def name_get(self):
        return [(v.id, f"[{v.code}] {v.product_id.name} – {dict(v._fields['packaging_type'].selection).get(v.packaging_type, '')}") for v in self]


class GicaProductPrice(models.Model):
    """Grille de prix d'une variante"""
    _name = 'gica.product.price'
    _description = 'Grille de prix produit GICA'
    _order = 'date_start desc'

    variant_id = fields.Many2one(
        'gica.product.variant',
        string='Variante',
        required=True,
        ondelete='cascade'
    )

    date_start = fields.Date(
        string='Date début',
        required=True,
        default=fields.Date.today
    )

    date_end = fields.Date(string='Date fin')

    price_base = fields.Monetary(
        string='Prix unitaire HT',
        required=True,
        currency_field='currency_id'
    )

    # ── Remises ──────────────────────────────────────────────────────────────
    remise_sodismac = fields.Float(
        string='Remise SODISMAC (%)',
        default=7.0,
        digits=(5, 2)
    )

    remise_other_client = fields.Float(
        string='Remise Autre client (%)',
        default=4.0,
        digits=(5, 2)
    )

    remise_export = fields.Float(
        string='Remise Export (%)',
        default=10.0,
        digits=(5, 2)
    )

    # ── Prix nets calculés ───────────────────────────────────────────────────
    price_sodismac = fields.Monetary(
        string='Prix SODISMAC',
        compute='_compute_prices',
        store=True,
        currency_field='currency_id'
    )

    price_other_client = fields.Monetary(
        string='Prix Autre client',
        compute='_compute_prices',
        store=True,
        currency_field='currency_id'
    )

    price_export = fields.Monetary(
        string='Prix Export',
        compute='_compute_prices',
        store=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='variant_id.currency_id',
        store=True
    )

    @api.depends('price_base', 'remise_sodismac', 'remise_other_client', 'remise_export')
    def _compute_prices(self):
        for line in self:
            line.price_sodismac     = line.price_base * (1 - line.remise_sodismac     / 100)
            line.price_other_client = line.price_base * (1 - line.remise_other_client / 100)
            line.price_export       = line.price_base * (1 - line.remise_export       / 100)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for line in self:
            if line.date_end and line.date_end < line.date_start:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")