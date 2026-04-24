# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaClassificationConfig(models.Model):
    """
    Paramètres configurables du système de classification.
    Une seule configuration peut être active à la fois.

    X : CA mensuel en DA pour obtenir 1 point       (Score CA,       max 40 pts)
    Y : Paiement mensuel en DA pour obtenir 1 point (Score Paiement, max 30 pts)
    """
    _name = 'gica.classification.config'
    _description = 'Configuration Classification GICA'
    _rec_name = 'name'

    name = fields.Char(
        string='Libellé',
        required=True,
        default='Configuration Classification',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Une seule configuration peut être active à la fois.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ── Paramètre X — Score CA (40 pts max) ──────────────────────────────
    seuil_ca_par_point = fields.Monetary(
        string='X — CA mensuel par point (DA)',
        currency_field='currency_id',
        required=True,
        default=1_000_000,
        help='1 point de CA pour chaque X DA de CA mensuel moyen.\n'
             'Exemple : X = 1 000 000 DA → CA mensuel de 10 MDA = 10 points.',
    )

    # ── Paramètre Y — Score Paiement (30 pts max) ─────────────────────────
    seuil_paiement_par_point = fields.Monetary(
        string='Y — Paiement mensuel par point (DA)',
        currency_field='currency_id',
        required=True,
        default=1_000_000,
        help='1 point de paiement pour chaque Y DA payés à temps par mois.\n'
             'Exemple : Y = 1 000 000 DA → 15 MDA payés à temps par mois = 15 points.',
    )

    # ── Seuils de niveau ──────────────────────────────────────────────────
    seuil_platinum = fields.Float(string='Seuil PLATINUM (pts)', required=True, default=90.0)
    seuil_gold     = fields.Float(string='Seuil GOLD (pts)',     required=True, default=75.0)
    seuil_silver   = fields.Float(string='Seuil SILVER (pts)',   required=True, default=50.0)

    note = fields.Text(string='Notes')

    # ── Contraintes ────────────────────────────────────────────────────────

    @api.constrains('active')
    def _check_single_active(self):
        for rec in self:
            if rec.active:
                others = self.search([('active', '=', True), ('id', '!=', rec.id)])
                if others:
                    raise ValidationError(
                        'Une seule configuration peut être active à la fois.\n'
                        'Désactivez la configuration existante avant d\'en activer une nouvelle.'
                    )

    @api.constrains('seuil_ca_par_point', 'seuil_paiement_par_point')
    def _check_seuils_positifs(self):
        for rec in self:
            if rec.seuil_ca_par_point <= 0:
                raise ValidationError('Le seuil CA (X) doit être strictement positif.')
            if rec.seuil_paiement_par_point <= 0:
                raise ValidationError('Le seuil paiement (Y) doit être strictement positif.')

    @api.constrains('seuil_platinum', 'seuil_gold', 'seuil_silver')
    def _check_seuils_coherents(self):
        for rec in self:
            if not (rec.seuil_platinum > rec.seuil_gold > rec.seuil_silver > 0):
                raise ValidationError(
                    'Les seuils doivent respecter : PLATINUM > GOLD > SILVER > 0.'
                )

    @api.model
    def get_active_config(self):
        """Retourne la configuration active. Lève une erreur si aucune n'existe."""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise ValidationError(
                'Aucune configuration de classification active.\n'
                'Allez dans Configuration > Classification pour en créer une.'
            )
        return config