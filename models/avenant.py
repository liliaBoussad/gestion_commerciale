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

    conditionnement_id = fields.Many2one(
        'product.attribute.value',
        string='Conditionnement',
        domain="[('attribute_id.name', '=', 'Conditionnement')]",
        tracking=True,
    )

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

    # ── Computes ──────────────────────────────────────────────────────────

    @api.depends('commande_globale_id')
    def _compute_product_tmpl_ids(self):
        for rec in self:
            if rec.commande_globale_id:
                rec.product_tmpl_ids = rec.commande_globale_id.line_ids.mapped('product_tmpl_id')
            else:
                rec.product_tmpl_ids = False

    @api.depends('product_tmpl_id', 'conditionnement_id')
    def _compute_product_id(self):
        for rec in self:
            if rec.product_tmpl_id and rec.conditionnement_id:
                label = rec.conditionnement_id.name
                variant = rec.product_tmpl_id.product_variant_ids.filtered(
                    lambda v: any(
                        a.attribute_id.name == 'Conditionnement'
                        and a.product_attribute_value_id.name == label
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
                rec.commande_globale_id
                and rec.commande_globale_id.state in ('annulee', 'cloturee')
            )

    # ── Onchanges ─────────────────────────────────────────────────────────

    @api.onchange('commande_globale_id')
    def _onchange_commande_globale_id(self):
        self.product_tmpl_id   = False
        self.conditionnement_id = False

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        self.conditionnement_id = False
        if self.product_tmpl_id and self.commande_globale_id:
            # Filtre les conditionnements disponibles pour ce produit dans le BCG
            lignes = self.commande_globale_id.line_ids.filtered(
                lambda l: l.product_tmpl_id == self.product_tmpl_id
            )
            valeur_ids = lignes.mapped('conditionnement_id').ids
            # Prix de la première ligne si une seule ligne
            if len(lignes) == 1:
                self.ancien_prix = lignes[0].prix_unitaire
            return {
                'domain': {
                    'conditionnement_id': [('id', 'in', valeur_ids)]
                }
            }

    @api.onchange('conditionnement_id')
    def _onchange_conditionnement_id(self):
        if self.product_tmpl_id and self.conditionnement_id and self.commande_globale_id:
            ligne = self.commande_globale_id.line_ids.filtered(
                lambda l: l.product_tmpl_id == self.product_tmpl_id
                and l.conditionnement_id == self.conditionnement_id
            )
            if ligne:
                self.ancien_prix = ligne[0].prix_unitaire

    # ── Create ────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('gica.avenant') or 'Nouveau'
                )
        return super().create(vals_list)

    # ── Actions ───────────────────────────────────────────────────────────

    def action_valider(self):
        self.ensure_one()
        if self.state == 'valide':
            raise ValidationError('Cet avenant est deja valide.')
        if self.commande_globale_id.state in ('annulee', 'cloturee'):
            raise ValidationError(
                'Impossible de valider un avenant sur une commande annulee ou cloturee.'
            )

        if self.product_tmpl_id and self.conditionnement_id:
            ligne_bcg = self.commande_globale_id.line_ids.filtered(
                lambda l: l.product_tmpl_id == self.product_tmpl_id
                and l.conditionnement_id == self.conditionnement_id
            )
            if not ligne_bcg:
                raise ValidationError(
                    f'Le produit {self.product_tmpl_id.name} / '
                    f'{self.conditionnement_id.name} '
                    f'n\'existe pas dans le BCG {self.commande_globale_id.name}.'
                )

            if self.type_avenant == 'addition':
                if self.quantite:
                    ligne_bcg[0].quantity_tonne += self.quantite
                if self.nouveau_prix:
                    ligne_bcg[0].prix_unitaire = self.nouveau_prix

            elif self.type_avenant == 'reduction':
                if self.quantite:
                    if self.quantite > ligne_bcg[0].quantity_restante:
                        raise ValidationError(
                            f'La reduction ({self.quantite} T) depasse '
                            f'la quantite restante ({ligne_bcg[0].quantity_restante:.2f} T).'
                        )
                    ligne_bcg[0].quantity_tonne -= self.quantite
                if self.nouveau_prix:
                    ligne_bcg[0].prix_unitaire = self.nouveau_prix

        self.write({'state': 'valide'})

        cond_name = self.conditionnement_id.name if self.conditionnement_id else '-'

        self.message_post(
            body=f'Avenant valide — {self.type_avenant} de {self.quantite} T '
                 f'sur {self.product_tmpl_id.name} / {cond_name}'
        )
        self.commande_globale_id.message_post(
            body=f'Avenant {self.name} valide : {self.type_avenant} '
                 f'de {self.quantite} T sur {self.product_tmpl_id.name} '
                 f'/ {cond_name}'
        )

    def action_remettre_brouillon(self):
        self.ensure_one()
        self.write({'state': 'brouillon'})