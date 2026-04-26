# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaBonCommandeLine(models.Model):
    _name = 'gica.bon.commande.line'
    _description = 'Ligne Bon de Commande GICA'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    bon_commande_id = fields.Many2one(
        'gica.bon.commande',
        string='Bon de Commande',
        required=True,
        ondelete='cascade',
    )

    # ── Produit — Many2one vers product.product ───────────────────────────
    product_id = fields.Many2one(
        'product.product',
        string='Produit / Conditionnement',
        required=True,
        domain="[('product_tmpl_id.is_gica_product', '=', True)]",
    )

    conditionnement = fields.Selection(
        related='product_id.conditionnement_gica',
        string='Conditionnement',
        store=True,
        readonly=True,
    )

    quantity_tonne = fields.Float(string='Quantité (T)', required=True)

    prix_unitaire = fields.Float(
        string='Prix unitaire (DA)',
        compute='_compute_prix_unitaire',
        store=True,
    )

    montant_total = fields.Float(
        string='Montant (DA)',
        compute='_compute_montant_total',
        store=True,
    )

    quantity_disponible = fields.Float(
        string='Disponible BCG (T)',
        compute='_compute_quantity_disponible',
    )

    @api.depends('bon_commande_id.commande_globale_id', 'product_id')
    def _compute_prix_unitaire(self):
        for rec in self:
            prix = 0.0
            if rec.bon_commande_id.commande_globale_id and rec.product_id:
                bcg_line = rec.bon_commande_id.commande_globale_id.line_ids.filtered(
                    lambda l: l.product_id == rec.product_id
                )
                if bcg_line:
                    prix = bcg_line[0].prix_unitaire
            rec.prix_unitaire = prix

    @api.depends('quantity_tonne', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantity_tonne * rec.prix_unitaire

    @api.depends('bon_commande_id.commande_globale_id',
                 'bon_commande_id.commande_globale_id.bon_commande_ids',
                 'product_id')
    def _compute_quantity_disponible(self):
        for rec in self:
            disponible = 0.0
            if rec.bon_commande_id.commande_globale_id and rec.product_id:
                bcg = rec.bon_commande_id.commande_globale_id
                bcg_line = bcg.line_ids.filtered(lambda l: l.product_id == rec.product_id)
                if bcg_line:
                    qty_bcg = bcg_line[0].quantity_tonne
                    autres_bc = bcg.bon_commande_ids.filtered(
                        lambda bc: bc.id != rec.bon_commande_id.id
                        and bc.state != 'annule'
                    )
                    qty_prise = sum(
                        l.quantity_tonne
                        for bc in autres_bc
                        for l in bc.line_ids
                        if l.product_id == rec.product_id
                    )
                    disponible = qty_bcg - qty_prise
            rec.quantity_disponible = disponible

    @api.constrains('product_id', 'bon_commande_id')
    def _check_produit_dans_bcg(self):
        for rec in self:
            bcg = rec.bon_commande_id.commande_globale_id
            if not bcg:
                continue
            bcg_line = bcg.line_ids.filtered(lambda l: l.product_id == rec.product_id)
            if not bcg_line:
                raise ValidationError(
                    f'❌ Le produit "{rec.product_id.display_name}" '
                    f'n\'existe pas dans la commande globale {bcg.name}.\n\n'
                    f'Veuillez choisir uniquement les produits du contrat.'
                )

    @api.constrains('quantity_tonne', 'product_id', 'bon_commande_id')
    def _check_quantite_disponible(self):
        for rec in self:
            if rec.quantity_tonne <= 0:
                raise ValidationError('❌ La quantité doit être supérieure à 0.')
            bcg = rec.bon_commande_id.commande_globale_id
            if not bcg or not rec.product_id:
                continue
            bcg_line = bcg.line_ids.filtered(lambda l: l.product_id == rec.product_id)
            if not bcg_line:
                continue

            qty_bcg = bcg_line[0].quantity_tonne
            autres_bc = bcg.bon_commande_ids.filtered(
                lambda bc: bc.id != rec.bon_commande_id.id and bc.state != 'annule'
            )
            qty_prise = sum(
                l.quantity_tonne
                for bc in autres_bc
                for l in bc.line_ids
                if l.product_id == rec.product_id
            )
            qty_totale = qty_prise + rec.quantity_tonne

            if qty_totale > qty_bcg:
                raise ValidationError(
                    f'❌ Quantité dépassée pour {rec.product_id.display_name} :\n\n'
                    f'  📦 Quantité BCG totale  : {qty_bcg:.2f} T\n'
                    f'  ✅ Déjà commandé        : {qty_prise:.2f} T\n'
                    f'  🛒 Ce bon de commande   : {rec.quantity_tonne:.2f} T\n'
                    f'  ⚠️  Total               : {qty_totale:.2f} T\n\n'
                    f'  👉 Quantité disponible  : {qty_bcg - qty_prise:.2f} T'
                )


class GicaBonCommande(models.Model):
    _name = 'gica.bon.commande'
    _description = 'Bon de Commande GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_creation desc'
    _rec_name = 'name'

    name = fields.Char(string='Numéro BC', readonly=True, copy=False, default='Nouveau', tracking=True)

    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('state', 'in', ['nouveau', 'en_cours'])]",
    )

    client_id = fields.Many2one(
        'gica.client', related='commande_globale_id.client_id', store=True, readonly=True,
    )
    contrat_id = fields.Many2one(
        'gica.client.contract', related='commande_globale_id.contrat_id', store=True, readonly=True,
    )

    date_creation = fields.Date(string='Date de création', required=True, default=fields.Date.today, tracking=True)
    date_prevue_enlevement = fields.Date(string="Date prévue d'enlèvement", required=True, tracking=True)
    date_reelle_enlevement = fields.Date(string="Date réelle d'enlèvement", readonly=True, tracking=True)

    state = fields.Selection([
        ('brouillon',  'Brouillon'),
        ('en_attente', 'En attente validation'),
        ('valide',     'Validé'),
        ('enleve',     'Enlevé'),
        ('annule',     'Annulé'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    line_ids = fields.One2many('gica.bon.commande.line', 'bon_commande_id', string='Lignes produits')

    bon_circulation_id = fields.Many2one('gica.bon.circulation', string='Bon de Circulation', readonly=True)

    quantity_total_tonne = fields.Float(compute='_compute_totaux', store=True)
    montant_total        = fields.Float(compute='_compute_totaux', store=True)
    observations         = fields.Text(string='Observations')

    @api.depends('line_ids.quantity_tonne', 'line_ids.montant_total')
    def _compute_totaux(self):
        for rec in self:
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))
            rec.montant_total        = sum(rec.line_ids.mapped('montant_total'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('gica.bon.commande') or 'Nouveau'
        return super().create(vals_list)

    @api.constrains('date_prevue_enlevement')
    def _check_date_enlevement(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_prevue_enlevement and rec.date_prevue_enlevement < today:
                raise ValidationError(
                    f'❌ La date d\'enlèvement ({rec.date_prevue_enlevement}) '
                    f'ne peut pas être dans le passé.\n\n'
                    f'👉 Choisir une date à partir du {today}.'
                )

    @api.constrains('commande_globale_id')
    def _check_commande_globale_active(self):
        for rec in self:
            if rec.commande_globale_id.state not in ('nouveau', 'en_cours'):
                raise ValidationError('❌ Impossible de créer un BC sur une commande clôturée ou annulée.')

    def action_soumettre(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('❌ Le BC doit contenir au moins une ligne produit.')
            rec._check_date_enlevement()
            rec.write({'state': 'en_attente'})
            rec.message_post(body=f'📋 BC soumis à validation pour enlèvement le {rec.date_prevue_enlevement}.')

    def action_valider(self):
        for rec in self:
            rec.write({'state': 'valide'})
            rec.message_post(body=f'✅ BC validé — enlèvement prévu le {rec.date_prevue_enlevement}.')

    def action_marquer_enleve(self):
        for rec in self:
            rec.write({'state': 'enleve', 'date_reelle_enlevement': fields.Date.today()})
            rec.commande_globale_id._check_cloture_automatique()
            rec.message_post(body=f'📦 Marchandise enlevée le {fields.Date.today()}.')

    def action_annuler(self):
        for rec in self:
            if rec.state == 'enleve':
                raise ValidationError('❌ Impossible d\'annuler un BC déjà enlevé.')
            rec.write({'state': 'annule'})

    def action_remettre_brouillon(self):
        for rec in self:
            if rec.state in ('brouillon', 'valide', 'enleve'):
                raise ValidationError('❌ Impossible de remettre en brouillon depuis cet état.')
            rec.write({'state': 'brouillon'})