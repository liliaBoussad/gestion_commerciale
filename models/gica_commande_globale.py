# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaCommandeGlobaleLine(models.Model):
    _name = 'gica.commande.globale.line'
    _description = 'Ligne Commande Globale GICA'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    commande_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale',
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

    product_name = fields.Char(
        related='product_id.product_tmpl_id.name',
        string='Produit',
        readonly=True,
        store=True,
    )

    conditionnement = fields.Selection(
        related='product_id.conditionnement_gica',
        string='Conditionnement',
        store=True,
        readonly=True,
    )

    quantity_tonne = fields.Float(string='Quantité (T)', required=True)
    prix_unitaire  = fields.Float(string='Prix unitaire (DA)', required=True)

    montant_total = fields.Float(
        string='Montant total (DA)',
        compute='_compute_montant_total',
        store=True,
    )

    quantity_enlevee = fields.Float(
        string='Qté enlevée (T)',
        compute='_compute_quantity_enlevee',
        store=True,
    )

    quantity_restante = fields.Float(
        string='Qté restante (T)',
        compute='_compute_quantity_enlevee',
        store=True,
    )

    @api.depends('quantity_tonne', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantity_tonne * rec.prix_unitaire

    @api.depends('commande_id.bon_commande_ids.line_ids.quantity_tonne',
                 'commande_id.bon_commande_ids.state')
    def _compute_quantity_enlevee(self):
        for rec in self:
            bc_enleves = rec.commande_id.bon_commande_ids.filtered(
                lambda bc: bc.state == 'enleve'
            )
            enlevee = sum(
                line.quantity_tonne
                for bc in bc_enleves
                for line in bc.line_ids
                if line.product_id == rec.product_id
            )
            rec.quantity_enlevee  = enlevee
            rec.quantity_restante = rec.quantity_tonne - enlevee


class GicaCommandeGlobale(models.Model):
    _name = 'gica.commande.globale'
    _description = 'Commande Globale GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_commande desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Numéro',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    client_id = fields.Many2one('gica.client', string='Client', required=True, tracking=True)
    contrat_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat',
        required=True,
        tracking=True,
        domain="[('client_id', '=', client_id), ('state', 'in', ['actif', 'en_cours'])]",
    )

    date_commande = fields.Date(
        string='Date de la commande',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    date_expiration = fields.Date(
        string="Date d'expiration",
        related='contrat_id.date_end',
        store=True,
        readonly=True,
    )

    state = fields.Selection([
        ('nouveau',  'Nouveau'),
        ('en_cours', 'En cours'),
        ('cloturee', 'Clôturée'),
        ('annulee',  'Annulée'),
    ], string='Statut', default='nouveau', tracking=True, required=True)

    line_ids = fields.One2many(
        'gica.commande.globale.line', 'commande_id', string='Lignes produits',
    )
    bon_commande_ids = fields.One2many(
        'gica.bon.commande', 'commande_globale_id', string='Bons de Commande',
    )
    bon_commande_count = fields.Integer(compute='_compute_bon_commande_count')

    montant_total        = fields.Float(compute='_compute_totaux', store=True)
    quantity_total_tonne = fields.Float(compute='_compute_totaux', store=True)
    quantity_enlevee     = fields.Float(compute='_compute_totaux', store=True)
    quantity_restante    = fields.Float(compute='_compute_totaux', store=True)
    taux_realisation     = fields.Float(compute='_compute_totaux', store=True)

    mode_paiement    = fields.Selection(related='contrat_id.mode_paiement',    readonly=True)
    modalite_paiement = fields.Selection(related='contrat_id.modalite_paiement', readonly=True)
    devise           = fields.Char(default='DZD', readonly=True)
    observations     = fields.Text(string='Observations')

    @api.depends('bon_commande_ids')
    def _compute_bon_commande_count(self):
        for rec in self:
            rec.bon_commande_count = len(rec.bon_commande_ids)

    @api.depends('line_ids.montant_total', 'line_ids.quantity_tonne', 'line_ids.quantity_enlevee')
    def _compute_totaux(self):
        for rec in self:
            rec.montant_total        = sum(rec.line_ids.mapped('montant_total'))
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))
            rec.quantity_enlevee     = sum(rec.line_ids.mapped('quantity_enlevee'))
            rec.quantity_restante    = sum(rec.line_ids.mapped('quantity_restante'))
            rec.taux_realisation     = (
                (rec.quantity_enlevee / rec.quantity_total_tonne * 100)
                if rec.quantity_total_tonne else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.commande.globale'
                ) or 'Nouveau'
        return super().create(vals_list)

    @api.onchange('contrat_id')
    def _onchange_contrat_id(self):
        if self.contrat_id:
            lines = []
            for line in self.contrat_id.line_ids:
                lines.append((0, 0, {
                    'product_id':    line.product_id.id,
                    'quantity_tonne': line.quantity_tonne,
                    'prix_unitaire':  line.prix_unitaire,
                }))
            self.line_ids = lines

    def action_demarrer(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('La commande globale doit avoir au moins une ligne.')
            rec.write({'state': 'en_cours'})

    def action_annuler(self):
        for rec in self:
            if rec.state == 'cloturee':
                raise ValidationError('Impossible d\'annuler une commande clôturée.')
            rec.write({'state': 'annulee'})

    def action_remettre_nouveau(self):
        for rec in self:
            if rec.state == 'annulee':
                rec.write({'state': 'nouveau'})

    def _check_cloture_automatique(self):
        for rec in self:
            if (rec.state == 'en_cours'
                    and rec.quantity_total_tonne > 0
                    and rec.quantity_restante <= 0):
                rec.write({'state': 'cloturee'})
                rec.message_post(body='✅ Commande clôturée — toute la quantité a été enlevée.')

    def action_voir_bons_commande(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Commande',
            'res_model': 'gica.bon.commande',
            'view_mode': 'list,form',
            'domain':    [('commande_globale_id', '=', self.id)],
            'context':   {'default_commande_globale_id': self.id,
                          'default_client_id': self.client_id.id},
        }

    @api.constrains('contrat_id', 'client_id')
    def _check_contrat_client(self):
        for rec in self:
            if rec.contrat_id and rec.contrat_id.client_id != rec.client_id:
                raise ValidationError('Le contrat ne correspond pas à ce client.')

    @api.constrains('contrat_id')
    def _check_one_commande_per_contrat(self):
        for rec in self:
            existing = self.search([
                ('contrat_id', '=', rec.contrat_id.id),
                ('state', 'not in', ['annulee']),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(
                    f'Le contrat {rec.contrat_id.name} a déjà une commande '
                    f'globale active : {existing[0].name}.'
                )