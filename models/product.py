# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    """
    Héritage de product.template pour ajouter les champs GICA.
    On filtre les produits GICA avec is_gica_product = True.
    """
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


class ProductProduct(models.Model):
    """
    Héritage de product.product (variantes) pour ajouter
    le type de conditionnement GICA.
    """
    _inherit = 'product.product'

    conditionnement_gica = fields.Selection([
        ('sac_25kg',           'Sac 25 kg'),
        ('sac_50kg',           'Sac 50 kg'),
        ('sac_25kg_fardelise', 'Sac 25 kg Fardelisé'),
        ('sac_50kg_fardelise', 'Sac 50 kg Fardelisé'),
        ('vrac',               'Vrac'),
        ('big_bag_client',     'Big-Bag (charge client)'),
        ('big_bag_scaek',      'Big-Bag (charge SCAEK)'),
    ], string='Conditionnement GICA')