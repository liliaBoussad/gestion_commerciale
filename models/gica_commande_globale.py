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

    product_id = fields.Many2one(
        'product.product',
        string='Produit',
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

    quantity_tonne  = fields.Float(string='Quantité (T)', required=True)
    prix_unitaire   = fields.Float(string='Prix unitaire (DA)')

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

    quantity_planifiee = fields.Float(
        string='Qté planifiée (T)',
        compute='_compute_quantity_planifiee',
        store=True,
    )

    @api.depends('quantity_tonne', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantity_tonne * rec.prix_unitaire

    @api.depends(
        'commande_id.bon_commande_ids.order_line.product_uom_qty',
        'commande_id.bon_commande_ids.date_reelle_enlevement',
    )
    def _compute_quantity_enlevee(self):
        for rec in self:
            bc_enleves = rec.commande_id.bon_commande_ids.filtered(
                lambda bc: bc.date_reelle_enlevement
            )
            enlevee = sum(
                line.product_uom_qty
                for bc in bc_enleves
                for line in bc.order_line
                if line.product_id == rec.product_id
            )
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
        'gica.commande.globale.line',
        'commande_id',
        string='Lignes produits',
    )

    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        string='Produits disponibles',
    )

    @api.depends('line_ids.product_id')
    def _compute_product_ids(self):
        for rec in self:
            rec.product_ids = rec.line_ids.mapped('product_id')

    planification_ids = fields.One2many(
        'gica.planification.client',
        'commande_globale_id',
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
        'sale.order',
        'commande_globale_id',
        string='Bons de Commande',
    )
    bon_commande_count = fields.Integer(
        compute='_compute_bon_commande_count',
        string='Nb BC',
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
    observations      = fields.Text(string='Observations')

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

    # ── ORM ───────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.commande.globale'
                ) or 'Nouveau'
        records = super().create(vals_list)
        # Invalide le cache commande_globale_id sur les contrats liés
        # pour que le bouton "Créer BCG" disparaisse immédiatement.
        contrat_ids = records.mapped('contrat_id')
        if contrat_ids:
            contrat_ids.invalidate_recordset(['commande_globale_id'])
        return records

    def unlink(self):
        # Mémorise les contrats avant suppression pour invalider après.
        contrat_ids = self.mapped('contrat_id')
        res = super().unlink()
        # Invalide le cache : le bouton "Créer BCG" réapparaît.
        if contrat_ids:
            contrat_ids.invalidate_recordset(['commande_globale_id'])
        return res

    # ── Onchange ──────────────────────────────────────────────────────────
    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.contrat_id = False

    @api.onchange('contrat_id')
    def _onchange_contrat_id(self):
        if self.contrat_id:
            lines = []
            for line in self.contrat_id.line_ids:
                lines.append((0, 0, {
                    'product_id':     line.product_id.id,
                    'quantity_tonne': line.quantity_tonne,
                    'prix_unitaire':  line.prix_unitaire,
                }))
            self.line_ids = lines

    # ── Actions ───────────────────────────────────────────────────────────
    def action_demarrer(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('La commande globale doit avoir au moins une ligne.')
            rec.write({'state': 'en_cours'})

    def action_annuler(self):
        for rec in self:
            if rec.state == 'cloturee':
                raise ValidationError("Impossible d'annuler une commande clôturée.")
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
                rec.message_post(
                    body='✅ Commande clôturée — toute la quantité a été enlevée.'
                )

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

    # ── Contraintes ───────────────────────────────────────────────────────
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