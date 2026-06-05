# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class GicaPlanificationConsolidation(models.Model):
    _name        = 'gica.planification.consolidation'
    _description = 'Consolidation Planification Usine GICA'
    _order       = 'date_enlevement asc, product_id asc'

    planification_usine_id = fields.Many2one(
        'gica.planification.usine',
        string='Planification Usine',
        required=True,
        ondelete='cascade',
    )
    date_enlevement  = fields.Date(string='Date enlèvement', readonly=True)
    product_id       = fields.Many2one('product.product', string='Produit', readonly=True)
    conditionnement = fields.Char(
    string='Conditionnement',
    compute='_compute_conditionnement',
    store=True,
    readonly=True,
    )

    @api.depends('product_id')
    def _compute_conditionnement(self):
        for rec in self:
            if rec.product_id:
                attr_line = rec.product_id.product_template_attribute_value_ids.filtered(
                    lambda v: v.attribute_id.name == 'Conditionnement'
                )
                rec.conditionnement = attr_line[0].name if attr_line else ''
            else:
                rec.conditionnement = ''


    nb_lignes       = fields.Integer(string='Nb clients',    readonly=True)
    nb_rotations    = fields.Integer(string='Rotations',     readonly=True)
    quantity_tonne  = fields.Float(string='Qté totale (T)',  readonly=True)


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

    date_debut = fields.Date(string='Date début', required=True, tracking=True)
    date_fin   = fields.Date(
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

    # ── Lignes produits directes ──────────────────────────────────────────
    planification_line_ids = fields.One2many(
        'gica.planification.client.line',
        'planification_usine_id',
        string='Lignes produits',
    )

    # ── Consolidation ─────────────────────────────────────────────────────
    consolidation_ids = fields.One2many(
        'gica.planification.consolidation',
        'planification_usine_id',
        string='Consolidation',
        readonly=True,
    )

    observations = fields.Text(string='Observations')

    # ── Compteurs ─────────────────────────────────────────────────────────
    planification_count = fields.Integer(
        compute='_compute_counts',
        string='Total',
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

    # ── Totaux quantités ──────────────────────────────────────────────────
    quantity_total_demandee = fields.Float(
        compute='_compute_quantities',
        store=True,
        string='Qté totale demandée (T)',
    )
    quantity_total_validee = fields.Float(
        compute='_compute_quantities',
        store=True,
        string='Qté totale validée (T)',
    )

    @api.depends('date_debut')
    def _compute_date_fin(self):
        for rec in self:
            rec.date_fin = rec.date_debut + timedelta(days=14) if rec.date_debut else False

    @api.depends('planification_ids', 'planification_ids.state',
                 'planification_line_ids.state')
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
                rec.planification_line_ids.filtered(lambda l: l.state == 'en_attente')
            )

    @api.depends(
        'planification_ids.quantity_total_tonne',
        'planification_ids.state',
        'planification_line_ids.quantity_tonne',
        'planification_line_ids.state',
    )
    def _compute_quantities(self):
        for rec in self:
            rec.quantity_total_demandee = sum(
                rec.planification_line_ids.mapped('quantity_tonne')
            )
            rec.quantity_total_validee = sum(
                l.quantity_tonne
                for l in rec.planification_line_ids
                if l.state == 'validee'
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
        self.ensure_one()
        if not self.date_debut or not self.date_fin:
            raise ValidationError('❌ Veuillez définir une date de début.')

        # Chercher uniquement les lignes dont la date est dans cette période
        lignes = self.env['gica.planification.client.line'].search([
            ('date_enlevement', '>=', self.date_debut),
            ('date_enlevement', '<=', self.date_fin),
            ('planification_id.state', '=', 'soumise'),
            ('planification_id.planification_usine_id', '=', False),
            ('state', '=', 'en_attente'),
        ])

        if not lignes:
            raise ValidationError(
                f'⚠️ Aucune ligne soumise pour la période '
                f'{self.date_debut} → {self.date_fin}.'
            )

        # Rattacher uniquement les lignes (pas forcément toute la planification)
        planifications_concernees = lignes.mapped('planification_id')

        # Pour chaque planification, vérifier si TOUTES ses lignes sont dans cette période
        planifications_completes = self.env['gica.planification.client']
        planifications_partielles = self.env['gica.planification.client']

        for planif in planifications_concernees:
            lignes_planif = planif.line_ids
            lignes_dans_periode = lignes_planif.filtered(
                lambda l: l.date_enlevement
                and self.date_debut <= l.date_enlevement <= self.date_fin
            )
            if len(lignes_dans_periode) == len(lignes_planif):
                # Toutes les lignes sont dans cette période → rattacher la planification
                planifications_completes |= planif
            else:
                # Certaines lignes seulement → rattacher uniquement ces lignes
                planifications_partielles |= planif

        # Rattacher les planifications complètes
        if planifications_completes:
            planifications_completes.write({'planification_usine_id': self.id})

        # Pour les planifications partielles, rattacher uniquement les lignes concernées
        if planifications_partielles:
            lignes_partielles = lignes.filtered(
                lambda l: l.planification_id in planifications_partielles
            )
            lignes_partielles.write({'planification_usine_id': self.id})

        total_planifs = len(planifications_completes) + len(planifications_partielles)
        self.write({'state': 'en_cours'})
        self.message_post(
            body=f'📋 {total_planifs} planification(s) récupérée(s) '
                 f'({len(lignes)} ligne(s)) pour la période '
                 f'{self.date_debut} → {self.date_fin}.'
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Planifications récupérées',
                'message': f'{len(lignes)} ligne(s) récupérée(s).',
                'type': 'success',
            }
        }

    def action_confirmer(self):
        for rec in self:
            en_attente = rec.planification_line_ids.filtered(
                lambda l: l.state == 'en_attente'
            )
            if en_attente:
                raise ValidationError(
                    f'❌ Il reste {len(en_attente)} ligne(s) en attente de traitement.'
                )
            rec.write({'state': 'confirmee'})
            rec._calculer_consolidation()
            rec.message_post(
                body=f'🔒 Période confirmée et verrouillée : '
                     f'{rec.date_debut} → {rec.date_fin}'
            )

    def action_remettre_en_cours(self):
        for rec in self:
            rec.write({'state': 'en_cours'})
            rec.message_post(body='↩️ Période remise en cours.')

    def _calculer_consolidation(self):
        """Agrège les lignes validées par (date, produit, conditionnement)"""
        self.ensure_one()
        self.consolidation_ids.unlink()

        data = {}
        for line in self.planification_line_ids.filtered(lambda l: l.state == 'validee'):
            key = (line.date_enlevement, line.product_id.id, line.conditionnement)
            if key not in data:
                data[key] = {
                    'nb_lignes':      0,
                    'nb_rotations':   0,
                    'quantity_tonne': 0.0,
                }
            data[key]['nb_lignes']      += 1
            data[key]['nb_rotations']   += line.rotation
            data[key]['quantity_tonne'] += line.quantity_tonne

        for (date, product_id, conditionnement), vals in data.items():
            self.env['gica.planification.consolidation'].create({
                'planification_usine_id': self.id,
                'date_enlevement':        date,
                'product_id':             product_id,
                'conditionnement':        conditionnement,
                'nb_lignes':              vals['nb_lignes'],
                'nb_rotations':           vals['nb_rotations'],
                'quantity_tonne':         vals['quantity_tonne'],
            })

        self.message_post(
            body=f'📊 Consolidation calculée — {len(data)} ligne(s).'
        )

    def action_calculer_consolidation(self):
        self.ensure_one()
        self._calculer_consolidation()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Consolidation',
                'message': 'Consolidation recalculée avec succès.',
                'type': 'success',
            }
        }

    def action_valider_planification(self, planification_id):
        self.ensure_one()
        planification = self.env['gica.planification.client'].browse(planification_id)
        if planification.planification_usine_id != self:
            raise ValidationError('❌ Cette planification n\'appartient pas à cette période.')
        planification.action_valider()

    def action_refuser_planification(self, planification_id, motif):
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