# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaProject(models.Model):
    _name        = 'gica.project'
    _description = 'Projet client — Entreprise de Réalisation'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_debut desc, name'

    # ── Identification ────────────────────────────────────────────────────
    name = fields.Char(
        string='Nom du projet', required=True, tracking=True,
    )
    reference = fields.Char(
        string='Référence projet', readonly=True, copy=False,
    )
    client_id = fields.Many2one(
        'res.partner', string='Client',
        ondelete='cascade', tracking=True,
        domain="[('client_type','=','realisation')]",
    )
    client_ref = fields.Char(
        string='Code client',
        related='client_id.ref',
        store=True,
        readonly=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────
    date_debut = fields.Date(string='Date début', tracking=True)
    date_fin   = fields.Date(string='Date fin',   tracking=True)

    # ── Localisation ──────────────────────────────────────────────────────
    wilaya    = fields.Char(string='Wilaya')
    commune   = fields.Char(string='Commune')
    adresse   = fields.Char(string='Adresse du chantier')

    # ── Statut ────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('en_cours',  'En cours'),
        ('termine',   'Terminé'),
        ('annule',    'Annulé'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    # ── Lignes produits ───────────────────────────────────────────────────
    line_ids = fields.One2many(
        'gica.project.line', 'project_id', string='Produits du projet',
    )

    # ── Totaux ────────────────────────────────────────────────────────────
    quantity_total = fields.Float(
        string='Quantité totale',
        compute='_compute_totaux', store=True,
    )
    nb_produits = fields.Integer(
        string='Nb produits',
        compute='_compute_totaux', store=True,
    )

    # ── Contrat lié (calculé automatiquement, sans store) ─────────────────
    # Pas de store=True : recalculé à chaque affichage, toujours frais.
    # Sert uniquement à piloter le bouton invisible et le smart button.
    contract_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat',
        compute='_compute_contract_id',
    )
    contract_count = fields.Integer(
        string='Contrats',
        compute='_compute_contract_count',
    )

    # ── Observations ──────────────────────────────────────────────────────
    observations = fields.Text(string='Observations')

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends('line_ids.quantity_tonne')
    def _compute_totaux(self):
        for rec in self:
            rec.quantity_total = sum(rec.line_ids.mapped('quantity_tonne'))
            rec.nb_produits    = len(rec.line_ids)

    # @api.depends() vide : Odoo recalcule à chaque lecture du champ.
    # Le cache est invalidé manuellement depuis gica.client.contract
    # lors d'un create() ou unlink() pour rafraîchir l'UI immédiatement.
    @api.depends()
    def _compute_contract_id(self):
        Contract = self.env['gica.client.contract']
        for rec in self:
            contract = Contract.search(
                [('project_id', '=', rec.id)], limit=1
            )
            rec.contract_id = contract

    def _compute_contract_count(self):
        for rec in self:
            rec.contract_count = 1 if rec.contract_id else 0

    # ── ORM ───────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('gica.project') or 'Nouveau'
                )
        return super().create(vals_list)

    # ── Contraintes ───────────────────────────────────────────────────────
    @api.constrains('client_id')
    def _check_client_er(self):
        for rec in self:
            if rec.client_id and rec.client_id.client_type != 'realisation':
                raise ValidationError(
                    '❌ Un projet ne peut être créé que pour une Entreprise de Réalisation.'
                )

    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_debut and rec.date_fin and rec.date_fin < rec.date_debut:
                raise ValidationError(
                    '❌ La date de fin doit être postérieure à la date de début.'
                )

    # ── Actions ───────────────────────────────────────────────────────────
    def action_demarrer(self):
        self.write({'state': 'en_cours'})

    def action_terminer(self):
        self.write({'state': 'termine'})

    def action_annuler(self):
        self.write({'state': 'annule'})

    def action_brouillon(self):
        self.write({'state': 'brouillon'})

    def action_voir_contrats(self):
        self.ensure_one()
        if not self.contract_id:
            return self.action_creer_contrat()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Contrat — {self.name}',
            'res_model': 'gica.client.contract',
            'view_mode': 'form',
            'res_id': self.contract_id.id,
        }

    def action_creer_contrat(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Créer un contrat',
            'res_model': 'gica.client.contract',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.id,
                'default_client_id':  self.client_id.id,
            },
        }


class GicaProjectLine(models.Model):
    _name        = 'gica.project.line'
    _description = 'Produit du projet'
    _order       = 'sequence, id'

    sequence   = fields.Integer(default=10)
    project_id = fields.Many2one(
        'gica.project', string='Projet', ondelete='cascade', required=True,
    )
    client_id = fields.Many2one(
        related='project_id.client_id', store=True, string='Client',
    )
    project_name = fields.Char(
        related='project_id.name', string='Nom du projet', store=True,
    )

    # ── Aligné sur gica.client.contract.line ──
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
    quantity = fields.Float(string='Quantité', required=True)
    uom = fields.Selection([
        ('tonne', 'Tonne'),
        ('sac',   'Sac'),
    ], string='Unité', required=True, default='tonne')
    quantity_tonne = fields.Float(
        string='Qté (T)',
        compute='_compute_quantity_tonne',
        store=True,
    )

    @api.depends('quantity', 'uom')
    def _compute_quantity_tonne(self):
        for rec in self:
            rec.quantity_tonne = rec.quantity