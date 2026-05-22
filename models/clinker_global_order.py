# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClinkerGlobalOrderLine(models.Model):
    _name        = 'clinker.global.order.line'
    _description = 'Ligne BCG Clinker'
    _order       = 'sequence, id'

    sequence   = fields.Integer(default=10)

    order_id = fields.Many2one(
        'clinker.global.order',
        string='BCG',
        required=True,
        ondelete='cascade',
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        domain="[('product_tmpl_id.type_ciment', '=', 'clinker')]",
    )

    quantite_autorisee = fields.Float(
        string='Quantité Autorisée (T)',
        required=True,
    )

    quantite_commandee = fields.Float(
        string='Quantité Commandée (T)',
        compute='_compute_quantites',
        store=True,
    )

    quantite_restante = fields.Float(
        string='Quantité Restante (T)',
        compute='_compute_quantites',
        store=True,
    )

    quantite_livree = fields.Float(
        string='Quantité Livrée (T)',
        default=0.0,
    )

    @api.depends('quantite_autorisee', 'quantite_livree')
    def _compute_quantites(self):
        for rec in self:
            rec.quantite_commandee = rec.quantite_autorisee
            rec.quantite_restante  = rec.quantite_autorisee - rec.quantite_livree


class ClinkerGlobalOrder(models.Model):
    _name        = 'clinker.global.order'
    _description = 'Bon de Commande Global Clinker'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_commande desc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        domain="[('is_gica_client', '=', True)]",
    )

    date_commande = fields.Date(
        string='Date de commande',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )

    date_expiration = fields.Date(
        string="Date d'expiration",
        required=True,
        tracking=True,
    )

    ref_bon_commande = fields.Char(
        string='Réf. Bon de Commande',
        tracking=True,
    )

    motif_refus = fields.Text(
        string='Motif de refus/blocage',
        tracking=True,
    )

    state = fields.Selection([
        ('brouillon',    'Brouillon'),
        ('soumis',       'Soumis à la production'),
        ('actif',        'Actif'),
        ('termine',      'Terminé'),
        ('bloque',       'Bloqué'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    line_ids = fields.One2many(
        'clinker.global.order.line',
        'order_id',
        string='Lignes produits',
    )

    # ── Totaux ────────────────────────────────────────────────────────────
    total_autorise = fields.Float(
        string='Total Autorisé (T)',
        compute='_compute_totaux',
        store=True,
    )
    total_restant = fields.Float(
        string='Total Restant (T)',
        compute='_compute_totaux',
        store=True,
    )
    total_livre = fields.Float(
        string='Total Livré (T)',
        compute='_compute_totaux',
        store=True,
    )

    # ── Planifications liées ──────────────────────────────────────────────
    planning_ids = fields.One2many(
        'clinker.planning',
        'bcg_id',
        string='Planifications',
    )
    planning_count = fields.Integer(
        compute='_compute_planning_count',
        string='Nb Planifications',
    )

    @api.depends('line_ids.quantite_autorisee', 'line_ids.quantite_restante', 'line_ids.quantite_livree')
    def _compute_totaux(self):
        for rec in self:
            rec.total_autorise = sum(rec.line_ids.mapped('quantite_autorisee'))
            rec.total_livre    = sum(rec.line_ids.mapped('quantite_livree'))
            rec.total_restant  = rec.total_autorise - rec.total_livre

    @api.depends('planning_ids')
    def _compute_planning_count(self):
        for rec in self:
            rec.planning_count = len(rec.planning_ids)

    # ── Séquence ──────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'clinker.global.order'
                ) or 'Nouveau'
        return super().create(vals_list)

    # ── Contraintes ───────────────────────────────────────────────────────
    @api.constrains('date_expiration', 'date_commande')
    def _check_dates(self):
        for rec in self:
            if rec.date_expiration and rec.date_commande:
                if rec.date_expiration <= rec.date_commande:
                    raise ValidationError(
                        '❌ La date d\'expiration doit être postérieure à la date de commande.'
                    )

    @api.constrains('client_id', 'state')
    def _check_doublon_bcg(self):
        for rec in self:
            if rec.state == 'actif':
                doublon = self.search([
                    ('client_id', '=', rec.client_id.id),
                    ('state',     '=', 'actif'),
                    ('id',        '!=', rec.id),
                ])
                if doublon:
                    raise ValidationError(
                        f'❌ Ce client a déjà un BCG Clinker actif : {doublon[0].name}.\n'
                        '👉 Terminez-le avant d\'en activer un nouveau.'
                    )

    @api.constrains('line_ids')
    def _check_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('❌ Le BCG doit contenir au moins une ligne produit.')

    # ── Actions ───────────────────────────────────────────────────────────
    def action_soumettre(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('❌ Ajoutez au moins une ligne produit.')
            if not rec.date_expiration:
                raise ValidationError('❌ La date d\'expiration est obligatoire.')
            rec.write({'state': 'soumis'})
            rec.message_post(body='📋 BCG soumis à la production pour validation.')
            # Notification au responsable production
            rec._notifier_production()

    def action_activer(self):
        """Action de la production pour valider le BCG"""
        for rec in self:
            rec.write({'state': 'actif', 'motif_refus': False})
            rec.message_post(body='✅ BCG validé par la production — statut Actif.')
            rec._notifier_commercial('actif')

    def action_bloquer(self):
        """Action de la production pour bloquer le BCG"""
        for rec in self:
            if not rec.motif_refus:
                raise ValidationError(
                    '❌ Le motif de refus/blocage est obligatoire.\n'
                    '👉 Saisissez un motif avant de bloquer.'
                )
            rec.write({'state': 'bloque'})
            rec.message_post(body=f'❌ BCG bloqué — Motif : {rec.motif_refus}')
            rec._notifier_commercial('bloque')

    def action_resoumettre(self):
        """Commercial re-soumet après modification"""
        for rec in self:
            if rec.state != 'bloque':
                raise ValidationError('❌ Seul un BCG bloqué peut être re-soumis.')
            rec.write({'state': 'soumis', 'motif_refus': False})
            rec.message_post(body='📋 BCG re-soumis à la production après modification.')
            rec._notifier_production()

    def action_terminer(self):
        for rec in self:
            rec.write({'state': 'termine'})
            rec.message_post(body='🏁 BCG Clinker terminé.')

    def action_brouillon(self):
        for rec in self:
            if rec.state not in ('bloque',):
                raise ValidationError('❌ Seul un BCG bloqué peut revenir en brouillon.')
            rec.write({'state': 'brouillon'})

    def action_voir_planifications(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Planifications Clinker',
            'res_model': 'clinker.planning',
            'view_mode': 'list,form',
            'domain':    [('bcg_id', '=', self.id)],
            'context':   {'default_bcg_id': self.id},
        }

    # ── Notifications ─────────────────────────────────────────────────────
    def _notifier_production(self):
        self.ensure_one()
        self.message_post(
            body=f'📢 BCG {self.name} soumis — en attente de validation production.',
            partner_ids=self._get_responsables_production(),
        )

    def _notifier_commercial(self, etat):
        self.ensure_one()
        msg = '✅ BCG activé' if etat == 'actif' else f'❌ BCG bloqué — {self.motif_refus}'
        self.message_post(body=msg)

    def _get_responsables_production(self):
        groupe = self.env.ref('base.group_system', raise_if_not_found=False)
        if groupe:
            return groupe.users.mapped('partner_id').ids
        return []

    # ── Cron expiration automatique ───────────────────────────────────────
    @api.model
    def _cron_check_expiration(self):
        today = fields.Date.today()
        self.search([
            ('state',           '=',  'actif'),
            ('date_expiration', '<',  today),
        ]).write({'state': 'termine'})

    def _check_cloture_automatique(self):
        for rec in self:
            if rec.state == 'actif' and rec.total_restant <= 0:
                rec.write({'state': 'termine'})
                rec.message_post(body='🏁 BCG Clinker clôturé automatiquement — toute la quantité a été livrée.')