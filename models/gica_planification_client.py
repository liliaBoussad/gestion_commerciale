# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaPlanificationClientLine(models.Model):
    _name = 'gica.planification.client.line'
    _description = 'Ligne Planification Client GICA'
    _order = 'date_enlevement, sequence, id'
    _rec_name = 'display_name_cal'

    display_name_cal = fields.Char(
        string='Nom',
        compute='_compute_display_name_cal',
        store=True,
    )

    @api.depends('client_id', 'product_id', 'quantity_tonne')
    def _compute_display_name_cal(self):
        for rec in self:
            client = rec.client_id.display_name if rec.client_id else '—'
            produit = rec.product_id.name if rec.product_id else '—'
            rec.display_name_cal = f'{client} — {produit} ({rec.quantity_tonne:.0f}T)'

    sequence = fields.Integer(default=10)

    planification_id = fields.Many2one(
        'gica.planification.client',
        string='Planification',
        required=True,
        ondelete='cascade',
    )

    # ── État de validation par ligne ──────────────────────────────────────
    state = fields.Selection([
        ('en_attente', 'En attente'),
        ('validee',    'Validée'),
        ('refusee',    'Refusée'),
    ], string='État', default='en_attente', tracking=True)

    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        domain="[('product_tmpl_id.is_gica_product', '=', True)]",
    )

    conditionnement = fields.Selection(
        related='product_id.conditionnement_gica',
        string='Conditionnement',
        store=True,
        readonly=True,
    )

    # ── Date enlèvement par ligne ─────────────────────────────────────────
    date_enlevement = fields.Date(
        string="Date d'enlèvement",
        required=True,
    )

    nbr_paquets    = fields.Integer(string='Nombre de Paquets')
    quantity_tonne = fields.Float(string='Quantité (T)', required=True)
    rotation       = fields.Integer(string='Rotations (nb camions)', required=True, default=1)

    quantity_disponible = fields.Float(
        string='Qté restante BCG (T)',
        compute='_compute_quantity_disponible',
        store=True,
    )

    prix_unitaire = fields.Float(
        string='Prix unitaire (DA)',
        compute='_compute_prix_unitaire',
        store=True,
    )

    # ── BC généré par ligne ───────────────────────────────────────────────
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Bon de Commande',
        readonly=True,
    )

    # ── Related pour affichage dans vue usine ─────────────────────────────
    client_id = fields.Many2one(
        'gica.client',
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
        string='État planification',
        store=True,
        readonly=True,
    )

    @api.depends('planification_id.commande_globale_id', 'product_id')
    def _compute_prix_unitaire(self):
        for rec in self:
            prix = 0.0
            bcg = rec.planification_id.commande_globale_id
            if bcg and rec.product_id:
                line = bcg.line_ids.filtered(lambda l: l.product_id == rec.product_id)
                if line:
                    prix = line[0].prix_unitaire
            rec.prix_unitaire = prix

    @api.depends(
        'planification_id.commande_globale_id',
        'planification_id.commande_globale_id.line_ids',
        'product_id',
    )
    def _compute_quantity_disponible(self):
        for rec in self:
            disponible = 0.0
            bcg = rec.planification_id.commande_globale_id
            if bcg and rec.product_id:
                line = bcg.line_ids.filtered(lambda l: l.product_id == rec.product_id)
                if line:
                    disponible = line[0].quantity_restante
            rec.quantity_disponible = disponible

    @api.constrains('product_id', 'planification_id')
    def _check_produit_dans_bcg(self):
        for rec in self:
            bcg = rec.planification_id.commande_globale_id
            if not bcg:
                continue
            if not bcg.line_ids.filtered(lambda l: l.product_id == rec.product_id):
                raise ValidationError(
                    f'❌ Le produit "{rec.product_id.display_name}" '
                    f'n\'existe pas dans le BCG {bcg.name}.'
                )

    @api.constrains('quantity_tonne', 'product_id', 'planification_id')
    def _check_quantite_disponible(self):
        for rec in self:
            if rec.quantity_tonne <= 0:
                raise ValidationError('❌ La quantité doit être supérieure à 0.')
            bcg = rec.planification_id.commande_globale_id
            if not bcg or not rec.product_id:
                continue
            line = bcg.line_ids.filtered(lambda l: l.product_id == rec.product_id)
            if not line:
                continue
            if rec.quantity_tonne > line[0].quantity_restante:
                raise ValidationError(
                    f'❌ Quantité dépassée pour {rec.product_id.display_name} :\n'
                    f'  📦 Disponible BCG : {line[0].quantity_restante:.2f} T\n'
                    f'  🛒 Demandé        : {rec.quantity_tonne:.2f} T'
                )

    @api.constrains('rotation')
    def _check_rotation(self):
        for rec in self:
            if rec.rotation <= 0:
                raise ValidationError('❌ Le nombre de rotations doit être supérieur à 0.')

    @api.constrains('date_enlevement')
    def _check_date_enlevement(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_enlevement and rec.date_enlevement < today:
                raise ValidationError(
                    '❌ La date d\'enlèvement ne peut pas être dans le passé.'
                )

    @api.constrains('date_enlevement')
    def _check_date_non_verrouillee(self):
        for rec in self:
            if not rec.date_enlevement:
                continue
            periode = self.env['gica.planification.usine'].search([
                ('state', '=', 'confirmee'),
                ('date_debut', '<=', rec.date_enlevement),
                ('date_fin',   '>=', rec.date_enlevement),
            ], limit=1)
            if periode:
                raise ValidationError(
                    f'❌ La date {rec.date_enlevement} est dans une période verrouillée '
                    f'({periode.date_debut} → {periode.date_fin}).\n'
                    f'👉 Veuillez choisir une autre date.'
                )

    @api.onchange('date_enlevement')
    def _onchange_date_enlevement(self):
        if not self.date_enlevement:
            return
        # ── Weekend (vendredi=4, samedi=5) ────────────────────────────────
        if self.date_enlevement.weekday() in (4, 5):
            jour = "Vendredi" if self.date_enlevement.weekday() == 4 else "Samedi"
            return {
                'warning': {
                    'title': '⛔ Jour non ouvrable',
                    'message': f'Le {jour} {self.date_enlevement} est un jour de weekend.\n'
                               f'Les enlèvements ne sont pas autorisés le vendredi et samedi.\n'
                               f'👉 Veuillez choisir une autre date.',
                }
            }
        # ── Période verrouillée ───────────────────────────────────────────
        periode = self.env['gica.planification.usine'].search([
            ('state',      '=',  'confirmee'),
            ('date_debut', '<=', self.date_enlevement),
            ('date_fin',   '>=', self.date_enlevement),
        ], limit=1)
        if periode:
            return {
                'warning': {
                    'title': '🔒 Période verrouillée',
                    'message': f'La date {self.date_enlevement} est dans une période verrouillée :\n'
                               f'{periode.name} ({periode.date_debut} → {periode.date_fin})\n'
                               f'👉 Veuillez choisir une autre date.',
                }
            }

    # ── Actions validation/refus par ligne ────────────────────────────────
    def action_valider_ligne(self):
        for rec in self:
            rec.write({'state': 'validee'})
            rec._generer_bon_commande()
            rec.planification_id._recompute_state()

    def action_refuser_ligne(self):
        for rec in self:
            rec.write({'state': 'refusee'})
            rec.planification_id._recompute_state()

    def action_voir_bc(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bon de Commande',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def _generer_bon_commande(self):
        self.ensure_one()
        if self.sale_order_id:
            return
        planif = self.planification_id
        partner = planif.client_id.partner_id if hasattr(planif.client_id, 'partner_id') else False
        order = self.env['sale.order'].create({
            'partner_id': partner.id if partner else False,
            'commande_globale_id': planif.commande_globale_id.id,
            'planification_id': planif.id,
            'date_prevue_enlevement': self.date_enlevement,
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'product_uom_qty': self.quantity_tonne,
                'price_unit': self.prix_unitaire,
                'name': self.product_id.display_name,
            })],
        })
        order.action_confirm()
        self.write({'sale_order_id': order.id})


class GicaPlanificationClient(models.Model):
    _name = 'gica.planification.client'
    _description = 'Planification Client GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    client_id = fields.Many2one(
        'gica.client',
        string='Client',
        required=True,
        tracking=True,
    )

    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale (BCG)',
        required=True,
        tracking=True,
        domain="[('client_id', '=', client_id), ('state', 'in', ['nouveau', 'en_cours'])]",
    )

    contrat_id = fields.Many2one(
        'gica.client.contract',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
        string='Contrat',
    )

    # Date min des lignes
    date_enlevement = fields.Date(
        string="Date min. enlèvement",
        compute='_compute_date_enlevement',
        store=True,
        readonly=True,
    )

    @api.depends('line_ids.date_enlevement')
    def _compute_date_enlevement(self):
        for rec in self:
            dates = list(filter(None, rec.line_ids.mapped('date_enlevement')))
            rec.date_enlevement = min(dates) if dates else False

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('soumise',   'Soumise'),
        ('validee',   'Validée'),
        ('refusee',   'Refusée'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    motif_refus            = fields.Text(string='Motif du refus', tracking=True)
    planification_usine_id = fields.Many2one(
        'gica.planification.usine',
        readonly=True,
        tracking=True,
    )

    # ── Dates de la période usine liée ───────────────────────────────────
    periode_debut = fields.Date(
        related='planification_usine_id.date_debut',
        string='Date début période',
        store=True,
        readonly=True,
    )
    periode_fin = fields.Date(
        related='planification_usine_id.date_fin',
        string='Date fin période',
        store=True,
        readonly=True,
    )

    line_ids = fields.One2many(
        'gica.planification.client.line',
        'planification_id',
        string='Lignes produits',
    )

    # ── One2many vers lignes pour planification usine ─────────────────────
    planification_line_ids = fields.One2many(
        'gica.planification.client.line',
        'planification_usine_id',
        string='Lignes produits (usine)',
    )

    bcg_quantity_restante = fields.Float(
        related='commande_globale_id.quantity_restante',
        string='Dispo BCG (T)',
        readonly=True,
        store=True,
    )
    bcg_date_expiration = fields.Date(
        related='commande_globale_id.date_expiration',
        string='Expiration BCG',
        readonly=True,
        store=True,
    )

    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        string='Produits du BCG',
    )

    @api.depends('commande_globale_id.line_ids.product_id')
    def _compute_product_ids(self):
        for rec in self:
            rec.product_ids = (
                rec.commande_globale_id.line_ids.mapped('product_id')
                if rec.commande_globale_id else False
            )

    quantity_total_tonne = fields.Float(
        compute='_compute_totaux',
        store=True,
        string='Quantité totale (T)',
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

    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.commande_globale_id = False
        self.line_ids = [(5, 0, 0)]

    @api.onchange('commande_globale_id')
    def _onchange_commande_globale_id(self):
        self.line_ids = [(5, 0, 0)]
        if self.commande_globale_id and not self.client_id:
            self.client_id = self.commande_globale_id.client_id

    @api.constrains('client_id', 'commande_globale_id')
    def _check_client_bcg(self):
        for rec in self:
            if (rec.commande_globale_id
                    and rec.client_id
                    and rec.commande_globale_id.client_id != rec.client_id):
                raise ValidationError(
                    f'❌ Le BCG {rec.commande_globale_id.name} '
                    f'n\'appartient pas au client {rec.client_id.display_name}.'
                )

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

    def _recompute_state(self):
        """Recalcule le state de la planification selon l'état des lignes"""
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
                # Toutes les lignes sont traitées
                if nb_refusee == total:
                    # Toutes refusées
                    rec.write({'state': 'refusee'})
                    rec.message_post(body='❌ Toutes les lignes ont été refusées.')
                    rec._notifier_client_refus(rec.motif_refus or '')
                else:
                    # Au moins une validée
                    rec.write({'state': 'validee'})
                    rec.message_post(body='✅ Planification traitée — BCs générés.')
                    rec._notifier_client_validation()

    def action_soumettre(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('❌ La planification doit contenir au moins une ligne.')
            if not all(l.date_enlevement for l in rec.line_ids):
                raise ValidationError('❌ Toutes les lignes doivent avoir une date d\'enlèvement.')
            rec.line_ids.write({'state': 'en_attente'})
            rec.write({'state': 'soumise'})
            rec.message_post(body=f'📋 Planification soumise avec {len(rec.line_ids)} ligne(s).')

    def action_valider(self):
        """Valide toutes les lignes en attente"""
        for rec in self:
            lignes_attente = rec.line_ids.filtered(lambda l: l.state == 'en_attente')
            for line in lignes_attente:
                line.action_valider_ligne()

    def action_refuser(self, motif=''):
        """Refuse toutes les lignes en attente"""
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
            'type': 'ir.actions.act_window',
            'name': 'Bons de Commande',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', bc_ids)],
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