from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class GicaClientAgrement(models.Model):
    _name = 'gica.client.agrement'
    _description = 'Agrément Client GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'

    # ── Identification ────────────────────────────────────────────────────────
    name = fields.Char(
        string="Numéro d'agrément",
        required=True,
        copy=False,
        tracking=True,
    )

    # ── Client ────────────────────────────────────────────────────────────────
    # Seuls les Distributeurs officiels, Conditionneurs et Revendeurs agréés
    # sont concernés par l'agrément (Article III GICA)
    client_id = fields.Many2one(
        'gica.client',
        string="Client",
        required=True,
        tracking=True,
        domain=[('client_type', 'in', ['distributeur', 'conditionneur', 'rev_agree'])],
    )
    client_type = fields.Selection(
        related='client_id.client_type',
        string="Type client",
        readonly=True,
    )

    # ── Dates (durée max 2 ans) ───────────────────────────────
    date_debut = fields.Date(
        string="Date de début",
        required=True,
        tracking=True,
    )
    date_expiration = fields.Date(
        string="Date d'expiration",
        required=True,
        tracking=True,
    )
    duree_mois = fields.Integer(
        string="Durée (mois)",
        compute='_compute_duree_mois',
        store=True,
    )

    @api.depends('date_debut', 'date_expiration')
    def _compute_duree_mois(self):
        for rec in self:
            if rec.date_debut and rec.date_expiration:
                delta = relativedelta(rec.date_expiration, rec.date_debut)
                rec.duree_mois = delta.months + delta.years * 12
            else:
                rec.duree_mois = 0

    @api.onchange('date_debut')
    def _onchange_date_debut(self):
        if self.date_debut:
            self.date_expiration = self.date_debut + relativedelta(years=2)
        else:
            self.date_expiration = False


            
    # ── Statut ────────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('actif',    'Actif'),
        ('suspendu', 'Suspendu'),
        ('expire',   'Expiré'),
        ('retire',   'Retiré'),
    ], string="Statut", default='actif',
       required=True, tracking=True)

    # Motif retrait (Section 3.02)
    motif_retrait = fields.Selection([
        ('cessation_activite',   'Changement ou cessation d\'activité'),
        ('manquement_obligations', 'Manquement aux obligations contractuelles'),
        ('autre',                'Autre'),
    ], string="Motif de retrait", tracking=True)

    motif_details = fields.Text(
        string="Détails du motif",
        tracking=True,
    )

    # ── Renouvellement ────────────────────────────────────────────────────────
    renouvele = fields.Boolean(
        string="Renouvelé",
        default=False,
        tracking=True,
    )
    agrement_precedent_id = fields.Many2one(
        'gica.client.agrement',
        string="Agrément précédent",
        tracking=True,
    )

    # ── Alerte expiration proche ──────────────────────────────────────────────
    expiration_proche = fields.Boolean(
        string="Expiration proche (≤ 30 jours)",
        compute='_compute_expiration_proche',
        store=True,
    )

    @api.depends('date_expiration', 'state')
    def _compute_expiration_proche(self):
        today = fields.Date.today()
        seuil = today + relativedelta(days=30)
        for rec in self:
            rec.expiration_proche = (
                rec.state == 'actif'
                and rec.date_expiration
                and rec.date_expiration <= seuil
            )

    # ── Contraintes ───────────────────────────────────────────────────────────
    @api.constrains('date_debut', 'date_expiration')
    def _check_dates(self):
        for rec in self:
            if rec.date_debut and rec.date_expiration:
                if rec.date_expiration <= rec.date_debut:
                    raise ValidationError(
                        "La date d'expiration doit être postérieure à la date de début."
                    )
                # Section 3.01 : durée maximale 2 ans
                delta = relativedelta(rec.date_expiration, rec.date_debut)
                duree_mois = delta.months + delta.years * 12
                if duree_mois > 24:
                    raise ValidationError(
                        "La durée de l'agrément ne peut pas dépasser 2 ans (Section 3.01 GICA)."
                    )

    # ── Actions workflow ──────────────────────────────────────────────────────
    def action_suspendre(self):
        self.write({'state': 'suspendu'})

    def action_retirer(self):
        self.write({'state': 'retire'})

    def action_renouveler(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Renouveler l'agrément",
            'res_model': 'gica.client.agrement',
            'view_mode': 'form',
            'context': {
                'default_client_id': self.client_id.id,
                'default_agrement_precedent_id': self.id,
                'default_renouvele': True,
            },
        }

    # ── Cron expiration automatique ───────────────────────────────────────────
    @api.model
    def _cron_check_expiration(self):
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'actif'),
            ('date_expiration', '<', today),
        ])
        expired.write({'state': 'expire'})