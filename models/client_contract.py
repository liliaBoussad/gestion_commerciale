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

    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        domain="[('product_tmpl_id.is_gica_product', '=', True)]",
    )

    type_ciment = fields.Selection(
        related='product_id.product_tmpl_id.type_ciment',
        string='Famille ciment',
        store=True,
        readonly=True,
    )

    conditionnement = fields.Selection(
        related='product_id.conditionnement_gica',
        string='Conditionnement',
        store=True,
        readonly=True,
    )

    quantity = fields.Float(string='Quantité', required=True)

    uom = fields.Selection([
        ('tonne', 'Tonne'),
        ('sac',   'Sac'),
    ], string='Unité de mesure', required=True, default='tonne')

    quantity_tonne = fields.Float(
        string='Quantité (tonnes)',
        compute='_compute_quantity_tonne',
        store=True,
    )

    prix_unitaire = fields.Float(string='Prix unitaire (DA)')

    montant_total = fields.Float(
        string='Montant total (DA)',
        compute='_compute_montant_total',
        store=True,
    )

    quantity_livree = fields.Float(
        string='Qté livrée',
        compute='_compute_quantity_livree',
        store=True,
    )
    quantity_restante = fields.Float(
        string='Qté restante',
        compute='_compute_quantity_livree',
        store=True,
    )

    @api.depends('quantity', 'uom', 'conditionnement')
    def _compute_quantity_tonne(self):
        for rec in self:
            if rec.uom == 'tonne':
                rec.quantity_tonne = rec.quantity
            elif rec.uom == 'sac':
                if rec.conditionnement == 'sac_50kg':
                    rec.quantity_tonne = rec.quantity * 0.05
                elif rec.conditionnement in ('sac_25kg', 'sac_25kg_fardelise'):
                    rec.quantity_tonne = rec.quantity * 0.025
                else:
                    rec.quantity_tonne = rec.quantity
            else:
                rec.quantity_tonne = rec.quantity

    @api.depends('quantity', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantity * rec.prix_unitaire

    @api.depends('quantity')
    def _compute_quantity_livree(self):
        for rec in self:
            rec.quantity_livree   = 0.0
            rec.quantity_restante = rec.quantity

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.prix_unitaire = self.product_id.lst_price


class GicaClientContract(models.Model):
    _name = 'gica.client.contract'
    _description = 'Contrat Client GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    # ── Identification ────────────────────────────────────────────────────
    name = fields.Char(
        string='Numéro du contrat',
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
    )

    # ── Type client calculé (pour invisible dans la vue) ──────────────────
    client_type = fields.Selection(
        related='client_id.client_type',
        string='Type client',
        store=True,
        readonly=True,
    )

    # ── Projet (visible uniquement si Entreprise de réalisation) ──────────
    project_id = fields.Many2one(
        'gica.project',
        string='Projet',
        tracking=True,
        domain="[('client_id', '=', client_id)]",
    )

    # ── Lignes produits ───────────────────────────────────────────────────
    line_ids = fields.One2many(
        'gica.client.contract.line',
        'contract_id',
        string='Lignes produits',
        copy=True,
    )

    # ── Totaux ────────────────────────────────────────────────────────────
    montant_total = fields.Float(
        string='Montant total (DA)',
        compute='_compute_totaux',
        store=True,
    )
    quantity_total_tonne = fields.Float(
        string='Quantité totale (tonnes)',
        compute='_compute_totaux',
        store=True,
    )

    @api.depends('line_ids.montant_total', 'line_ids.quantity_tonne')
    def _compute_totaux(self):
        for rec in self:
            rec.montant_total        = sum(rec.line_ids.mapped('montant_total'))
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))

    # ── Paiement ──────────────────────────────────────────────────────────
    mode_paiement = fields.Selection([
        ('comptant', 'Paiement au comptant'),
        ('terme',    'Paiement à terme'),
    ], string='Mode de paiement', required=True, default='comptant', tracking=True)

    modalite_paiement = fields.Selection([
        ('cheque_certifie',  'Chèque de banque certifié'),
        ('cheque_ordinaire', 'Chèque ordinaire'),
        ('virement',         'Virement bancaire'),
        ('lettre_change',    'Lettre de change'),
        ('versement',        'Versement bancaire'),
        ('cib',              'Paiement électronique CIB'),
        ('especes',          'Espèces (max 200 000 DA, points de vente)'),
    ], string='Modalité de paiement', tracking=True)

    delai_paiement  = fields.Integer(string='Délai de paiement (jours)', default=0, tracking=True)
    delai_livraison = fields.Integer(string='Délai de livraison (jours)', tracking=True)

    # ── Livraison ─────────────────────────────────────────────────────────
    lieu_livraison = fields.Selection([
        ('depart_usine',   'Départ usine'),
        ('livraison_site', 'Livraison sur site client'),
    ], string='Lieu de livraison', tracking=True)
    adresse_livraison = fields.Char(string='Adresse de livraison')

    # ── Dates ─────────────────────────────────────────────────────────────
    date_start = fields.Date(string='Date début', required=True, tracking=True)
    date_end   = fields.Date(string='Date fin',   required=True, tracking=True)

    # ── Statut ────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',    'Brouillon'),
        ('actif',    'Actif'),
        ('en_cours', 'En cours'),
        ('suspendu', 'Suspendu'),
        ('expire',   'Expiré'),
        ('resilie',  'Résilié'),
    ], string='Statut', default='draft', tracking=True, required=True)

    motif_suspension = fields.Text(string='Motif de suspension / résiliation', tracking=True)
    observations     = fields.Text(string='Observations')

    # ── Contrainte unicité projet ─────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_project_contract',
            'UNIQUE(project_id)',
            '❌ Ce projet a déjà un contrat associé !',
        ),
    ]

    # ── ORM ───────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.client.contract'
                ) or 'Nouveau'
        records = super().create(vals_list)
        # Invalide le cache contract_id sur les projets liés
        # pour que le bouton "Créer un contrat" disparaisse immédiatement.
        project_ids = records.mapped('project_id')
        if project_ids:
            project_ids.invalidate_recordset(['contract_id'])
        return records

    def unlink(self):
        # Mémorise les projets avant suppression pour invalider après.
        project_ids = self.mapped('project_id')
        res = super().unlink()
        # Invalide le cache : le bouton "Créer un contrat" réapparaît.
        if project_ids:
            project_ids.invalidate_recordset(['contract_id'])
        return res

    # ── Onchange ──────────────────────────────────────────────────────────
    @api.onchange('client_id')
    def _onchange_client_id(self):
        """Quand on sélectionne un client ER, le projet se remplit automatiquement."""
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
                    'title': '⛔ Date invalide',
                    'message': (
                        f'La date de début ne peut pas être dans le passé.\n'
                        f'👉 Choisir une date à partir du {today}.'
                    ),
                }
            }

    # ── Contraintes ───────────────────────────────────────────────────────
    @api.constrains('client_id', 'project_id')
    def _check_projet_realisation(self):
        """Bloque la sauvegarde si un client ER n'a pas de projet associé."""
        for rec in self:
            if rec.client_id.client_type == 'realisation' and not rec.project_id:
                raise ValidationError(
                    '❌ Un projet est obligatoire pour une Entreprise de réalisation.\n'
                    '👉 Créez d\'abord un projet pour ce client avant de créer le contrat.'
                )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_start and rec.date_start < today:
                raise ValidationError(
                    f'❌ La date de début ne peut pas être dans le passé.\n'
                    f'👉 Choisir une date à partir du {today}.'
                )
            if rec.date_start and rec.date_end and rec.date_end <= rec.date_start:
                raise ValidationError(
                    '❌ La date de fin doit être postérieure à la date de début.'
                )

    @api.constrains('line_ids', 'mode_paiement')
    def _check_paiement_clinker(self):
        for rec in self:
            if rec.mode_paiement == 'terme':
                for line in rec.line_ids:
                    if line.type_ciment == 'clinker':
                        raise ValidationError(
                            'Le clinker ne peut pas être vendu à terme (règle GICA Article V).'
                        )

    @api.constrains('line_ids')
    def _check_lines_not_empty(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('Un contrat doit contenir au moins une ligne produit.')

    @api.constrains('line_ids')
    def _check_no_duplicate_product(self):
        for rec in self:
            products = [l.product_id.id for l in rec.line_ids]
            if len(products) != len(set(products)):
                raise ValidationError(
                    'Un même produit/conditionnement ne peut pas apparaître deux fois.'
                )

    # ── Actions ───────────────────────────────────────────────────────────
    def action_activer(self):
        """Bloque l'activation si client ER sans projet."""
        for rec in self:
            if rec.client_id.client_type == 'realisation' and not rec.project_id:
                raise ValidationError(
                    '❌ Impossible d\'activer ce contrat : projet manquant.\n'
                    '👉 Associez un projet avant d\'activer le contrat.'
                )
        self.write({'state': 'actif'})

    def action_demarrer(self):
        self.write({'state': 'en_cours'})

    def action_suspendre(self):
        self.write({'state': 'suspendu'})

    def action_resilier(self):
        self.write({'state': 'resilie'})

    # ── Cron ──────────────────────────────────────────────────────────────
    @api.model
    def _cron_check_expiration(self):
        today = fields.Date.today()
        self.search([
            ('state', 'in', ['actif', 'en_cours']),
            ('date_end', '<', today),
        ]).write({'state': 'expire'})