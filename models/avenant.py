# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaAvenant(models.Model):
    _name        = 'gica.avenant'
    _description = 'Avenant Commande Globale GICA'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date desc, id desc'

    name = fields.Char(
        string='Numero',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    type_avenant = fields.Selection([
        ('addition',  'Addition'),
        ('reduction', 'Reduction'),
    ], string="Type d'avenant", required=True, default='addition', tracking=True)

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide',    'Valide'),
    ], string='Etat', default='brouillon', tracking=True, required=True)

    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Bon Global',
        required=True,
        tracking=True,
        ondelete='cascade',
    )

    client_id = fields.Many2one(
        'res.partner',
        related='commande_globale_id.client_id',
        string='Client',
        store=True,
        readonly=True,
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

    conditionnement = fields.Selection([
        ('sac_25kg',           'Sac 25kg'),
        ('sac_50kg',           'Sac 50kg'),
        ('sac_25kg_fardelise', 'Sac 25kg Fardelise'),
        ('sac_50kg_fardelise', 'Sac 50kg Fardelise'),
        ('vrac',               'Vrac'),
        ('big_bag_client',     'Big Bag Client'),
        ('big_bag_scaek',      'Big Bag Scaek'),
    ], string='Conditionnement', tracking=True)

    product_id = fields.Many2one(
        'product.product',
        string='Variante',
        compute='_compute_product_id',
        store=True,
    )

    ancien_prix  = fields.Float(string='Ancien prix (DA)',  readonly=True, tracking=True)
    nouveau_prix = fields.Float(string='Nouveau prix (DA)', tracking=True)
    quantite     = fields.Float(string='Quantite (T)',      tracking=True)
    nbr_paquets  = fields.Float(string='Nbr paquets',       tracking=True)

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

    alerte_commande = fields.Boolean(compute='_compute_alerte_commande')

    @api.depends('commande_globale_id')
    def _compute_product_tmpl_ids(self):
        for rec in self:
            if rec.commande_globale_id:
                rec.product_tmpl_ids = rec.commande_globale_id.line_ids.mapped('product_tmpl_id')
            else:
                rec.product_tmpl_ids = False

    @api.depends('product_tmpl_id', 'conditionnement')
    def _compute_product_id(self):
        for rec in self:
            if rec.product_tmpl_id and rec.conditionnement:
                label = dict(rec._fields['conditionnement'].selection).get(rec.conditionnement)
                variant = rec.product_tmpl_id.product_variant_ids.filtered(
                    lambda v: any(
                        a.attribute_id.name == 'Conditionnement' and
                        a.product_attribute_value_id.name == label
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

    @api.onchange('commande_globale_id')
    def _onchange_commande_globale_id(self):
        self.product_tmpl_id = False
        self.conditionnement = False

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        self.conditionnement = False
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
            raise ValidationError('Cet avenant est deja valide.')
        if self.commande_globale_id.state in ('annulee', 'cloturee'):
            raise ValidationError(
                'Impossible de valider un avenant sur une commande annulee ou cloturee.'
            )

        # Appliquer la modification sur la ligne BCG correspondante
        if self.product_tmpl_id and self.conditionnement:
            ligne_bcg = self.commande_globale_id.line_ids.filtered(
                lambda l: l.product_tmpl_id == self.product_tmpl_id
                and l.conditionnement == self.conditionnement
            )
            if not ligne_bcg:
                raise ValidationError(
                    f'Le produit {self.product_tmpl_id.name} / {self.conditionnement} '
                    f'n\'existe pas dans le BCG {self.commande_globale_id.name}.'
                )

            if self.type_avenant == 'addition':
                # Ajouter la quantite
                if self.quantite:
                    ligne_bcg[0].quantity_tonne += self.quantite
                # Mettre a jour le prix si specifie
                if self.nouveau_prix:
                    ligne_bcg[0].prix_unitaire = self.nouveau_prix

            elif self.type_avenant == 'reduction':
                # Verifier que la reduction ne depasse pas la quantite restante
                if self.quantite:
                    if self.quantite > ligne_bcg[0].quantity_restante:
                        raise ValidationError(
                            f'La reduction ({self.quantite} T) depasse '
                            f'la quantite restante ({ligne_bcg[0].quantity_restante:.2f} T).'
                        )
                    ligne_bcg[0].quantity_tonne -= self.quantite
                # Mettre a jour le prix si specifie
                if self.nouveau_prix:
                    ligne_bcg[0].prix_unitaire = self.nouveau_prix

        self.write({'state': 'valide'})

        # Notifier dans le chatter de l'avenant
        self.message_post(
            body=f'Avenant valide — {self.type_avenant} de {self.quantite} T '
                 f'sur {self.product_tmpl_id.name} / {self.conditionnement}'
        )

        # Notifier dans le chatter du BCG
        self.commande_globale_id.message_post(
            body=f'Avenant {self.name} valide : {self.type_avenant} '
                 f'de {self.quantite} T sur {self.product_tmpl_id.name} '
                 f'/ {self.conditionnement}'
        )

    def action_remettre_brouillon(self):
        self.ensure_one()
        self.write({'state': 'brouillon'})