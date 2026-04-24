# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    exclusivite_gica = fields.Boolean(
        string='Exclusivité GICA',
        default=False,
        tracking=True,
        help='Le client achète exclusivement des produits GICA (+10 pts).',
    )
    classification_actuelle = fields.Selection(
        [('platinum', 'PLATINUM'), ('gold', 'GOLD'),
         ('silver', 'SILVER'),    ('bronze', 'BRONZE')],
        string='Classification Actuelle',
        readonly=True,
        tracking=True,
    )
    score_actuel = fields.Float(
        string='Score Actuel (/100)', readonly=True, tracking=True,
    )
    date_derniere_classification = fields.Date(
        string='Dernière Classification', readonly=True,
    )
    # Historique via partner_id (related dans gica.client.classification)
    classification_ids = fields.One2many(
        'gica.client.classification',
        'partner_id',
        string='Historique Classifications',
    )
    delai_paiement = fields.Integer(
        string='Délai de paiement (jours)',
        compute='_compute_delai_paiement',
        store=True,
        help='PLATINUM=30j | GOLD=15j | SILVER/BRONZE=0j',
    )

    @api.depends('classification_actuelle')
    def _compute_delai_paiement(self):
        DELAIS = {'platinum': 30, 'gold': 15, 'silver': 0, 'bronze': 0}
        for partner in self:
            partner.delai_paiement = DELAIS.get(
                partner.classification_actuelle or '', 0
            )