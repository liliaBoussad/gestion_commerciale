# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaBonCommandeLine(models.Model):
    """
    Ligne du bon de commande.
    Sous-ensemble des lignes de la commande globale.
    La somme des quantités BC ne peut pas dépasser la quantité BCG.
    """
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
        string='Quantité (T)',
        required=True,
    )

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

    # ── Computed ───────────────────────────────────────────────────────────

    @api.depends('bon_commande_id.commande_globale_id', 'product_type', 'conditionnement')
    def _compute_prix_unitaire(self):
        for rec in self:
            prix = 0.0
            if rec.bon_commande_id.commande_globale_id:
                bcg_line = rec.bon_commande_id.commande_globale_id.line_ids.filtered(
                    lambda l: l.product_type == rec.product_type
                    and l.conditionnement == rec.conditionnement
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
                 'product_type', 'conditionnement')
    def _compute_quantity_disponible(self):
        for rec in self:
            disponible = 0.0
            if rec.bon_commande_id.commande_globale_id:
                bcg = rec.bon_commande_id.commande_globale_id
                bcg_line = bcg.line_ids.filtered(
                    lambda l: l.product_type == rec.product_type
                    and l.conditionnement == rec.conditionnement
                )
                if bcg_line:
                    # Quantité totale BCG
                    qty_bcg = bcg_line[0].quantity_tonne
                    # Quantité déjà prise par les autres BC actifs
                    autres_bc = bcg.bon_commande_ids.filtered(
                        lambda bc: bc.id != rec.bon_commande_id.id
                        and bc.state != 'annule'
                    )
                    qty_prise = sum(
                        l.quantity_tonne
                        for bc in autres_bc
                        for l in bc.line_ids
                        if l.product_type == rec.product_type
                        and l.conditionnement == rec.conditionnement
                    )
                    disponible = qty_bcg - qty_prise
            rec.quantity_disponible = disponible

    # ── Contraintes ────────────────────────────────────────────────────────

    @api.constrains('product_type', 'conditionnement', 'bon_commande_id')
    def _check_produit_dans_bcg(self):
        """
        Le produit/conditionnement doit exister dans la commande globale.
        """
        for rec in self:
            bcg = rec.bon_commande_id.commande_globale_id
            if not bcg:
                continue
            bcg_line = bcg.line_ids.filtered(
                lambda l: l.product_type == rec.product_type
                and l.conditionnement == rec.conditionnement
            )
            if not bcg_line:
                raise ValidationError(
                    f'❌ Le produit "{dict(self._fields["product_type"].selection).get(rec.product_type)}" '
                    f'avec le conditionnement "{dict(self._fields["conditionnement"].selection).get(rec.conditionnement)}" '
                    f'n\'existe pas dans la commande globale {bcg.name}.\n\n'
                    f'Veuillez choisir uniquement les produits du contrat.'
                )

    @api.constrains('quantity_tonne', 'product_type', 'conditionnement', 'bon_commande_id')
    def _check_quantite_disponible(self):
        """
        La quantité demandée ne peut pas dépasser la quantité restante dans la BCG.
        """
        for rec in self:
            if rec.quantity_tonne <= 0:
                raise ValidationError(
                    '❌ La quantité doit être supérieure à 0.'
                )
            bcg = rec.bon_commande_id.commande_globale_id
            if not bcg:
                continue
            bcg_line = bcg.line_ids.filtered(
                lambda l: l.product_type == rec.product_type
                and l.conditionnement == rec.conditionnement
            )
            if not bcg_line:
                continue

            qty_bcg = bcg_line[0].quantity_tonne

            # Somme des autres BC actifs (hors ce BC)
            autres_bc = bcg.bon_commande_ids.filtered(
                lambda bc: bc.id != rec.bon_commande_id.id
                and bc.state != 'annule'
            )
            qty_prise = sum(
                l.quantity_tonne
                for bc in autres_bc
                for l in bc.line_ids
                if l.product_type == rec.product_type
                and l.conditionnement == rec.conditionnement
            )

            qty_totale = qty_prise + rec.quantity_tonne

            if qty_totale > qty_bcg:
                produit_label = dict(
                    self._fields['product_type'].selection
                ).get(rec.product_type, rec.product_type)
                cond_label = dict(
                    self._fields['conditionnement'].selection
                ).get(rec.conditionnement, rec.conditionnement)
                raise ValidationError(
                    f'❌ Quantité dépassée pour {produit_label} ({cond_label}) :\n\n'
                    f'  📦 Quantité BCG totale  : {qty_bcg:.2f} T\n'
                    f'  ✅ Déjà commandé        : {qty_prise:.2f} T\n'
                    f'  🛒 Ce bon de commande   : {rec.quantity_tonne:.2f} T\n'
                    f'  ⚠️  Total               : {qty_totale:.2f} T\n\n'
                    f'  👉 Quantité disponible  : {qty_bcg - qty_prise:.2f} T'
                )


class GicaBonCommande(models.Model):
    """
    Bon de Commande GICA.
    Créé par le client depuis une Commande Globale.
    Cycle : Brouillon → En attente → Validé → Enlevé → Annulé
    Numérotation : BC/YYYY/XXXX
    """
    _name = 'gica.bon.commande'
    _description = 'Bon de Commande GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_creation desc'
    _rec_name = 'name'

    # ── Identification ─────────────────────────────────────────────────────
    name = fields.Char(
        string='Numéro BC',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    # ── Liens ──────────────────────────────────────────────────────────────
    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('state', 'in', ['nouveau', 'en_cours'])]",
    )

    client_id = fields.Many2one(
        'gica.client',
        string='Client',
        related='commande_globale_id.client_id',
        store=True,
        readonly=True,
    )

    contrat_id = fields.Many2one(
        'gica.client.contract',
        string='Contrat',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
    )

    # ── Dates ──────────────────────────────────────────────────────────────
    date_creation = fields.Date(
        string='Date de création',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )

    date_prevue_enlevement = fields.Date(
        string="Date prévue d'enlèvement",
        required=True,
        tracking=True,
        help='Date souhaitée par le client. Doit être aujourd\'hui ou dans le futur.',
    )

    date_reelle_enlevement = fields.Date(
        string="Date réelle d'enlèvement",
        readonly=True,
        tracking=True,
    )

    # ── Statut ─────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('brouillon',  'Brouillon'),
        ('en_attente', 'En attente validation'),
        ('valide',     'Validé'),
        ('enleve',     'Enlevé'),
        ('annule',     'Annulé'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    # ── Lignes ─────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'gica.bon.commande.line',
        'bon_commande_id',
        string='Lignes produits',
    )

    # ── Bon de circulation lié ─────────────────────────────────────────────
    bon_circulation_id = fields.Many2one(
        'gica.bon.circulation',
        string='Bon de Circulation',
        readonly=True,
    )

    # ── Totaux ─────────────────────────────────────────────────────────────
    quantity_total_tonne = fields.Float(
        string='Quantité Totale (T)',
        compute='_compute_totaux',
        store=True,
    )

    montant_total = fields.Float(
        string='Montant Total (DA)',
        compute='_compute_totaux',
        store=True,
    )

    observations = fields.Text(string='Observations')

    # ── Computed ───────────────────────────────────────────────────────────

    @api.depends('line_ids.quantity_tonne', 'line_ids.montant_total')
    def _compute_totaux(self):
        for rec in self:
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))
            rec.montant_total        = sum(rec.line_ids.mapped('montant_total'))

    # ── Numérotation ───────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.bon.commande'
                ) or 'Nouveau'
        return super().create(vals_list)

    # ── Contraintes ────────────────────────────────────────────────────────

    @api.constrains('date_prevue_enlevement')
    def _check_date_enlevement(self):
        """
        La date d'enlèvement doit être aujourd'hui ou dans le futur.
        """
        today = fields.Date.today()
        for rec in self:
            if rec.date_prevue_enlevement and rec.date_prevue_enlevement < today:
                raise ValidationError(
                    f'❌ La date d\'enlèvement prévue ({rec.date_prevue_enlevement}) '
                    f'ne peut pas être dans le passé.\n\n'
                    f'👉 Veuillez choisir une date à partir du {today}.'
                )

    @api.constrains('commande_globale_id')
    def _check_commande_globale_active(self):
        for rec in self:
            if rec.commande_globale_id.state not in ('nouveau', 'en_cours'):
                raise ValidationError(
                    '❌ Impossible de créer un BC sur une commande globale '
                    'clôturée ou annulée.'
                )

    # ── Workflow ───────────────────────────────────────────────────────────

    def action_soumettre(self):
        """Brouillon → En attente de validation."""
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('❌ Le BC doit contenir au moins une ligne produit.')
            rec._check_date_enlevement()
            rec.write({'state': 'en_attente'})
            rec.message_post(
                body=f'📋 BC soumis à validation pour enlèvement le {rec.date_prevue_enlevement}.'
            )

    def action_valider(self):
        """En attente → Validé (par la commission)."""
        for rec in self:
            # TODO: vérifier gica.planning.periode (module planification)
            rec.write({'state': 'valide'})
            rec.message_post(
                body=f'✅ BC validé — enlèvement prévu le {rec.date_prevue_enlevement}.'
            )

    def action_marquer_enleve(self):
        """Validé → Enlevé."""
        for rec in self:
            rec.write({
                'state': 'enleve',
                'date_reelle_enlevement': fields.Date.today(),
            })
            rec.commande_globale_id._check_cloture_automatique()
            rec.message_post(
                body=f'📦 Marchandise enlevée le {fields.Date.today()}.'
            )

    def action_annuler(self):
        """Annuler le BC."""
        for rec in self:
            if rec.state == 'enleve':
                raise ValidationError('❌ Impossible d\'annuler un BC déjà enlevé.')
            rec.write({'state': 'annule'})

    def action_remettre_brouillon(self):
        """Remettre en brouillon depuis En attente ou Annulé."""
        for rec in self:
            if rec.state in ('brouillon', 'valide', 'enleve'):
                raise ValidationError(
                    '❌ Impossible de remettre en brouillon depuis cet état.'
                )
            rec.write({'state': 'brouillon'})