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

    # ── De la binôme : product_tmpl_id + conditionnement + _compute_product_id ──
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit',
        required=True,
        domain="[('is_gica_product', '=', True)]",
    )

    conditionnement = fields.Selection([
        ('sac_25kg',           'Sac 25 kg'),
        ('sac_50kg',           'Sac 50 kg'),
        ('sac_25kg_fardelise', 'Sac 25 kg Fardelisé'),
        ('sac_50kg_fardelise', 'Sac 50 kg Fardelisé'),
        ('vrac',               'Vrac'),
        ('big_bag_client',     'Big-Bag (charge client)'),
        ('big_bag_scaek',      'Big-Bag (charge SCAEK)'),
    ], string='Conditionnement', required=True)

    product_id = fields.Many2one(
        'product.product',
        string='Variante',
        compute='_compute_product_id',
        store=True,
    )

    type_ciment = fields.Selection(
        related='product_tmpl_id.type_ciment',
        string='Famille ciment',
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

    @api.depends('product_tmpl_id', 'conditionnement')
    def _compute_product_id(self):
        for rec in self:
            if rec.product_tmpl_id and rec.conditionnement:
                variant = rec.product_tmpl_id.product_variant_ids.filtered(
                    lambda v: any(
                        a.attribute_id.name == 'Conditionnement' and
                        a.product_attribute_value_id.name == dict(
                            rec._fields['conditionnement'].selection
                        ).get(rec.conditionnement)
                        for a in v.product_template_attribute_value_ids
                    )
                )
                rec.product_id = variant[0] if variant else False
            else:
                rec.product_id = False

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

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        self.conditionnement = False
        self.prix_unitaire = 0.0

    @api.onchange('product_tmpl_id', 'conditionnement')
    def _onchange_product_conditionnement(self):
        if self.product_tmpl_id and self.conditionnement:
            self.prix_unitaire = self.product_tmpl_id.list_price


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

    # ── Votre version : res.partner ───────────────────────────────────────
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
    )

    client_type = fields.Selection(
        related='client_id.client_type',
        string='Type client',
        store=True,
        readonly=True,
    )

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

    # ── BCG lié ───────────────────────────────────────────────────────────
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale',
        compute='_compute_commande_globale_id',
    )
    commande_globale_count = fields.Integer(
        string='BCG',
        compute='_compute_commande_globale_count',
    )

    # ── Contrainte unicité projet ─────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_project_contract',
            'UNIQUE(project_id)',
            '❌ Ce projet a déjà un contrat associé !',
        ),
    ]

    # ── Computed BCG ──────────────────────────────────────────────────────
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

    # ── ORM ───────────────────────────────────────────────────────────────
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

    # ── Onchange ──────────────────────────────────────────────────────────
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
            combinations = [
                (l.product_tmpl_id.id, l.conditionnement)
                for l in rec.line_ids
            ]
            if len(combinations) != len(set(combinations)):
                raise ValidationError(
                    'Un même produit/conditionnement ne peut pas apparaître deux fois.'
                )

    # ── Actions ───────────────────────────────────────────────────────────
    def action_activer(self):
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

    def action_voir_bcg(self):
        self.ensure_one()
        if not self.commande_globale_id:
            return self.action_creer_bcg()
        return {
            'type': 'ir.actions.act_window',
            'name': f'BCG — {self.name}',
            'res_model': 'gica.commande.globale',
            'view_mode': 'form',
            'res_id': self.commande_globale_id.id,
        }

    def action_creer_bcg(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Créer une commande globale',
            'res_model': 'gica.commande.globale',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_contrat_id': self.id,
                'default_client_id':  self.client_id.id,
            },
        }

    # ── Cron ──────────────────────────────────────────────────────────────
    @api.model
    def _cron_check_expiration(self):
        """Passe les contrats expirés à l'état 'expire' chaque nuit."""
        today = fields.Date.today()
        self.search([
            ('state', 'in', ['actif', 'en_cours']),
            ('date_end', '<', today),
        ]).write({'state': 'expire'})