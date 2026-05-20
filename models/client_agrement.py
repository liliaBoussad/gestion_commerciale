# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class GicaClientAgrement(models.Model):
    _name        = 'gica.client.agrement'
    _description = 'Agrément Client GICA'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_debut desc'

    name = fields.Char(
        string="Numéro d'agrément",
        readonly=True, copy=False, default='Nouveau', tracking=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        domain=[('client_type', 'in', ['distributeur', 'conditionneur', 'rev_agree'])],
    )
    client_type = fields.Selection(
        related='partner_id.client_type',
        string='Type client',
        readonly=True,
    )

    date_debut = fields.Date(
        string='Date de début', required=True, tracking=True,
    )
    date_expiration = fields.Date(
        string="Date d'expiration", required=True, tracking=True,
    )
    duree_mois = fields.Integer(
        string='Durée (mois)', compute='_compute_duree_mois', store=True,
    )

    @api.depends('date_debut', 'date_expiration')
    def _compute_duree_mois(self):
        for rec in self:
            if rec.date_debut and rec.date_expiration:
                delta = relativedelta(rec.date_expiration + relativedelta(days=1), rec.date_debut)
                rec.duree_mois = delta.months + delta.years * 12
            else:
                rec.duree_mois = 0

    @api.onchange('date_debut')
    def _onchange_date_debut(self):
        if not self.date_debut:
            self.date_expiration = False
            return
        today = fields.Date.today()
        if self.date_debut < today:
            return {
                'warning': {
                    'title': '⛔ Date invalide',
                    'message': f'La date de début ne peut pas être dans le passé.\n'
                               f'👉 Choisir une date à partir du {today}.',
                }
            }
        if not self.date_expiration:
            self.date_expiration = self.date_debut + relativedelta(years=2)

    # ── STATUTS ───────────────────────────────────────────────────────────
    state = fields.Selection([
        ('nouveau',  'Nouveau'),
        ('en_cours', 'En cours'),
        ('expire',   'Expiré'),
        ('resilie',  'Résilié'),
    ], string='Statut', default='nouveau', required=True, tracking=True)

    # ── RÉSILIATION ───────────────────────────────────────────────────────
    motif_resiliation = fields.Text(
        string='Motif de résiliation',
        tracking=True,
    )

    # ── RENOUVELLEMENT ────────────────────────────────────────────────────
    renouvele = fields.Boolean(string='Renouvelé', default=False, tracking=True)
    agrement_precedent_id = fields.Many2one(
        'gica.client.agrement', string='Agrément précédent', tracking=True,
    )

    expiration_proche = fields.Boolean(
        string='Expiration proche (≤ 30 jours)',
        compute='_compute_expiration_proche', store=True,
    )

    @api.depends('date_expiration', 'state')
    def _compute_expiration_proche(self):
        today = fields.Date.today()
        seuil = today + relativedelta(days=30)
        for rec in self:
            rec.expiration_proche = (
                rec.state == 'en_cours'
                and rec.date_expiration
                and rec.date_expiration <= seuil
            )

    # ── SÉQUENCE ──────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.client.agrement'
                ) or 'Nouveau'
        records = super().create(vals_list)
        for rec in records:
            rec.message_post(body='📋 Agrément Client créé.')
            # Expirer l'ancien agrément si renouvellement
            if rec.renouvele and rec.agrement_precedent_id:
                ancien = rec.agrement_precedent_id
                if ancien.state == 'en_cours':
                    ancien.write({'state': 'expire'})
                    ancien.message_post(
                        body=f'🔄 Agrément renouvelé — Remplacé par {rec.name}.'
                    )
                rec.message_post(
                    body=f'✅ Renouvellement de {ancien.name}.'
                )
        return records

    # ── CHAMP INTERMÉDIAIRE RÉSILIATION ──────────────────────────────────
    en_cours_resiliation = fields.Boolean(
        string='En cours de résiliation',
        default=False,
    )

    # ── CONTRAINTE : un seul agrément actif par client ────────────────────
    @api.constrains('partner_id', 'state')
    def _check_unique_agrement_actif(self):
        for rec in self:
            if rec.state in ('nouveau', 'en_cours'):
                doublon = self.search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('state',      '=', 'en_cours'),
                    ('id',         '!=', rec.id),
                ])
                if doublon:
                    raise ValidationError(
                        f'❌ Le client "{rec.partner_id.name}" possède déjà '
                        f'un agrément en cours : {doublon[0].name}.\n'
                        f'👉 Veuillez d\'abord résilier l\'agrément existant.'
                    )

    # ── CONTRAINTE : dates cohérentes ─────────────────────────────────────
    @api.constrains('date_debut', 'date_expiration')
    def _check_dates(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_debut and rec.date_debut < today and not rec._origin.id:
                raise ValidationError(
                    f'❌ La date de début ne peut pas être dans le passé.\n'
                    f'👉 Choisir une date à partir du {today}.'
                )
            if rec.date_debut and rec.date_expiration:
                if rec.date_expiration <= rec.date_debut:
                    raise ValidationError(
                        "❌ La date d'expiration doit être postérieure à la date de début."
                    )
                delta = relativedelta(rec.date_expiration, rec.date_debut)
                duree_mois = delta.months + delta.years * 12
                if duree_mois > 24:
                    raise ValidationError(
                        "❌ La durée de l'agrément ne peut pas dépasser 2 ans."
                    )

    # ── ACTIONS WORKFLOW ──────────────────────────────────────────────────
    def action_confirmer(self):
        """Nouveau → En cours"""
        for rec in self:
            rec.write({'state': 'en_cours'})
            rec.message_post(body='✅ Agrément confirmé — En cours.')

    def action_resilier(self):
        """Afficher le bloc motif sans changer le state"""
        for rec in self:
            rec.write({'en_cours_resiliation': True})

    def action_confirmer_resiliation(self):
        """Confirmer la résiliation après saisie du motif"""
        for rec in self:
            if not rec.motif_resiliation:
                raise ValidationError(
                    '❌ Veuillez saisir le motif de résiliation avant de confirmer.'
                )
            rec.write({
                'state':               'resilie',
                'en_cours_resiliation': False,
            })
            rec.message_post(
                body=f'❌ Agrément résilié — Motif : {rec.motif_resiliation}'
            )

    def action_annuler_resiliation(self):
        """Annuler — bloc motif disparaît, state reste en_cours"""
        for rec in self:
            rec.write({
                'en_cours_resiliation': False,
                'motif_resiliation':    False,
            })
            rec.message_post(body='↩️ Résiliation annulée.')

    def action_renouveler(self):
        """Ouvrir formulaire de renouvellement pré-rempli"""
        self.ensure_one()
        nouvelle_date_debut     = self.date_expiration + relativedelta(days=1) \
            if self.date_expiration else fields.Date.today()
        nouvelle_date_expiration = nouvelle_date_debut + relativedelta(years=2)
        return {
            'type':      'ir.actions.act_window',
            'name':      "Renouveler l'agrément",
            'res_model': 'gica.client.agrement',
            'view_mode': 'form',
            'target':    'new',
            'context': {
                'default_partner_id':            self.partner_id.id,
                'default_agrement_precedent_id': self.id,
                'default_renouvele':             True,
                'default_date_debut':            nouvelle_date_debut,
                'default_date_expiration':       nouvelle_date_expiration,
            },
        }

    # ── CRON : expirer automatiquement ────────────────────────────────────
    @api.model
    def _cron_check_expiration(self):
        today   = fields.Date.today()
        expired = self.search([
            ('state',           '=', 'en_cours'),
            ('date_expiration', '<', today),
        ])
        for rec in expired:
            rec.write({'state': 'expire'})
            rec.message_post(
                body=f'⏰ Agrément expiré automatiquement le {today}.'
            )