# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClinkerCadence(models.Model):
    _name        = 'clinker.cadence'
    _description = 'Cadence Usine Clinker'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_application desc, id desc'

    name = fields.Char(
        string='Référence',
        compute='_compute_name',
        store=True,
    )

    date_application = fields.Date(
        string="Date d'application",
        required=True,
        tracking=True,
    )

    quantite = fields.Float(
        string='Quantité (T/jour)',
        required=True,
        tracking=True,
    )

    marge_erreur = fields.Float(
        string='Marge d\'erreur (%)',
        default=0.0,
        tracking=True,
    )

    quantite_min = fields.Float(
        string='Quantité min (T)',
        compute='_compute_limites',
        store=True,
    )
    quantite_max = fields.Float(
        string='Quantité max (T)',
        compute='_compute_limites',
        store=True,
    )

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide',    'Validé'),
        ('expire',    'Expiré'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    observations = fields.Text(string='Observations')

    @api.depends('date_application', 'quantite')
    def _compute_name(self):
        for rec in self:
            if rec.date_application and rec.quantite:
                rec.name = f'Cadence des le {rec.date_application} - {rec.quantite} T/jour'
            else:
                rec.name = 'Nouvelle cadence'

    @api.depends('quantite', 'marge_erreur')
    def _compute_limites(self):
        for rec in self:
            if rec.marge_erreur > 0:
                rec.quantite_min = rec.quantite * (1 - rec.marge_erreur / 100)
                rec.quantite_max = rec.quantite * (1 + rec.marge_erreur / 100)
            else:
                rec.quantite_min = rec.quantite
                rec.quantite_max = rec.quantite

    @api.constrains('quantite')
    def _check_quantite(self):
        for rec in self:
            if rec.quantite <= 0:
                raise ValidationError('❌ La quantité doit être supérieure à 0.')

    @api.constrains('marge_erreur')
    def _check_marge(self):
        for rec in self:
            if rec.marge_erreur < 0 or rec.marge_erreur > 100:
                raise ValidationError('❌ La marge doit être entre 0 et 100%.')

    def action_valider(self):
        """
        CORRECTION : plusieurs cadences peuvent être Validé simultanément.
        On expire uniquement les cadences dont la date_application est
        antérieure à la cadence qu'on valide.
        """
        for rec in self:
            if rec.quantite <= 0:
                raise ValidationError('❌ La quantité doit être supérieure à 0.')

            # Expirer uniquement les cadences plus anciennes
            cadences_plus_anciennes = self.search([
                ('state',            '=',  'valide'),
                ('date_application', '<',  rec.date_application),
                ('id',               '!=', rec.id),
            ])
            cadences_plus_anciennes.write({'state': 'expire'})

            rec.write({'state': 'valide'})
            rec.message_post(
                body=f'✅ Cadence validée — {rec.quantite} T/jour à partir du {rec.date_application}'
            )

    def action_brouillon(self):
        for rec in self:
            rec.write({'state': 'brouillon'})
            rec.message_post(body='↩️ Remise en brouillon.')

    @api.model
    def get_cadence_active(self, date=None):
        """
        CORRECTION : retourne la cadence validée dont la date_application
        est <= date (aujourd'hui par défaut) — la plus récente.
        """
        if not date:
            date = fields.Date.today()
        cadence = self.search([
            ('state',            '=',  'valide'),
            ('date_application', '<=', date),
        ], order='date_application desc, id desc', limit=1)
        return cadence or False

    @api.model
    def verifier_quantite(self, quantite, date=None):
        cadence = self.get_cadence_active(date)
        if not cadence:
            return ('no_cadence', False)
        if quantite <= cadence.quantite_max:
            return ('ok', cadence)
        return ('depasse', cadence)