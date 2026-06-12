# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaCommandeGlobaleLine(models.Model):
    _name = 'gica.commande.globale.line'
    _description = 'Ligne Commande Globale GICA'
    _order = 'sequence, id'
    _rec_name = 'display_name_line'

    display_name_line = fields.Char(
        string='Designation',
        compute='_compute_display_name_line',
        store=True,
    )

    @api.depends('product_tmpl_id', 'conditionnement_id')
    def _compute_display_name_line(self):
        for rec in self:
            rec.display_name_line = rec.conditionnement_id.name or '-'

    sequence = fields.Integer(default=10)

    commande_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale',
        required=True,
        ondelete='cascade',
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit',
        required=True,
        domain="[('is_gica_product', '=', True)]",
    )

    conditionnement_id = fields.Many2one(
        'product.attribute.value',
        string='Conditionnement',
        domain="[('attribute_id.name', '=', 'Conditionnement')]",
    )

    product_id = fields.Many2one(
        'product.product',
        string='Variante',
        compute='_compute_product_id',
        store=True,
    )

    product_name = fields.Char(
        related='product_tmpl_id.name',
        string='Nom produit',
        readonly=True,
        store=True,
        translate=False,
    )

    quantity_tonne  = fields.Float(string='Quantite (T)', required=True)
    prix_unitaire   = fields.Float(string='Prix unitaire (DA)', default=0.0)

    montant_total = fields.Float(
        string='Montant total (DA)',
        compute='_compute_montant_total',
        store=True,
    )

    quantity_enlevee = fields.Float(
        string='Qte enlevee (T)',
        compute='_compute_quantity_enlevee',
        store=True,
    )

    quantity_restante = fields.Float(
        string='Qte restante (T)',
        compute='_compute_quantity_enlevee',
        store=True,
    )

    quantity_planifiee = fields.Float(
        string='Qte planifiee (T)',
        compute='_compute_quantity_planifiee',
        store=True,
    )

    # ── Computes ──────────────────────────────────────────────────────────

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

    @api.depends('quantity_tonne', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantity_tonne * rec.prix_unitaire

    @api.depends(
        'quantity_tonne',
        'commande_id.bon_commande_ids.order_line.product_uom_qty',
        'commande_id.bon_commande_ids.date_reelle_enlevement',
    )
    def _compute_quantity_enlevee(self):
        for rec in self:
            enlevee = 0.0
            if rec.commande_id and rec.product_tmpl_id and rec.conditionnement_id:
                label = rec.conditionnement_id.name
                bc_enleves = rec.commande_id.bon_commande_ids.filtered(
                    lambda bc: bc.date_reelle_enlevement
                )
                for bc in bc_enleves:
                    for line in bc.order_line:
                        if (line.product_id.product_tmpl_id == rec.product_tmpl_id
                                and line.product_id.product_template_attribute_value_ids.filtered(
                                    lambda a: a.attribute_id.name == 'Conditionnement'
                                    and a.product_attribute_value_id.name == label
                                )):
                            enlevee += line.product_uom_qty
            rec.quantity_enlevee  = enlevee
            rec.quantity_restante = rec.quantity_tonne - enlevee

    @api.depends(
        'commande_id.planification_ids.line_ids.quantity_tonne',
        'commande_id.planification_ids.state',
    )
    def _compute_quantity_planifiee(self):
        for rec in self:
            planifs = rec.commande_id.planification_ids.filtered(
                lambda p: p.state in ('soumise', 'validee')
            )
            planifiee = sum(
                line.quantity_tonne
                for p in planifs
                for line in p.line_ids
                if line.product_id == rec.product_id
            )
            rec.quantity_planifiee = planifiee

    # ── Helpers ───────────────────────────────────────────────────────────

    def _resoudre_variante(self):
        self.ensure_one()
        if self.product_tmpl_id and self.conditionnement_id:
            label = self.conditionnement_id.name
            variant = self.product_tmpl_id.product_variant_ids.filtered(
                lambda v: any(
                    a.attribute_id.name == 'Conditionnement'
                    and a.product_attribute_value_id.name == label
                    for a in v.product_template_attribute_value_ids
                )
            )
            return variant[0] if variant else False
        return False

    def _get_prix_from_pricelist(self):
        self.ensure_one()
        pricelist = self.commande_id.pricelist_id
        product   = self._resoudre_variante()

        if pricelist and product:
            try:
                results = pricelist._compute_price_rule(
                    product, 1.0,
                    uom=product.uom_id,
                    date=fields.Date.today(),
                    currency=pricelist.currency_id,
                )
                price = results.get(product.id, (0.0,))[0]
                if price:
                    return price
            except Exception:
                pass

        return self.product_tmpl_id.list_price if self.product_tmpl_id else 0.0

    # ── Onchanges ─────────────────────────────────────────────────────────

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        self.conditionnement_id = False
        self.prix_unitaire      = 0.0
        if self.product_tmpl_id:
            valeur_ids = self.product_tmpl_id.attribute_line_ids.filtered(
                lambda l: l.attribute_id.name == 'Conditionnement'
            ).value_ids.ids
            return {
                'domain': {
                    'conditionnement_id': [('id', 'in', valeur_ids)]
                }
            }

    @api.onchange('conditionnement_id')
    def _onchange_conditionnement_id(self):
        if self.product_tmpl_id and self.conditionnement_id:
            self.prix_unitaire = self._get_prix_from_pricelist()


class GicaCommandeGlobale(models.Model):
    _name        = 'gica.commande.globale'
    _description = 'Commande Globale GICA'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_commande desc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Numero',
        readonly=True, copy=False,
        default='Nouveau', tracking=True,
    )

    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        domain="[('is_gica_client', '=', True)]",
    )

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
        store=True, readonly=True,
    )

    state = fields.Selection([
        ('nouveau',  'Nouveau'),
        ('en_cours', 'En cours'),
        ('cloturee', 'Cloturee'),
        ('annulee',  'Annulee'),
        ('expire',   'Expire'),
    ], string='Statut', default='nouveau', tracking=True, required=True)

    line_ids = fields.One2many(
        'gica.commande.globale.line', 'commande_id',
        string='Lignes produits',
    )

    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        string='Produits disponibles',
    )

    product_tmpl_contrat_ids = fields.Many2many(
        'product.template',
        compute='_compute_product_tmpl_contrat_ids',
        string='Produits du contrat',
    )

    @api.depends('contrat_id.line_ids.product_tmpl_id')
    def _compute_product_tmpl_contrat_ids(self):
        for rec in self:
            rec.product_tmpl_contrat_ids = (
                rec.contrat_id.line_ids.mapped('product_tmpl_id')
                if rec.contrat_id else False
            )

    @api.depends('line_ids.product_id')
    def _compute_product_ids(self):
        for rec in self:
            rec.product_ids = rec.line_ids.mapped('product_id')

    planification_ids = fields.One2many(
        'gica.planification.client', 'commande_globale_id',
        string='Planifications',
    )
    planification_count = fields.Integer(
        compute='_compute_planification_count',
        string='Nb Planifications',
    )
    planification_en_attente_count = fields.Integer(
        compute='_compute_planification_count',
        string='En attente',
    )

    bon_commande_ids = fields.One2many(
        'sale.order', 'commande_globale_id',
        string='Bons de Commande',
    )
    bon_commande_count = fields.Integer(
        compute='_compute_bon_commande_count',
        string='Nb BC',
    )

    avenant_ids = fields.One2many(
        'gica.avenant', 'commande_globale_id',
        string='Avenants',
    )
    avenant_count = fields.Integer(
        compute='_compute_avenant_count',
        string='Nb Avenants',
    )

    montant_total        = fields.Float(compute='_compute_totaux', store=True)
    quantity_total_tonne = fields.Float(compute='_compute_totaux', store=True)
    quantity_enlevee     = fields.Float(compute='_compute_totaux', store=True)
    quantity_restante    = fields.Float(compute='_compute_totaux', store=True)
    quantity_planifiee   = fields.Float(compute='_compute_totaux', store=True)
    taux_realisation     = fields.Float(compute='_compute_totaux', store=True)

    mode_paiement     = fields.Selection(related='contrat_id.mode_paiement',     readonly=True)
    modalite_paiement = fields.Selection(related='contrat_id.modalite_paiement', readonly=True)
    devise            = fields.Char(default='DZD', readonly=True)

    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Liste de prix',
        tracking=True,
    )

    observations = fields.Text(string='Observations')

    # ── Computes ──────────────────────────────────────────────────────────

    @api.depends('planification_ids', 'planification_ids.state')
    def _compute_planification_count(self):
        for rec in self:
            rec.planification_count = len(rec.planification_ids)
            rec.planification_en_attente_count = len(
                rec.planification_ids.filtered(lambda p: p.state == 'soumise')
            )

    @api.depends('bon_commande_ids')
    def _compute_bon_commande_count(self):
        for rec in self:
            rec.bon_commande_count = len(rec.bon_commande_ids)

    @api.depends('avenant_ids')
    def _compute_avenant_count(self):
        for rec in self:
            rec.avenant_count = len(rec.avenant_ids)

    @api.depends(
        'line_ids.montant_total',
        'line_ids.quantity_tonne',
        'line_ids.quantity_enlevee',
        'line_ids.quantity_planifiee',
    )
    def _compute_totaux(self):
        for rec in self:
            rec.montant_total        = sum(rec.line_ids.mapped('montant_total'))
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))
            rec.quantity_enlevee     = sum(rec.line_ids.mapped('quantity_enlevee'))
            rec.quantity_restante    = sum(rec.line_ids.mapped('quantity_restante'))
            rec.quantity_planifiee   = sum(rec.line_ids.mapped('quantity_planifiee'))
            rec.taux_realisation     = (
                (rec.quantity_enlevee / rec.quantity_total_tonne * 100)
                if rec.quantity_total_tonne else 0.0
            )
            # ── Clôture automatique quand toute la quantité est enlevée ──
            if (rec.state == 'en_cours'
                    and rec.quantity_total_tonne > 0
                    and rec.quantity_enlevee >= rec.quantity_total_tonne):
                rec.state = 'cloturee'
                rec.message_post(body='BCG clôturé automatiquement — toute la quantité a été enlevée.')

    # ── Create / Unlink ───────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.commande.globale'
                ) or 'Nouveau'
        records = super().create(vals_list)
        records.mapped('contrat_id').invalidate_recordset(['commande_globale_id'])
        return records

    def unlink(self):
        contrat_ids = self.mapped('contrat_id')
        res = super().unlink()
        contrat_ids.invalidate_recordset(['commande_globale_id'])
        return res

    # ── Onchanges ─────────────────────────────────────────────────────────

    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.contrat_id = False
        # ── Remplissage automatique du contrat ──
        # Si le client a un seul contrat actif → remplir automatiquement
        # Si plusieurs → laisser l'utilisateur choisir
        if self.client_id:
            contrats = self.env['gica.client.contract'].search([
                ('client_id', '=', self.client_id.id),
                ('state', 'in', ['actif', 'en_cours']),
            ])
            if len(contrats) == 1:
                self.contrat_id = contrats[0]

    @api.onchange('contrat_id')
    def _onchange_contrat_id(self):
        """
        Copie uniquement produit + quantité depuis le contrat.
        Le conditionnement et le prix sont saisis sur le BCG.
        Les lignes ne sont pas modifiables après (readonly si state != nouveau).
        """
        if not self.contrat_id:
            return
        self.line_ids = [
            (0, 0, {
                'product_tmpl_id':    line.product_tmpl_id.id,
                'conditionnement_id': False,
                'quantity_tonne':     line.quantity_tonne,
                'prix_unitaire':      0.0,
            })
            for line in self.contrat_id.line_ids
        ]

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        for line in self.line_ids:
            if not line.product_tmpl_id or not line.conditionnement_id:
                continue
            product = line._resoudre_variante()
            if not product:
                continue
            if self.pricelist_id:
                try:
                    results = self.pricelist_id._compute_price_rule(
                        product, 1.0,
                        uom=product.uom_id,
                        date=fields.Date.today(),
                        currency=self.pricelist_id.currency_id,
                    )
                    prix = results.get(product.id, (0.0,))[0] or 0.0
                except Exception:
                    prix = product.product_tmpl_id.list_price
                line.prix_unitaire = prix
            else:
                line.prix_unitaire = product.product_tmpl_id.list_price

    # ── Actions ───────────────────────────────────────────────────────────

    def action_demarrer(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('La commande globale doit avoir au moins une ligne.')
            # Vérifier que toutes les lignes ont un conditionnement
            for line in rec.line_ids:
                if not line.conditionnement_id:
                    raise ValidationError(
                        f'Le produit "{line.product_tmpl_id.name}" n\'a pas de conditionnement.'
                    )
            rec.write({'state': 'en_cours'})

    def action_annuler(self):
        for rec in self:
            if rec.state == 'cloturee':
                raise ValidationError("Impossible d'annuler une commande cloturee.")
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
                rec.message_post(body='BCG clôturé — toute la quantité a été enlevée.')

    def action_voir_bons_commande(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Commande',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain':    [('commande_globale_id', '=', self.id)],
            'context':   {
                'default_commande_globale_id': self.id,
                'default_partner_id': self.client_id.id if self.client_id else False,
            },
        }

    def action_voir_planifications(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Planifications',
            'res_model': 'gica.planification.client',
            'view_mode': 'list,form',
            'domain':    [('commande_globale_id', '=', self.id)],
            'context':   {'default_commande_globale_id': self.id},
        }

    def action_voir_avenants(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Avenants',
            'res_model': 'gica.avenant',
            'view_mode': 'list,form',
            'domain':    [('commande_globale_id', '=', self.id)],
            'context':   {'default_commande_globale_id': self.id},
        }

    # ── Contraintes ───────────────────────────────────────────────────────

    @api.constrains('contrat_id', 'client_id')
    def _check_contrat_client(self):
        for rec in self:
            if rec.contrat_id and rec.contrat_id.client_id != rec.client_id:
                raise ValidationError('Le contrat ne correspond pas a ce client.')

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
                    f'Le contrat {rec.contrat_id.name} a deja une commande '
                    f'globale active : {existing[0].name}.'
                )

    @api.constrains('client_id', 'contrat_id')
    def _check_blocages_metier(self):
        today = fields.Date.today()
        for rec in self:
            agrement = rec.client_id.agrement_actif_id
            if agrement and agrement.date_expiration < today:
                raise ValidationError(
                    f'Agrement expire le {agrement.date_expiration} pour '
                    f'{rec.client_id.display_name}.\n'
                    f'Renouvelez l\'agrement avant de creer un BCG.'
                )
            if rec.contrat_id and rec.contrat_id.date_end < today:
                raise ValidationError(
                    f'Le contrat {rec.contrat_id.name} a expire le '
                    f'{rec.contrat_id.date_end}.\n'
                    f'Creez un avenant ou un nouveau contrat.'
                )
            if rec.contrat_id:
                bcg_actifs = self.search([
                    ('contrat_id', '=', rec.contrat_id.id),
                    ('state', 'not in', ['annulee', 'cloturee']),
                    ('id', '!=', rec.id),
                ])
                qty_utilisee = sum(bcg_actifs.mapped('quantity_total_tonne'))
                qty_contrat  = rec.contrat_id.quantity_total_tonne
                if qty_utilisee >= qty_contrat:
                    raise ValidationError(
                        f'La quantite du contrat {rec.contrat_id.name} est epuisee '
                        f'({qty_contrat:.0f} T).\n'
                        f'Creez un avenant pour ajouter de la quantite.'
                    )

    # ── Cron ──────────────────────────────────────────────────────────────

    @api.model
    def _cron_check_expiration(self):
        today = fields.Date.today()
        expired = self.search([
            ('state', 'in', ['nouveau', 'en_cours']),
            ('date_expiration', '<', today),
        ])
        if expired:
            expired.write({'state': 'expire'})
            for rec in expired:
                rec.message_post(
                    body=f"BCG expiré automatiquement le {today}."
                )


# ── Suppression du préfixe "Conditionnement: " dans l'affichage ──────────
class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name