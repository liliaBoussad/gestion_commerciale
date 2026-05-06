# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class GicaPlanificationUsine(models.Model):
    _name = 'gica.planification.usine'
    _description = 'Planification Usine GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    date_debut = fields.Date(
        string='Date début',
        required=True,
        tracking=True,
    )

    date_fin = fields.Date(
        string='Date fin',
        compute='_compute_date_fin',
        store=True,
        readonly=True,
        tracking=True,
    )

    state = fields.Selection([
        ('brouillon',  'Brouillon'),
        ('en_cours',   'En cours'),
        ('confirmee',  'Confirmée'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    planification_ids = fields.One2many(
        'gica.planification.client',
        'planification_usine_id',
        string='Planifications Clients',
    )

    planification_count = fields.Integer(
        compute='_compute_counts',
        string='Total Planifications',
    )
    planification_validee_count = fields.Integer(
        compute='_compute_counts',
        string='Validées',
    )
    planification_refusee_count = fields.Integer(
        compute='_compute_counts',
        string='Refusées',
    )
    planification_en_attente_count = fields.Integer(
        compute='_compute_counts',
        string='En attente',
    )

    observations = fields.Text(string='Observations')

    @api.depends('date_debut')
    def _compute_date_fin(self):
        for rec in self:
            if rec.date_debut:
                rec.date_fin = rec.date_debut + timedelta(days=14)
            else:
                rec.date_fin = False

    @api.depends('planification_ids', 'planification_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.planification_count = len(rec.planification_ids)
            rec.planification_validee_count = len(
                rec.planification_ids.filtered(lambda p: p.state == 'validee')
            )
            rec.planification_refusee_count = len(
                rec.planification_ids.filtered(lambda p: p.state == 'refusee')
            )
            rec.planification_en_attente_count = len(
                rec.planification_ids.filtered(lambda p: p.state == 'soumise')
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.planification.usine'
                ) or 'Nouveau'
        return super().create(vals_list)

    @api.constrains('date_debut')
    def _check_date_debut(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_debut and rec.date_debut < today:
                raise ValidationError(
                    '❌ La date de début ne peut pas être dans le passé.'
                )

    @api.constrains('date_debut')
    def _check_no_overlap(self):
        """Vérifie qu'il n'y a pas de chevauchement avec une période confirmée"""
        for rec in self:
            if not rec.date_debut:
                continue
            date_fin = rec.date_debut + timedelta(days=14)
            overlap = self.search([
                ('state', '=', 'confirmee'),
                ('id', '!=', rec.id),
                ('date_debut', '<=', date_fin),
                ('date_fin', '>=', rec.date_debut),
            ])
            if overlap:
                raise ValidationError(
                    f'❌ Cette période chevauche une période déjà confirmée : '
                    f'{overlap[0].name} ({overlap[0].date_debut} → {overlap[0].date_fin})'
                )

    def action_recuperer_planifications(self):
        """Récupère toutes les planifications clients soumises pour cette période"""
        self.ensure_one()
        if not self.date_debut or not self.date_fin:
            raise ValidationError('❌ Veuillez définir une date de début.')

        planifications = self.env['gica.planification.client'].search([
            ('state', '=', 'soumise'),
            ('date_enlevement', '>=', self.date_debut),
            ('date_enlevement', '<=', self.date_fin),
            ('planification_usine_id', '=', False),
        ])

        if not planifications:
            raise ValidationError(
                f'⚠️ Aucune planification cliente soumise pour la période '
                f'{self.date_debut} → {self.date_fin}.'
            )

        planifications.write({'planification_usine_id': self.id})
        self.write({'state': 'en_cours'})
        self.message_post(
            body=f'📋 {len(planifications)} planification(s) récupérée(s) '
                 f'pour la période {self.date_debut} → {self.date_fin}.'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Planifications récupérées',
                'message': f'{len(planifications)} planification(s) récupérée(s).',
                'type': 'success',
            }
        }

    def action_confirmer(self):
        """Confirme la période — verrouille les dates sur le portail"""
        for rec in self:
            # Vérifier qu'il n'y a plus de planifications en attente
            en_attente = rec.planification_ids.filtered(
                lambda p: p.state == 'soumise'
            )
            if en_attente:
                raise ValidationError(
                    f'❌ Il reste {len(en_attente)} planification(s) en attente de traitement.'
                )
            rec.write({'state': 'confirmee'})
            rec.message_post(
                body=f'🔒 Période confirmée et verrouillée : '
                     f'{rec.date_debut} → {rec.date_fin}'
            )

    def action_valider_planification(self, planification_id):
        """Valide une planification client spécifique"""
        self.ensure_one()
        planification = self.env['gica.planification.client'].browse(planification_id)
        if planification.planification_usine_id != self:
            raise ValidationError('❌ Cette planification n\'appartient pas à cette période.')
        planification.action_valider()

    def action_refuser_planification(self, planification_id, motif):
        """Refuse une planification client spécifique"""
        self.ensure_one()
        planification = self.env['gica.planification.client'].browse(planification_id)
        if planification.planification_usine_id != self:
            raise ValidationError('❌ Cette planification n\'appartient pas à cette période.')
        planification.action_refuser(motif)

    def action_voir_planifications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Planifications Clients',
            'res_model': 'gica.planification.client',
            'view_mode': 'list,form',
            'domain': [('planification_usine_id', '=', self.id)],
            'context': {'default_planification_usine_id': self.id},
        }
        