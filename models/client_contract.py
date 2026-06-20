# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaClientContractLine(models.Model):
    _name = 'gica.client.contract.line'
    _description = 'Ligne de contrat GICA'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    contract_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat',
        required=True,
        ondelete='cascade',
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit',
        required=True,
        domain="[('is_gica_product', '=', True)]",
    )

    type_ciment = fields.Selection(
        related='product_tmpl_id.type_ciment',
        string='Famille ciment',
        store=True,
        readonly=True,
    )

    quantity = fields.Float(string='Quantite', required=True)

    quantity_tonne = fields.Float(
        string='Quantite (tonnes)',
        compute='_compute_quantity_tonne',
        store=True,
    )

    uom = fields.Selection([
        ('tonne', 'Tonne'),
        ('sac',   'Sac'),
    ], string='Unite de mesure', required=True, default='tonne')

    quantity_livree   = fields.Float(string='Qte livree',   compute='_compute_quantity_livree', store=True)
    quantity_restante = fields.Float(string='Qte restante', compute='_compute_quantity_livree', store=True)

    @api.depends('quantity', 'uom')
    def _compute_quantity_tonne(self):
        for rec in self:
            rec.quantity_tonne = rec.quantity

    @api.depends('quantity')
    def _compute_quantity_livree(self):
        for rec in self:
            rec.quantity_livree   = 0.0
            rec.quantity_restante = rec.quantity


class GicaClientContract(models.Model):
    _name        = 'gica.client.contract'
    _description = 'Contrat Client GICA'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_start desc'

    name = fields.Char(
        string='Numero du contrat',
        readonly=True, copy=False,
        default='Nouveau', tracking=True,
    )

    client_id = fields.Many2one(
        'res.partner', string='Client',
        required=True, tracking=True,
    )

    client_type = fields.Selection(
        related='client_id.client_type',
        string='Type client', store=True, readonly=True,
    )

    project_id = fields.Many2one(
        'gica.project', string='Projet',
        tracking=True,
        domain="[('client_id', '=', client_id)]",
    )

    line_ids = fields.One2many(
        'gica.client.contract.line', 'contract_id',
        string='Lignes produits', copy=True,
    )

    quantity_total_tonne = fields.Float(
        string='Quantite totale (tonnes)',
        compute='_compute_totaux', store=True,
    )

    @api.depends('line_ids.quantity_tonne')
    def _compute_totaux(self):
        for rec in self:
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))

    # Paiement
    mode_paiement = fields.Selection([
        ('comptant', 'Paiement au comptant'),
        ('terme',    'Paiement a terme'),
    ], string='Mode de paiement', required=True, default='comptant', tracking=True)

    modalite_paiement = fields.Selection([
        ('cheque_certifie',  'Cheque de banque certifie'),
        ('cheque_ordinaire', 'Cheque ordinaire'),
        ('virement',         'Virement bancaire'),
        ('lettre_change',    'Lettre de change'),
        ('versement',        'Versement bancaire'),
        ('cib',              'Paiement electronique CIB'),
        ('especes',          'Especes (max 200 000 DA)'),
    ], string='Modalite de paiement', tracking=True)

    delai_paiement  = fields.Integer(string='Delai de paiement (jours)', default=0, tracking=True)
    delai_livraison = fields.Integer(string='Delai de livraison (jours)', tracking=True)

    # Livraison
    lieu_livraison = fields.Selection([
        ('depart_usine',   'Depart usine'),
        ('livraison_site', 'Livraison sur site client'),
    ], string='Lieu de livraison', tracking=True)
    adresse_livraison = fields.Char(string='Adresse de livraison')

    # Dates
    date_start = fields.Date(string='Date debut', required=True, tracking=True)
    date_end   = fields.Date(string='Date fin',   required=True, tracking=True)

    # Statut
    state = fields.Selection([
        ('draft',    'Brouillon'),
        ('actif',    'Actif'),
        ('en_cours', 'En cours'),
        ('suspendu', 'Suspendu'),
        ('expire',   'Expire'),
        ('resilie',  'Resilie'),
    ], string='Statut', default='draft', tracking=True, required=True)

    motif_suspension = fields.Text(string='Motif de suspension / resiliation', tracking=True)
    observations     = fields.Text(string='Observations')

    # BCG lie
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale',
        compute='_compute_commande_globale_id',
    )
    commande_globale_count = fields.Integer(
        string='BCG',
        compute='_compute_commande_globale_count',
    )

    _sql_constraints = [
        (
            'unique_project_contract',
            'UNIQUE(project_id)',
            'Ce projet a deja un contrat associe !',
        ),
    ]

    @api.depends()
    def _compute_commande_globale_id(self):
        BCG = self.env['gica.commande.globale']
        for rec in self:
            bcg = BCG.search(
                [('contrat_id', '=', rec.id),
                 ('state', 'not in', ['annulee'])],
                limit=1,
            )
            rec.commande_globale_id = bcg

    def _compute_commande_globale_count(self):
        for rec in self:
            rec.commande_globale_count = 1 if rec.commande_globale_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.client.contract'
                ) or 'Nouveau'
        records = super().create(vals_list)
        project_ids = records.mapped('project_id')
        if project_ids:
            project_ids.invalidate_recordset(['contract_id'])
        return records

    def unlink(self):
        project_ids = self.mapped('project_id')
        res = super().unlink()
        if project_ids:
            project_ids.invalidate_recordset(['contract_id'])
        return res

    # ── Onchanges ─────────────────────────────────────────────────────────

    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.project_id = False
        if self.client_id and self.client_id.client_type == 'realisation':
            projet = self.env['gica.project'].search(
                [('client_id', '=', self.client_id.id)], limit=1
            )
            self.project_id = projet or False

    @api.onchange('date_start')
    def _onchange_date_start(self):
        today = fields.Date.today()
        if self.date_start and self.date_start < today:
            return {
                'warning': {
                    'title':   'Date invalide',
                    'message': f'La date de debut ne peut pas etre dans le passe.\n'
                               f'Choisir une date a partir du {today}.',
                }
            }

    # ── Contraintes ───────────────────────────────────────────────────────

    @api.constrains('client_id', 'project_id')
    def _check_projet_realisation(self):
        for rec in self:
            if rec.client_id.client_type == 'realisation' and not rec.project_id:
                raise ValidationError(
                    'Un projet est obligatoire pour une Entreprise de realisation.'
                )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_start and rec.date_start < today:
                raise ValidationError('La date de debut ne peut pas etre dans le passe.')
            if rec.date_start and rec.date_end and rec.date_end <= rec.date_start:
                raise ValidationError('La date de fin doit etre posterieure a la date de debut.')

    @api.constrains('line_ids', 'mode_paiement', 'client_id')
    def _check_paiement_terme_interdit(self):
        for rec in self:
            if rec.mode_paiement != 'terme':
                continue
            for line in rec.line_ids:
                if line.type_ciment == 'clinker':
                    raise ValidationError('Le clinker ne peut pas etre vendu a terme.')
            bcg = rec.commande_globale_id
            if bcg and bcg.pricelist_id:
                if 'Exportation' in (bcg.pricelist_id.name or ''):
                    raise ValidationError(
                        "Les contrats d'exportation ne peuvent pas etre vendus a terme."
                    )
            if rec.client_id.client_type == 'exportation':
                raise ValidationError(
                    'Les clients exportateurs ne peuvent pas avoir un contrat a terme.'
                )

    @api.constrains('line_ids')
    def _check_lines_not_empty(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('Un contrat doit contenir au moins une ligne produit.')

    @api.constrains('line_ids')
    def _check_no_duplicate_product(self):
        """Un même produit ne peut pas apparaître deux fois dans un contrat."""
        for rec in self:
            product_ids = [l.product_tmpl_id.id for l in rec.line_ids]
            if len(product_ids) != len(set(product_ids)):
                raise ValidationError(
                    'Un meme produit ne peut pas apparaitre deux fois dans le contrat.'
                )

    # ── Actions ───────────────────────────────────────────────────────────

    def action_activer(self):
        for rec in self:
            if rec.client_id.client_type == 'realisation' and not rec.project_id:
                raise ValidationError('Impossible d\'activer ce contrat : projet manquant.')
        self.write({'state': 'actif'})

    def action_demarrer(self):
        self.write({'state': 'en_cours'})

    def action_suspendre(self):
        self.write({'state': 'suspendu'})

    def action_resilier(self):
        self.write({'state': 'resilie'})

    def action_voir_bcg(self):
        self.ensure_one()
        if not self.commande_globale_id:
            return self.action_creer_bcg()
        return {
            'type':      'ir.actions.act_window',
            'name':      f'BCG — {self.name}',
            'res_model': 'gica.commande.globale',
            'view_mode': 'form',
            'res_id':    self.commande_globale_id.id,
        }

    def action_creer_bcg(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Creer une commande globale',
            'res_model': 'gica.commande.globale',
            'view_mode': 'form',
            'target':    'current',
            'context': {
                'default_contrat_id': self.id,
                'default_client_id':  self.client_id.id,
            },
        }

    # ── Cron ──────────────────────────────────────────────────────────────

    @api.model
    def _cron_check_expiration(self):
        """Passe automatiquement les contrats dont la date de fin est dépassée en 'expire'."""
        today = fields.Date.today()
        expired = self.search([
            ('state', 'in', ['actif', 'en_cours']),
            ('date_end', '<', today),
        ])
        if expired:
            expired.write({'state': 'expire'})
            for rec in expired:
                rec.message_post(
                    body=f"Contrat expiré automatiquement le {today}."
                )