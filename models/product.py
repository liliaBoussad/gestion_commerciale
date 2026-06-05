# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_gica_product = fields.Boolean(
        string='Produit GICA',
        default=False,
        help='Cocher pour identifier ce produit comme produit GICA.',
    )

    type_ciment = fields.Selection([
        ('cem_i_425_crs', 'CEM I 42.5 N-LH/SR5 (GICA MOUDHAD CRS)'),
        ('cem_i_525',     'CEM I 52.5 N-SR5 (GICA MOUDHAD)'),
        ('cem_ii_325',    'CEM II/A-L 32.5 N (GICA BÉTON)'),
        ('cem_ii_425_n',  'CEM II/A-L 42.5 N (GICA BÉTON)'),
        ('cem_ii_425_r',  'CEM II/A-L 42.5 R (GICA BÉTON)'),
        ('well_cement_g', 'Well Cement Class G HSR (GICA PÉTROLE)'),
        ('clinker',       'Clinker'),
    ], string='Famille ciment', tracking=True)


class PricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    a_la_charge_de = fields.Selection([
        ('client', 'A la charge du client'),
        ('scaek',  'A la charge de SCAEK'),
    ], string='A la charge de')