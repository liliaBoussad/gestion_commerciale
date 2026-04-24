# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaCommandeGlobaleLine(models.Model):
    """
    Ligne de la commande globale — reprise automatiquement depuis le contrat.
    Produit + Conditionnement + Quantité + Prix unitaire.
    """
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

    # Repris depuis le contrat
    product_type = fields.Selection([
        ('cem2_al_425n',  'GICA BÉTON — CEM II/A-L 42.5 N'),
        ('cem2_al_425r',  'GICA BÉTON — CEM II/A-L 42.5 R'),
        ('cem1_425n_sr5', 'GICA MOUDHAD — CEM I 42.5 N-LH/SR5 (CRS)'),
        ('cem1_525n_sr5', 'GICA MOUDHAD — CEM I 52.5 N/SR5 (CRS)'),
        ('well_cement_g', 'GICA PÉTROLE — Well Cement Class G (HSR)'),
        ('clinker',       'Clinker'),
    ], string='Produit', required=True)

    conditionnement = fields.Selection([
        ('sac_50kg', 'Sac 50 kg'),
        ('sac_25kg', 'Sac 25 kg'),
        ('vrac',     'Vrac'),
        ('big_bag',  'Big-Bag'),
    ], string='Conditionnement', required=True)

    quantity_tonne = fields.Float(
        string='Quantité (tonnes)',
        required=True,
        help='Quantité totale reprise du contrat.',
    )

    prix_unitaire = fields.Float(string='Prix unitaire (DA)', required=True)

    montant_total = fields.Float(
        string='Montant total (DA)',
        compute='_compute_montant_total',
        store=True,
    )

    # Suivi enlèvements
    quantity_enlevee = fields.Float(
        string='Qté enlevée (T)',
        compute='_compute_quantity_enlevee',
        store=True,
        help='Somme des quantités des bons de commande enlevés.',
    )

    quantity_restante = fields.Float(
        string='Qté restante (T)',
        compute='_compute_quantity_enlevee',
        store=True,
    )

    # ── Computed ───────────────────────────────────────────────────────────

    @api.depends('quantity_tonne', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantity_tonne * rec.prix_unitaire

    @api.depends('commande_id.bon_commande_ids.line_ids.quantity_tonne',
                 'commande_id.bon_commande_ids.state')
    def _compute_quantity_enlevee(self):
        for rec in self:
            # Somme des BC enlevés pour ce produit/conditionnement
            bc_enleves = rec.commande_id.bon_commande_ids.filtered(
                lambda bc: bc.state == 'enleve'
            )
            enlevee = sum(
                line.quantity_tonne
                for bc in bc_enleves
                for line in bc.line_ids
                if line.product_type == rec.product_type
                and line.conditionnement == rec.conditionnement
            )
            rec.quantity_enlevee = enlevee
            rec.quantity_restante = rec.quantity_tonne - enlevee


class GicaCommandeGlobale(models.Model):
    """
    Commande Globale GICA.

    Créée depuis un contrat — reprend exactement les mêmes lignes produits.
    Divisée ensuite en plusieurs Bons de Commande.

    Cycle : Nouveau → En cours → Clôturée → Annulée
    Clôture automatique quand quantité enlevée = quantité totale.
    Numérotation : CG/YYYY/XXXX
    """
    _name = 'gica.commande.globale'
    _description = 'Commande Globale GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_commande desc'
    _rec_name = 'name'

    # ── Identification ─────────────────────────────────────────────────────
    name = fields.Char(
        string='Numéro',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    # ── Client & Contrat ───────────────────────────────────────────────────
    client_id = fields.Many2one(
        'gica.client',
        string='Client',
        required=True,
        tracking=True,
    )

    contrat_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat',
        required=True,
        tracking=True,
        domain="[('client_id', '=', client_id), ('state', 'in', ['actif', 'en_cours'])]",
    )

    # ── Dates ──────────────────────────────────────────────────────────────
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

    # ── Statut ─────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('nouveau',   'Nouveau'),
        ('en_cours',  'En cours'),
        ('cloturee',  'Clôturée'),
        ('annulee',   'Annulée'),
    ], string='Statut', default='nouveau', tracking=True, required=True)

    # ── Lignes produits ────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'gica.commande.globale.line',
        'commande_id',
        string='Lignes produits',
    )

    # ── Bons de commande liés ──────────────────────────────────────────────
    bon_commande_ids = fields.One2many(
        'gica.bon.commande',
        'commande_globale_id',
        string='Bons de Commande',
    )

    bon_commande_count = fields.Integer(
        string='Nombre de BC',
        compute='_compute_bon_commande_count',
    )

    # ── Totaux ─────────────────────────────────────────────────────────────
    montant_total = fields.Float(
        string='Montant Total (DA)',
        compute='_compute_totaux',
        store=True,
    )

    quantity_total_tonne = fields.Float(
        string='Quantité Totale (T)',
        compute='_compute_totaux',
        store=True,
    )

    quantity_enlevee = fields.Float(
        string='Qté Enlevée (T)',
        compute='_compute_totaux',
        store=True,
    )

    quantity_restante = fields.Float(
        string='Qté Restante (T)',
        compute='_compute_totaux',
        store=True,
    )

    taux_realisation = fields.Float(
        string='Taux de réalisation (%)',
        compute='_compute_totaux',
        store=True,
    )

    # Paiement — repris du contrat
    mode_paiement = fields.Selection(
        related='contrat_id.mode_paiement',
        string='Mode de paiement',
        readonly=True,
    )

    modalite_paiement = fields.Selection(
        related='contrat_id.modalite_paiement',
        string='Modalité de paiement',
        readonly=True,
    )

    devise = fields.Char(
        string='Devise',
        default='DZD',
        readonly=True,
    )

    observations = fields.Text(string='Observations')

    # ── Computed ───────────────────────────────────────────────────────────

    @api.depends('bon_commande_ids')
    def _compute_bon_commande_count(self):
        for rec in self:
            rec.bon_commande_count = len(rec.bon_commande_ids)

    @api.depends('line_ids.montant_total', 'line_ids.quantity_tonne',
                 'line_ids.quantity_enlevee')
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

    # ── Numérotation automatique ───────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.commande.globale'
                ) or 'Nouveau'
        return super().create(vals_list)

    # ── Actions workflow ───────────────────────────────────────────────────

    def action_demarrer(self):
        """Nouveau → En cours."""
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(
                    'La commande globale doit avoir au moins une ligne produit.'
                )
            rec.write({'state': 'en_cours'})

    def action_annuler(self):
        """Annuler la commande globale."""
        for rec in self:
            if rec.state == 'cloturee':
                raise ValidationError(
                    'Impossible d\'annuler une commande déjà clôturée.'
                )
            rec.write({'state': 'annulee'})

    def action_remettre_nouveau(self):
        """Remettre en Nouveau depuis Annulée."""
        for rec in self:
            if rec.state == 'annulee':
                rec.write({'state': 'nouveau'})

    def _check_cloture_automatique(self):
        """
        Appelée après chaque enlèvement.
        Clôture automatiquement la commande si toute la quantité est enlevée.
        """
        for rec in self:
            if (rec.state == 'en_cours'
                    and rec.quantity_total_tonne > 0
                    and rec.quantity_restante <= 0):
                rec.write({'state': 'cloturee'})
                rec.message_post(
                    body='✅ Commande globale clôturée automatiquement — '
                         'toute la quantité a été enlevée.'
                )

    # ── Génération depuis le contrat ───────────────────────────────────────

    @api.onchange('contrat_id')
    def _onchange_contrat_id(self):
        """
        Quand le contrat est sélectionné, on reprend automatiquement
        les lignes produits (produit + conditionnement + quantité + prix).
        """
        if self.contrat_id:
            lines = []
            for line in self.contrat_id.line_ids:
                lines.append((0, 0, {
                    'product_type':   line.product_type,
                    'conditionnement': line.conditionnement,
                    'quantity_tonne': line.quantity_tonne,
                    'prix_unitaire':  line.prix_unitaire,
                }))
            self.line_ids = lines

    # ── Smart button BC ────────────────────────────────────────────────────

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

    # ── Contraintes ────────────────────────────────────────────────────────

    @api.constrains('contrat_id', 'client_id')
    def _check_contrat_client(self):
        for rec in self:
            if rec.contrat_id and rec.contrat_id.client_id != rec.client_id:
                raise ValidationError(
                    'Le contrat sélectionné n\'appartient pas à ce client.'
                )

    @api.constrains('contrat_id')
    def _check_one_commande_per_contrat(self):
        """Un contrat ne peut avoir qu'une seule commande globale active."""
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