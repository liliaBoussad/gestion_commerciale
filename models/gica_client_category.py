# -*- coding: utf-8 -*-
from odoo import models, fields


class GicaClientCategory(models.Model):
    _name        = 'gica.client.category'
    _description = 'Catégorie des clients GICA'
    _order       = 'marche, sequence, name'

    name = fields.Char(string='Nom du catégorie', required=True)

    sequence = fields.Integer(default=10)

    marche = fields.Selection([
        ('local',       'Local'),
        ('international', 'International'),
    ], string='Type de marché', required=True, default='local')

    need_agrement = fields.Boolean(string='Agrément ?', default=False)

    # Documents à fournir (Many2many vers gica.document.type)
    document_ids = fields.Many2many(
        'gica.document.type',
        'gica_client_category_document_rel',
        'category_id',
        'document_id',
        string='Documents à fournir',
    )

    # Lien avec le champ client_type de res.partner
    client_type = fields.Selection([
        ('realisation',    'Entreprise de réalisation'),
        ('investisseur',   'Investisseur'),
        ('promoteur',      'Promoteur immobilier'),
        ('transformateur', 'Transformateur'),
        ('broyage',        'Centre de broyage'),
        ('revendeur',      'Revendeur'),
        ('rev_agree',      'Revendeur agréé'),
        ('distributeur',   'Distributeur officiel'),
        ('conditionneur',  'Conditionneur'),
        ('exportateur',    'Exportateur'),
        ('auto_const',     'Auto-constructeur'),
        ('autres',         'Autres'),
        ('fab_etr',        'Fabricants de ciment étrangers'),
        ('trader',         'Traders internationaux'),
        ('ent_etr',        'Entreprise étrangère'),
    ], string='Type client lié')

    active = fields.Boolean(default=True)