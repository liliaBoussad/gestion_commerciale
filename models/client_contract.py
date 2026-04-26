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

    # ── Produit — Many2one vers product.product (variante Odoo) ──────────
    product_id = fields.Many2one(
        'product.product',
        string='Produit / Conditionnement',
        required=True,
        domain="[('product_tmpl_id.is_gica_product', '=', True)]",
    )

    # Champs liés au produit pour affichage
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

    # ── Quantité ──────────────────────────────────────────────────────────
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

    # ── Prix ──────────────────────────────────────────────────────────────
    prix_unitaire = fields.Float(
        string='Prix unitaire (DA)',
        required=True,
    )

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

    # ── Computed ───────────────────────────────────────────────────────────

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

    # Remplir le prix automatiquement depuis le produit
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.prix_unitaire = self.product_id.lst_price


class GicaClientContract(models.Model):
    _name = 'gica.client.contract'
    _description = 'Contrat Client GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    name = fields.Char(
        string='Numéro du contrat',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    client_id = fields.Many2one(
        'gica.client',
        string='Client',
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        'gica.client.contract.line',
        'contract_id',
        string='Lignes produits',
        copy=True,
    )

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

    delai_paiement = fields.Integer(
        string='Délai de paiement (jours)',
        default=0,
        tracking=True,
    )

    delai_livraison  = fields.Integer(string='Délai de livraison (jours)', tracking=True)
    lieu_livraison   = fields.Selection([
        ('depart_usine',   'Départ usine'),
        ('livraison_site', 'Livraison sur site client'),
    ], string='Lieu de livraison', tracking=True)
    adresse_livraison = fields.Char(string='Adresse de livraison')

    date_start = fields.Date(string='Date début', required=True, tracking=True)
    date_end   = fields.Date(string='Date fin',   required=True, tracking=True)

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

    # ── Contraintes ────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.client.contract'
                ) or 'Nouveau'
        return super().create(vals_list)




    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end <= rec.date_start:
                raise ValidationError('La date de fin doit être postérieure à la date de début.')

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

    # ── Workflow ───────────────────────────────────────────────────────────

    def action_activer(self):  self.write({'state': 'actif'})
    def action_demarrer(self): self.write({'state': 'en_cours'})
    def action_suspendre(self): self.write({'state': 'suspendu'})
    def action_resilier(self):  self.write({'state': 'resilie'})

    @api.model
    def _cron_check_expiration(self):
        today = fields.Date.today()
        self.search([
            ('state', 'in', ['actif', 'en_cours']),
            ('date_end', '<', today),
        ]).write({'state': 'expire'})