# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaAvenant(models.Model):
    _name        = 'gica.avenant'
    _description = 'Avenant Commande Globale GICA'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date desc, id desc'

    name = fields.Char(
        string='Numéro',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    type_avenant = fields.Selection([
        ('addition',  'Addition'),
        ('reduction', 'Réduction'),
    ], string="Type d'avenant", required=True, default='addition', tracking=True)

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide',    'Validé'),
    ], string='État', default='brouillon', tracking=True, required=True)

    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Bon Global',
        required=True,
        tracking=True,
        ondelete='cascade',
    )

    client_id = fields.Many2one(
        'gica.client',
        string='Client',
        tracking=True,
    )

    product_tmpl_ids = fields.Many2many(
        'product.template',
        compute='_compute_product_tmpl_ids',
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit',
        required=True,
        domain="[('id', 'in', product_tmpl_ids)]",
        tracking=True,
    )

    product_id = fields.Many2one(
        'product.product',
        string='Variante',
        compute='_compute_product_id',
        store=True,
    )

    conditionnement_ids = fields.Many2many(
        'product.attribute.value',
        compute='_compute_conditionnement_ids',
    )

    conditionnement_id = fields.Many2one(
        'product.attribute.value',
        string='Conditionnement',
        domain="[('id', 'in', conditionnement_ids)]",
        tracking=True,
    )

    ancien_prix = fields.Float(
        string='Ancien prix (DA)',
        readonly=True,
        tracking=True,
    )

    nouveau_prix = fields.Float(
        string='Nouveau prix (DA)',
        tracking=True,
    )

    quantite = fields.Float(
        string='Quantité (T)',
        tracking=True,
    )

    nbr_paquets = fields.Float(
        string='Nbr paquets',
        tracking=True,
    )

    motif = fields.Text(
        string='Motif / Justification',
        required=True,
        tracking=True,
    )

    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='Utilisateur',
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
    )

    alerte_commande = fields.Boolean(
        compute='_compute_alerte_commande',
    )

    @api.depends('commande_globale_id')
    def _compute_product_tmpl_ids(self):
        for rec in self:
            if rec.commande_globale_id:
                rec.product_tmpl_ids = rec.commande_globale_id.line_ids.mapped('product_tmpl_id')
            else:
                rec.product_tmpl_ids = False

    @api.depends('commande_globale_id', 'product_tmpl_id')
    def _compute_conditionnement_ids(self):
        for rec in self:
            if rec.commande_globale_id and rec.product_tmpl_id:
                lines = rec.commande_globale_id.line_ids.filtered(
                    lambda l: l.product_tmpl_id == rec.product_tmpl_id
                )
                rec.conditionnement_ids = lines.mapped('conditionnement_id')
            elif rec.commande_globale_id:
                rec.conditionnement_ids = rec.commande_globale_id.line_ids.mapped('conditionnement_id')
            else:
                rec.conditionnement_ids = False

    @api.depends('product_tmpl_id', 'conditionnement_id')
    def _compute_product_id(self):
        for rec in self:
            if rec.product_tmpl_id and rec.conditionnement_id:
                variant = rec.product_tmpl_id.product_variant_ids.filtered(
                    lambda v: any(
                        a.product_attribute_value_id == rec.conditionnement_id
                        for a in v.product_template_attribute_value_ids
                    )
                )
                rec.product_id = variant[0] if variant else False
            else:
                rec.product_id = False

    @api.depends('commande_globale_id.state')
    def _compute_alerte_commande(self):
        for rec in self:
            rec.alerte_commande = (
                rec.commande_globale_id and
                rec.commande_globale_id.state in ('annulee', 'cloturee')
            )

    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.commande_globale_id = False

    @api.onchange('commande_globale_id')
    def _onchange_commande_globale_id(self):
        if self.commande_globale_id and not self.client_id:
            self.client_id = self.commande_globale_id.client_id
        self.product_tmpl_id = False
        self.conditionnement_id = False

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        self.conditionnement_id = False
        if self.product_tmpl_id and self.commande_globale_id:
            ligne = self.commande_globale_id.line_ids.filtered(
                lambda l: l.product_tmpl_id == self.product_tmpl_id
            )
            if ligne:
                self.ancien_prix = ligne[0].prix_unitaire

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('gica.avenant') or 'Nouveau'
                )
        return super().create(vals_list)

    def action_valider(self):
        self.ensure_one()
        if self.state == 'valide':
            raise ValidationError('Cet avenant est déjà validé.')
        if self.commande_globale_id.state in ('annulee', 'cloturee'):
            raise ValidationError(
                'Impossible de valider un avenant sur une commande annulée ou clôturée.'
            )
        self.write({'state': 'valide'})
        self.message_post(body='Avenant validé.')

    def action_remettre_brouillon(self):
        self.ensure_one()
        self.write({'state': 'brouillon'})