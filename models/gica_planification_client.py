# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaPlanificationClientLine(models.Model):
    _name = 'gica.planification.client.line'
    _description = 'Ligne Planification Client GICA'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    planification_id = fields.Many2one(
        'gica.planification.client',
        string='Planification',
        required=True,
        ondelete='cascade',
    )

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

    nbr_paquets = fields.Integer(string='Nombre de Paquets')

    quantity_tonne = fields.Float(
        string='Quantité (T)',
        required=True,
    )

    rotation = fields.Integer(
        string='Rotations (nb camions)',
        required=True,
        default=1,
    )

    quantity_disponible = fields.Float(
        string='Disponible BCG (T)',
        compute='_compute_quantity_disponible',
    )

    prix_unitaire = fields.Float(
        string='Prix unitaire (DA)',
        compute='_compute_prix_unitaire',
        store=True,
    )

    @api.depends('planification_id.commande_globale_id', 'product_id')
    def _compute_prix_unitaire(self):
        for rec in self:
            prix = 0.0
            bcg = rec.planification_id.commande_globale_id
            if bcg and rec.product_id:
                bcg_line = bcg.line_ids.filtered(
                    lambda l: l.product_id == rec.product_id
                )
                if bcg_line:
                    prix = bcg_line[0].prix_unitaire
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
                bcg_line = bcg.line_ids.filtered(
                    lambda l: l.product_id == rec.product_id
                )
                if bcg_line:
                    disponible = bcg_line[0].quantity_restante
            rec.quantity_disponible = disponible

    @api.constrains('product_id', 'planification_id')
    def _check_produit_dans_bcg(self):
        for rec in self:
            bcg = rec.planification_id.commande_globale_id
            if not bcg:
                continue
            bcg_line = bcg.line_ids.filtered(
                lambda l: l.product_id == rec.product_id
            )
            if not bcg_line:
                raise ValidationError(
                    f'❌ Le produit "{rec.product_id.display_name}" '
                    f'n\'existe pas dans le BCG {bcg.name}.\n'
                    f'Veuillez choisir uniquement les produits du contrat.'
                )

    @api.constrains('quantity_tonne', 'product_id', 'planification_id')
    def _check_quantite_disponible(self):
        for rec in self:
            if rec.quantity_tonne <= 0:
                raise ValidationError('❌ La quantité doit être supérieure à 0.')
            bcg = rec.planification_id.commande_globale_id
            if not bcg or not rec.product_id:
                continue
            bcg_line = bcg.line_ids.filtered(
                lambda l: l.product_id == rec.product_id
            )
            if not bcg_line:
                continue
            if rec.quantity_tonne > bcg_line[0].quantity_restante:
                raise ValidationError(
                    f'❌ Quantité dépassée pour {rec.product_id.display_name} :\n'
                    f'  📦 Disponible BCG : {bcg_line[0].quantity_restante:.2f} T\n'
                    f'  🛒 Demandé        : {rec.quantity_tonne:.2f} T'
                )

    @api.constrains('rotation')
    def _check_rotation(self):
        for rec in self:
            if rec.rotation <= 0:
                raise ValidationError('❌ Le nombre de rotations doit être supérieur à 0.')


class GicaPlanificationClient(models.Model):
    _name = 'gica.planification.client'
    _description = 'Planification Client GICA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_enlevement desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    commande_globale_id = fields.Many2one(
        'gica.commande.globale',
        string='Commande Globale (BCG)',
        required=True,
        tracking=True,
        domain="[('state', 'in', ['nouveau', 'en_cours'])]",
    )

    client_id = fields.Many2one(
        'gica.client',
        related='commande_globale_id.client_id',
        store=True,
        readonly=True,
        string='Client',
    )

    contrat_id = fields.Many2one(
        'gica.client.contract',
        related='commande_globale_id.contrat_id',
        store=True,
        readonly=True,
        string='Contrat',
    )

    date_enlevement = fields.Date(
        string="Date d'enlèvement souhaitée",
        required=True,
        tracking=True,
    )

    state = fields.Selection([
        ('brouillon',  'Brouillon'),
        ('soumise',    'Soumise'),
        ('validee',    'Validée'),
        ('refusee',    'Refusée'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    motif_refus = fields.Text(
        string='Motif du refus',
        tracking=True,
    )

    planification_usine_id = fields.Many2one(
        'gica.planification.usine',
        string='Planification Usine',
        readonly=True,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Bon de Commande généré',
        readonly=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        'gica.planification.client.line',
        'planification_id',
        string='Lignes produits',
    )

    quantity_total_tonne = fields.Float(
        compute='_compute_totaux',
        store=True,
        string='Quantité totale (T)',
    )

    observations = fields.Text(string='Observations')

    # Indique si créée depuis le portail ou par le commercial
    source = fields.Selection([
        ('portail',    'Portail Client'),
        ('commercial', 'Commercial'),
    ], string='Source', default='commercial', tracking=True)

    @api.depends('line_ids.quantity_tonne')
    def _compute_totaux(self):
        for rec in self:
            rec.quantity_total_tonne = sum(rec.line_ids.mapped('quantity_tonne'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.planification.client'
                ) or 'Nouveau'
        return super().create(vals_list)

    @api.constrains('date_enlevement')
    def _check_date_enlevement(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_enlevement and rec.date_enlevement < today:
                raise ValidationError(
                    f'❌ La date d\'enlèvement ne peut pas être dans le passé.\n'
                    f'👉 Choisir une date à partir du {today}.'
                )

    @api.constrains('date_enlevement', 'commande_globale_id')
    def _check_date_non_verrouillee(self):
        for rec in self:
            if not rec.date_enlevement:
                continue
            # Vérifier si la date tombe dans une période verrouillée
            periode = self.env['gica.planification.usine'].search([
                ('state', '=', 'confirmee'),
                ('date_debut', '<=', rec.date_enlevement),
                ('date_fin', '>=', rec.date_enlevement),
            ], limit=1)
            if periode:
                raise ValidationError(
                    f'❌ La date {rec.date_enlevement} est dans une période '
                    f'verrouillée ({periode.date_debut} → {periode.date_fin}).\n'
                    f'👉 Veuillez choisir une autre date.'
                )

    def action_soumettre(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('❌ La planification doit contenir au moins une ligne.')
            rec.write({'state': 'soumise'})
            rec.message_post(
                body=f'📋 Planification soumise pour le {rec.date_enlevement}.'
            )

    def action_valider(self):
        """Appelé par la commission depuis la planification usine"""
        for rec in self:
            rec.write({'state': 'validee'})
            # Générer automatiquement le BC (sale.order)
            rec._generer_bon_commande()
            rec.message_post(
                body=f'✅ Planification validée — BC généré : {rec.sale_order_id.name}'
            )
            # Notifier le client
            rec._notifier_client_validation()

    def action_refuser(self, motif=''):
        """Appelé par la commission depuis la planification usine"""
        for rec in self:
            rec.write({
                'state': 'refusee',
                'motif_refus': motif or 'Refusé par la commission.',
            })
            rec.message_post(
                body=f'❌ Planification refusée. Motif : {rec.motif_refus}'
            )
            rec._notifier_client_refus(rec.motif_refus)

    def action_voir_bc(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bon de Commande',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def action_remettre_brouillon(self):
        for rec in self:
            if rec.state == 'soumise':
                rec.write({'state': 'brouillon'})

    def _generer_bon_commande(self):
        """Génère automatiquement un sale.order depuis la planification validée"""
        self.ensure_one()
        if self.sale_order_id:
            return  # BC déjà généré

        # Récupérer le partenaire Odoo du client GICA
        partner = self.client_id.partner_id if hasattr(self.client_id, 'partner_id') else False

        order_vals = {
            'partner_id': partner.id if partner else False,
            'commande_globale_id': self.commande_globale_id.id,
            'planification_id': self.id,
            'date_prevue_enlevement': self.date_enlevement,
            'order_line': [],
        }

        for line in self.line_ids:
            order_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity_tonne,
                'price_unit': line.prix_unitaire,
                'name': line.product_id.display_name,
            }))

        order = self.env['sale.order'].create(order_vals)
        self.write({'sale_order_id': order.id})

        # ── Bons de Circulation — activés en Phase 2 ─────────────────────
        # for line in self.line_ids:
        #     for i in range(line.rotation):
        #         self.env['gica.bon.circulation'].create({
        #             'sale_order_id': order.id,
        #             'planification_line_id': line.id,
        #             'product_id': line.product_id.id,
        #             'quantite_prevue': line.quantity_tonne / line.rotation,
        #             'nbr_paquets': line.nbr_paquets,
        #             'numero_rotation': i + 1,
        #         })

    def _notifier_client_validation(self):
        """Envoie notification email + SMS au client"""
        self.ensure_one()
        template = self.env.ref(
            'gestion_commerciale.email_template_planification_validee',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)

    def _notifier_client_refus(self, motif):
        """Envoie notification email + SMS au client avec motif refus"""
        self.ensure_one()
        template = self.env.ref(
            'gestion_commerciale.email_template_planification_refusee',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)