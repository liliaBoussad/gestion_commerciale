# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class GicaPlanificationClientLine(models.Model):
    _name        = 'gica.planification.client.line'
    _description = 'Ligne Planification Client GICA'
    _order       = 'date_enlevement, sequence, id'
    _rec_name    = 'display_name_cal'

    display_name_cal = fields.Char(
        string='Nom',
        compute='_compute_display_name_cal',
        store=True,
    )

    @api.depends('client_id', 'product_id', 'quantity_tonne')
    def _compute_display_name_cal(self):
        for rec in self:
            client  = rec.client_id.display_name if rec.client_id else '-'
            produit = rec.product_id.name if rec.product_id else '-'
            rec.display_name_cal = f'{client} - {produit} ({rec.quantity_tonne:.0f}T)'

    sequence = fields.Integer(default=10)

    planification_id = fields.Many2one(
        'gica.planification.client',
        string='Planification',
        required=True,
        ondelete='cascade',
    )

    state = fields.Selection([
        ('en_attente', 'En attente'),
        ('validee',    'Validee'),
        ('refusee',    'Refusee'),
    ], string='Etat', default='en_attente')

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit',
        required=True,
        domain="[('id', 'in', parent.product_tmpl_ids)]",
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

    date_enlevement = fields.Date(
        string="Date d'enlèvement",
        required=True,
    )

    nbr_paquets    = fields.Integer(string='Nombre de Paquets')
    quantity_tonne = fields.Float(string='Quantité (T)', required=True)
    rotation       = fields.Integer(string='Rotations (nb camions)', required=True, default=1)
    motif_refus = fields.Text(string='Motif du refus', tracking=True)

    quantity_disponible = fields.Float(
        string='Qte restante BCG (T)',
        compute='_compute_quantity_disponible',
        store=True,
    )

    prix_unitaire = fields.Float(
        string='Prix unitaire (DA)',
        compute='_compute_prix_unitaire',
        store=True,
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Bon de Commande',
        readonly=True,
    )
    motif_refus = fields.Text(string='Motif du refus', readonly=True)


    bon_circulation_count = fields.Integer(
        string='Nb BCs',
        compute='_compute_bon_circulation_count',
    )

    @api.depends('sale_order_id.bon_circulation_ids')
    def _compute_bon_circulation_count(self):
        for rec in self:
            rec.bon_circulation_count = (
                len(rec.sale_order_id.bon_circulation_ids)
                if rec.sale_order_id else 0
            )

    client_id = fields.Many2one(
        'res.partner',
        related='planification_id.client_id',
        string='Client',
        store=True,
        readonly=True,
    )
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        related='planification_id.commande_globale_id',
        string='BCG',
        store=True,
        readonly=True,
    )
    planification_usine_id = fields.Many2one(
        'gica.planification.usine',
        related='planification_id.planification_usine_id',
        string='Planification Usine',
        store=True,
        readonly=True,
    )
    planification_state = fields.Selection(
        related='planification_id.state',
        string='Etat planification',
        store=True,
        readonly=True,
    )

    bcg_line_ids = fields.Many2many(
        'gica.commande.globale.line',
        compute='_compute_bcg_line_ids',
    )
    bcg_line_id = fields.Many2one(
        'gica.commande.globale.line',
        string='Ligne BCG',
        domain="[('id', 'in', bcg_line_ids)]",
    )

    @api.depends('planification_id.commande_globale_id', 'product_tmpl_id')
    def _compute_bcg_line_ids(self):
        for rec in self:
            bcg = rec.planification_id.commande_globale_id
            if bcg and rec.product_tmpl_id:
                rec.bcg_line_ids = bcg.line_ids.filtered(
                    lambda l: l.product_tmpl_id == rec.product_tmpl_id
                )
            else:
                rec.bcg_line_ids = False

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

    @api.depends(
        'planification_id.commande_globale_id',
        'product_tmpl_id',
        'conditionnement_id',
    )
    def _compute_prix_unitaire(self):
        for rec in self:
            prix = 0.0
            bcg  = rec.planification_id.commande_globale_id
            if bcg and rec.product_tmpl_id and rec.conditionnement_id:
                line = bcg.line_ids.filtered(
                    lambda l: l.product_tmpl_id == rec.product_tmpl_id
                    and l.conditionnement_id == rec.conditionnement_id
                )
                if line:
                    prix = line[0].prix_unitaire
            rec.prix_unitaire = prix

    @api.depends(
        'planification_id.commande_globale_id',
        'planification_id.commande_globale_id.line_ids',
        'product_tmpl_id',
        'conditionnement_id',
    )
    def _compute_quantity_disponible(self):
        for rec in self:
            disponible = 0.0
            bcg        = rec.planification_id.commande_globale_id
            if bcg and rec.product_tmpl_id and rec.conditionnement_id:
                line = bcg.line_ids.filtered(
                    lambda l: l.product_tmpl_id == rec.product_tmpl_id
                    and l.conditionnement_id == rec.conditionnement_id
                )
                if line:
                    disponible = line[0].quantity_restante
            rec.quantity_disponible = disponible

    # ── Onchanges ─────────────────────────────────────────────────────────

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        self.bcg_line_id        = False
        self.conditionnement_id = False
        if self.product_tmpl_id and self.planification_id.commande_globale_id:
            bcg    = self.planification_id.commande_globale_id
            lignes = bcg.line_ids.filtered(
                lambda l: l.product_tmpl_id == self.product_tmpl_id
            )
            valeur_ids = lignes.mapped('conditionnement_id').ids
            if len(lignes) == 1:
                self.bcg_line_id        = lignes[0]
                self.conditionnement_id = lignes[0].conditionnement_id
            return {
                'domain': {
                    'conditionnement_id': [('id', 'in', valeur_ids)]
                }
            }

    @api.onchange('bcg_line_id')
    def _onchange_bcg_line_id(self):
        if self.bcg_line_id:
            self.conditionnement_id = self.bcg_line_id.conditionnement_id

    @api.onchange('conditionnement_id')
    def _onchange_conditionnement_id(self):
        if self.conditionnement_id and self.planification_id.commande_globale_id:
            bcg  = self.planification_id.commande_globale_id
            line = bcg.line_ids.filtered(
                lambda l: l.product_tmpl_id == self.product_tmpl_id
                and l.conditionnement_id == self.conditionnement_id
            )
            self.bcg_line_id = line[0] if line else False

    # ── Contraintes ───────────────────────────────────────────────────────

    @api.constrains('product_tmpl_id', 'conditionnement_id', 'planification_id')
    def _check_produit_dans_bcg(self):
        for rec in self:
            bcg = rec.planification_id.commande_globale_id
            if not bcg:
                continue
            if not bcg.line_ids.filtered(
                lambda l: l.product_tmpl_id == rec.product_tmpl_id
                and l.conditionnement_id == rec.conditionnement_id
            ):
                cond = rec.conditionnement_id.name if rec.conditionnement_id else '-'
                raise ValidationError(
                    f'Le produit "{rec.product_tmpl_id.name} - {cond}" '
                    f'n\'existe pas dans le BCG {bcg.name}.'
                )

    @api.constrains('quantity_tonne', 'product_tmpl_id', 'conditionnement_id', 'planification_id')
    def _check_quantite_disponible(self):
        for rec in self:
            if rec.quantity_tonne <= 0:
                raise ValidationError('La quantite doit etre superieure a 0.')
            bcg = rec.planification_id.commande_globale_id
            if not bcg or not rec.product_tmpl_id:
                continue
            line = bcg.line_ids.filtered(
                lambda l: l.product_tmpl_id == rec.product_tmpl_id
                and l.conditionnement_id == rec.conditionnement_id
            )
            if not line:
                continue
            deja_planifiee = sum(
                l.quantity_tonne
                for p in bcg.planification_ids.filtered(
                    lambda p: p.state in ('soumise', 'validee')
                )
                for l in p.line_ids.filtered(
                    lambda l: l.product_tmpl_id == rec.product_tmpl_id
                    and l.conditionnement_id == rec.conditionnement_id
                    and l.id != rec.id
                )
            )
            disponible_reel = line[0].quantity_restante - deja_planifiee
            if rec.quantity_tonne > disponible_reel:
                raise ValidationError(
                    f'Quantite depassee pour {rec.product_tmpl_id.name} :\n'
                    f'  Restant BCG      : {line[0].quantity_restante:.2f} T\n'
                    f'  Deja planifie    : {deja_planifiee:.2f} T\n'
                    f'  Disponible reel  : {disponible_reel:.2f} T\n'
                    f'  Demande          : {rec.quantity_tonne:.2f} T'
                )

    @api.constrains('rotation')
    def _check_rotation(self):
        for rec in self:
            if rec.rotation <= 0:
                raise ValidationError('Le nombre de rotations doit etre superieur a 0.')

    @api.constrains('date_enlevement')
    def _check_date_enlevement(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_enlevement and rec.date_enlevement < today:
                raise ValidationError(
                    'La date d\'enlevement ne peut pas etre dans le passe.'
                )

    @api.constrains('date_enlevement')
    def _check_date_non_verrouillee(self):
        for rec in self:
            if not rec.date_enlevement:
                continue
            periode = self.env['gica.planification.usine'].search([
                ('state',      '=',  'confirmee'),
                ('date_debut', '<=', rec.date_enlevement),
                ('date_fin',   '>=', rec.date_enlevement),
            ], limit=1)
            if periode:
                raise ValidationError(
                    f'La date {rec.date_enlevement} est dans une periode verrouillee '
                    f'({periode.date_debut} - {periode.date_fin}).\n'
                    f'Veuillez choisir une autre date.'
                )

    @api.onchange('date_enlevement')
    def _onchange_date_enlevement(self):
        if not self.date_enlevement:
            return

        bcg = self.planification_id.commande_globale_id
        if bcg and bcg.date_expiration and self.date_enlevement > bcg.date_expiration:
            self.date_enlevement = False
            return {
                'warning': {
                    'title':   'Date hors delai BCG',
                    'message': f'La date d\'enlevement choisie depasse '
                               f'la date d\'expiration du BCG ({bcg.date_expiration}).\n'
                               f'Veuillez choisir une date avant le {bcg.date_expiration}.',
                }
            }

        if self.date_enlevement.weekday() in (4, 5):
            jour = "Vendredi" if self.date_enlevement.weekday() == 4 else "Samedi"
            return {
                'warning': {
                    'title':   'Jour non ouvrable',
                    'message': f'Le {jour} {self.date_enlevement} est un jour de weekend.\n'
                               f'Veuillez choisir une autre date.',
                }
            }

        periode = self.env['gica.planification.usine'].search([
            ('state',      '=',  'confirmee'),
            ('date_debut', '<=', self.date_enlevement),
            ('date_fin',   '>=', self.date_enlevement),
        ], limit=1)
        if periode:
            return {
                'warning': {
                    'title':   'Periode verrouillee',
                    'message': f'La date {self.date_enlevement} est dans une periode verrouillee :\n'
                               f'{periode.name} ({periode.date_debut} - {periode.date_fin})\n'
                               f'Veuillez choisir une autre date.',
                }
            }

    # ── Actions ───────────────────────────────────────────────────────────

    def action_valider_ligne(self):
        for rec in self:
            rec.write({'state': 'validee'})
            rec._generer_bon_commande()
            rec.planification_id._recompute_state()

    def action_refuser_ligne(self):
        """Ouvre le wizard de refus."""
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Motif du refus',
            'res_model': 'gica.refus.ligne.wizard',
            'view_mode': 'form',
            'target':    'new',
            'context':   {'default_ligne_id': self.id},
        }

    def action_refuser_ligne_avec_motif(self, motif):
        """Appelé par le wizard après saisie du motif."""
        self.ensure_one()
        self.write({
            'state':      'refusee',
            'motif_refus': motif,
        })
        self.planification_id.message_post(
            body=f'❌ Ligne refusée — {self.product_id.name} '
                f'({self.date_enlevement}) : {motif}'
        )
        self.planification_id._recompute_state()

    def action_voir_bc(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bon de Commande',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id':    self.sale_order_id.id,
        }

    def action_voir_bons_circulation(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        bc_ids = self.sale_order_id.bon_circulation_ids.ids
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Circulation',
            'res_model': 'gica.bon.circulation',
            'view_mode': 'list,form',
            'domain':    [('id', 'in', bc_ids)],
        }

    def _generer_bon_commande(self):
        """
        Cree 1 BC (sale.order) + N bons de circulation automatiquement.
        N = self.rotation
        quantite par rotation = self.quantity_tonne / self.rotation
        """
        self.ensure_one()
        if self.sale_order_id:
            return

        planif    = self.planification_id
        partner   = planif.client_id
        bcg       = planif.commande_globale_id
        pricelist = bcg.pricelist_id if bcg else False

        order = self.env['sale.order'].with_context(no_recompute=True).create({
            'partner_id':             partner.id if partner else False,
            'pricelist_id':           pricelist.id if pricelist else False,
            'commande_globale_id':    bcg.id if bcg else False,
            'planification_id':       planif.id,
            'date_prevue_enlevement': self.date_enlevement,
            'order_line': [(0, 0, {
                'product_id':      self.product_id.id,
                'product_uom_qty': self.quantity_tonne,
                'price_unit':      self.prix_unitaire,
                'name':            self.product_id.display_name,
            })],
        })
        order.order_line._compute_price_unit()
        self.write({'sale_order_id': order.id})

        nbr_rotations            = max(1, self.rotation)
        quantite_par_rotation    = round(self.quantity_tonne / nbr_rotations, 3)
        nbr_paquets_par_rotation = (self.nbr_paquets // nbr_rotations if self.nbr_paquets else 0)

        for i in range(nbr_rotations):
            qte = (
                round(self.quantity_tonne - quantite_par_rotation * (nbr_rotations - 1), 3)
                if i == nbr_rotations - 1
                else quantite_par_rotation
            )
            self.env['gica.bon.circulation'].create({
                'sale_order_id':         order.id,
                'planification_line_id': self.id,
                'product_id':            self.product_id.id,
                'quantite_prevue':       qte,
                'nbr_paquets':           nbr_paquets_par_rotation,
                'numero_rotation':       i + 1,
            })

        order.message_post(
            body=f'BC genere depuis la planification {planif.name} - '
                 f'{nbr_rotations} rotation(s) de {quantite_par_rotation:.2f} T chacune.'
        )


class GicaPlanificationClient(models.Model):
    _name        = 'gica.planification.client'
    _description = 'Planification Client GICA'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'name desc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Reference',
        readonly=True, copy=False,
        default='Nouveau', tracking=True,
    )

    client_id = fields.Many2one(
        'res.partner', string='Client',
        required=True, tracking=True,
        domain="[('is_gica_client', '=', True)]",
    )

    # Domain filtré : seulement les BCG actifs (pas expiré, pas cloturé, pas annulé)
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale (BCG)',
        required=True, tracking=True,
        domain="[('client_id', '=', client_id), ('state', 'in', ['nouveau', 'en_cours'])]",
    )

    contrat_id = fields.Many2one(
        'gica.client.contract',
        related='commande_globale_id.contrat_id',
        store=True, readonly=True, string='Contrat',
    )

    date_enlevement = fields.Date(
        string="Date min. enlevement",
        compute='_compute_date_enlevement',
        store=True, readonly=True,
    )

    @api.depends('line_ids.date_enlevement')
    def _compute_date_enlevement(self):
        for rec in self:
            dates = list(filter(None, rec.line_ids.mapped('date_enlevement')))
            rec.date_enlevement = min(dates) if dates else False

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('soumise',   'Soumise'),
        ('validee',   'Validee'),
        ('refusee',   'Refusee'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    motif_refus = fields.Text(string='Motif du refus', readonly=True)

    planification_usine_id = fields.Many2one('gica.planification.usine', readonly=True, tracking=True)

    periode_debut = fields.Date(related='planification_usine_id.date_debut', store=True, readonly=True)
    periode_fin   = fields.Date(related='planification_usine_id.date_fin',   store=True, readonly=True)

    line_ids = fields.One2many(
        'gica.planification.client.line', 'planification_id',
        string='Lignes produits',
    )

    planification_line_ids = fields.One2many(
        'gica.planification.client.line', 'planification_usine_id',
        string='Lignes produits (usine)',
    )

    bcg_quantity_restante = fields.Float(
        related='commande_globale_id.quantity_restante',
        string='Dispo BCG (T)', readonly=True, store=True,
    )
    bcg_date_expiration = fields.Date(
        related='commande_globale_id.date_expiration',
        string='Expiration BCG', readonly=True, store=True,
    )

    product_tmpl_ids = fields.Many2many(
        'product.template',
        compute='_compute_product_tmpl_ids',
        string='Produits du BCG',
    )

    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        string='Variantes du BCG',
    )

    @api.depends('commande_globale_id.line_ids.product_tmpl_id')
    def _compute_product_tmpl_ids(self):
        for rec in self:
            rec.product_tmpl_ids = (
                rec.commande_globale_id.line_ids.mapped('product_tmpl_id')
                if rec.commande_globale_id else False
            )

    @api.depends('commande_globale_id.line_ids.product_id')
    def _compute_product_ids(self):
        for rec in self:
            rec.product_ids = (
                rec.commande_globale_id.line_ids.mapped('product_id')
                if rec.commande_globale_id else False
            )

    quantity_total_tonne = fields.Float(
        compute='_compute_totaux', store=True,
        string='Quantite totale (T)',
    )

    observations = fields.Text(string='Observations')

    source = fields.Selection([
        ('portail',    'Portail Client'),
        ('commercial', 'Commercial'),
    ], string='Source', default='commercial', tracking=True)

    @api.depends('line_ids.quantity_tonne')
    def _compute_totaux(self):
        for rec in self:
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))

    # ── Onchanges ─────────────────────────────────────────────────────────

    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.commande_globale_id = False
        self.line_ids            = [(5, 0, 0)]

    @api.onchange('commande_globale_id')
    def _onchange_commande_globale_id(self):
        self.line_ids = [(5, 0, 0)]
        if self.commande_globale_id and not self.client_id:
            self.client_id = self.commande_globale_id.client_id

    # ── Contraintes ───────────────────────────────────────────────────────

    @api.constrains('commande_globale_id')
    def _check_bcg_actif(self):
        """
        Securite DB : bloque toute planification rattachee a un BCG
        cloture, expire ou annule — meme si le domain UI est contourne.
        """
        etats_bloques = {
            'cloturee': 'cloture (toute la quantite a ete enlevee)',
            'expire':   'expire',
            'annulee':  'annule',
        }
        for rec in self:
            if rec.commande_globale_id and rec.commande_globale_id.state in etats_bloques:
                etat = etats_bloques[rec.commande_globale_id.state]
                raise ValidationError(
                    f'Le BCG {rec.commande_globale_id.name} est {etat}.\n'
                    f'Aucune planification ne peut y etre rattachee.\n'
                    f'Creez un nouveau BCG ou un avenant pour continuer.'
                )

    @api.constrains('client_id', 'commande_globale_id')
    def _check_client_bcg(self):
        for rec in self:
            if (rec.commande_globale_id
                    and rec.client_id
                    and rec.commande_globale_id.client_id != rec.client_id):
                raise ValidationError(
                    f'Le BCG {rec.commande_globale_id.name} '
                    f'n\'appartient pas au client {rec.client_id.display_name}.'
                )

    # ── Create ────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('client_id') and vals.get('commande_globale_id'):
                bcg = self.env['gica.commande.globale'].browse(vals['commande_globale_id'])
                vals['client_id'] = bcg.client_id.id
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.planification.client'
                ) or 'Nouveau'
        return super().create(vals_list)

    # ── Actions ───────────────────────────────────────────────────────────

    def _recompute_state(self):
        for rec in self:
            if rec.state not in ('soumise',):
                continue
            lignes = rec.line_ids
            if not lignes:
                continue
            nb_attente = len(lignes.filtered(lambda l: l.state == 'en_attente'))
            nb_refusee = len(lignes.filtered(lambda l: l.state == 'refusee'))
            total      = len(lignes)
            if nb_attente == 0:
                if nb_refusee == total:
                    rec.write({'state': 'refusee'})
                    rec.message_post(body='Toutes les lignes ont ete refusees.')
                    rec._notifier_client_refus(rec.motif_refus or '')
                else:
                    rec.write({'state': 'validee'})
                    rec.message_post(body='Planification traitee - BCs et bons de circulation generes.')
                    rec._notifier_client_validation()

    def action_soumettre(self):
        today = fields.Date.today()
        for rec in self:
            # 1. Verifier l'agrement client
            agrement = rec.client_id.agrement_actif_id
            if agrement and agrement.date_expiration < today:
                raise ValidationError(
                    f'Agrement expire le {agrement.date_expiration}.\n'
                    f'Renouvelez l\'agrement avant de soumettre une planification.'
                )

            bcg = rec.commande_globale_id

            # 2. Verifier le statut du BCG — bloque si cloture, expire ou annule
            if bcg:
                etats_bloques = {
                    'cloturee': 'cloture (toute la quantite contractuelle a ete enlevee)',
                    'expire':   'expire',
                    'annulee':  'annule',
                }
                if bcg.state in etats_bloques:
                    raise ValidationError(
                        f'Impossible de planifier : le BCG {bcg.name} est '
                        f'{etats_bloques[bcg.state]}.\n'
                        f'Creez un nouveau BCG ou un avenant pour continuer.'
                    )

                # 3. Verifier la date d'expiration
                if bcg.date_expiration and bcg.date_expiration < today:
                    raise ValidationError(
                        f'Le BCG {bcg.name} a expire le {bcg.date_expiration}.\n'
                        f'Creez un nouveau BCG pour continuer.'
                    )

                # 4. Verifier la quantite restante
                if bcg.quantity_restante <= 0:
                    raise ValidationError(
                        f'Le BCG {bcg.name} est epuise — quantite restante : 0 T.\n'
                        f'Creez un nouveau BCG ou un avenant contrat.'
                    )

            # 5. Verifier les dates d'enlevement (weekend)
            for line in rec.line_ids:
                if line.date_enlevement and line.date_enlevement.weekday() in (4, 5):
                    jour = "Vendredi" if line.date_enlevement.weekday() == 4 else "Samedi"
                    raise ValidationError(
                        f'La date {line.date_enlevement} est un {jour} (jour non ouvrable).\n'
                        f'Choisissez une date du dimanche au jeudi.'
                    )

            # 6. Verifier presence de lignes
            if not rec.line_ids:
                raise ValidationError('La planification doit contenir au moins une ligne.')
            if not all(l.date_enlevement for l in rec.line_ids):
                raise ValidationError('Toutes les lignes doivent avoir une date d\'enlevement.')

            rec.line_ids.write({'state': 'en_attente'})
            rec.write({'state': 'soumise'})
            rec.message_post(body=f'Planification soumise avec {len(rec.line_ids)} ligne(s).')
            rec._rattacher_planning_usine()

    def _rattacher_planning_usine(self):
        self.ensure_one()
        if self.planification_usine_id:
            return
        planning = self.env['gica.planification.usine'].search([
            ('state',      'in', ['brouillon', 'en_cours']),
            ('date_debut', '<=', self.date_enlevement),
            ('date_fin',   '>=', self.date_enlevement),
        ], limit=1)
        if planning:
            self.write({'planification_usine_id': planning.id})
            planning.write({'state': 'en_cours'})

    def action_valider(self):
        for rec in self:
            lignes_attente = rec.line_ids.filtered(lambda l: l.state == 'en_attente')
            for line in lignes_attente:
                line.action_valider_ligne()

    def action_refuser(self, motif=''):
        for rec in self:
            if motif:
                rec.write({'motif_refus': motif})
            lignes_attente = rec.line_ids.filtered(lambda l: l.state == 'en_attente')
            for line in lignes_attente:
                line.action_refuser_ligne()

    def action_voir_bc(self):
        self.ensure_one()
        bc_ids = self.line_ids.mapped('sale_order_id').ids
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Commande',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain':    [('id', 'in', bc_ids)],
        }

    def action_remettre_brouillon(self):
        for rec in self:
            if rec.state == 'soumise':
                rec.line_ids.write({'state': 'en_attente'})
                rec.write({'state': 'brouillon'})

    def _notifier_client_validation(self):
        self.ensure_one()
        template = self.env.ref(
            'gestion_commerciale.email_template_planification_validee',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)

    def _notifier_client_refus(self, motif):
        self.ensure_one()
        template = self.env.ref(
            'gestion_commerciale.email_template_planification_refusee',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)

    # ── Cron : alerte expiration BCG 7 jours avant ────────────────────────

    @api.model
    def _cron_alerte_expiration_bcg(self):
        """Envoie une alerte 7 jours avant l'expiration du BCG."""
        today   = fields.Date.today()
        dans_7j = today + timedelta(days=7)
        bcgs = self.env['gica.commande.globale'].search([
            ('state', 'in', ['nouveau', 'en_cours']),
            ('date_expiration', '=', dans_7j),
        ])
        for bcg in bcgs:
            bcg.message_post(
                body=(
                    f'Le BCG {bcg.name} expire dans 7 jours le {bcg.date_expiration}. '
                    f'Pensez a creer un avenant ou un nouveau contrat.'
                ),
                message_type='notification',
            )