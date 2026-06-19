# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClinkerGlobalOrderLine(models.Model):
    _name        = 'clinker.global.order.line'
    _description = 'Ligne BCG Clinker'
    _order       = 'sequence, id'

    sequence = fields.Integer(default=10)

    order_id = fields.Many2one(
        'clinker.global.order',
        string='BCG',
        required=True,
        ondelete='cascade',
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit',
        required=True,
        domain="[('type_ciment', '=', 'clinker')]",
    )

    # Conditionnement auto = Vrac (unique pour clinker)
    product_id = fields.Many2one(
        'product.product',
        string='Variante',
        compute='_compute_product_id',
        store=True,
    )
    conditionnement_label = fields.Char(
        string='Conditionnement',
        compute='_compute_conditionnement_label',
        default='Vrac',
    )

    

    quantite_autorisee = fields.Float(
        string='Quantite Autorisee (T)',
        required=True,
    )

    quantite_restante = fields.Float(
        string='Quantite Restante (T)',
        compute='_compute_quantites',
        store=True,
    )

    quantite_livree = fields.Float(
        string='Quantite Livree (T)',
        default=0.0,
    )

    prix_unitaire = fields.Float(
        string='Prix unitaire (DA)',
        default=0.0,
    )

    montant_total = fields.Float(
        string='Montant total (DA)',
        compute='_compute_montant_total',
        store=True,
    )

    @api.depends('product_tmpl_id')
    def _compute_conditionnement_label(self):
        for rec in self:
            rec.conditionnement_label = 'Vrac'

    @api.depends('product_tmpl_id')
    def _compute_product_id(self):
        """
        Clinker = toujours Vrac.
        On recupere la variante dont le conditionnement = Vrac.
        """
        for rec in self:
            if not rec.product_tmpl_id:
                rec.product_id = False
                continue
            variant = rec.product_tmpl_id.product_variant_ids.filtered(
                lambda v: any(
                    a.attribute_id.name == 'Conditionnement'
                    and a.product_attribute_value_id.name == 'Vrac'
                    for a in v.product_template_attribute_value_ids
                )
            )
            if variant:
                rec.product_id = variant[0]
            else:
                # Si pas d'attribut conditionnement, prendre la premiere variante
                rec.product_id = rec.product_tmpl_id.product_variant_ids[:1] or False

    @api.depends('quantite_autorisee', 'quantite_livree')
    def _compute_quantites(self):
        for rec in self:
            rec.quantite_restante = rec.quantite_autorisee - rec.quantite_livree

    @api.depends('quantite_autorisee', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantite_autorisee * rec.prix_unitaire

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        if self.product_tmpl_id and self.order_id.pricelist_id:
            self.prix_unitaire = self._get_prix_from_pricelist()

    def _get_prix_from_pricelist(self):
        self.ensure_one()
        pricelist = self.order_id.pricelist_id
        product   = self.product_id
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


class ClinkerGlobalOrder(models.Model):
    _name        = 'clinker.global.order'
    _description = 'Bon de Commande Global Clinker'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_commande desc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Reference',
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

    date_commande = fields.Date(
        string='Date de commande',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )

    date_expiration = fields.Date(
        string="Date d'expiration",
        required=True,
        tracking=True,
    )

    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Liste de prix',
        tracking=True,
    )

    motif_refus = fields.Text(
        string='Motif de refus/blocage',
        tracking=True,
    )

    expiration_proche = fields.Boolean(
        string='Expiration proche',
        compute='_compute_expiration_proche',
        store=True,
    )

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('soumis',    'Soumis a la production'),
        ('actif',     'Actif'),
        ('termine',   'Termine'),
        ('bloque',    'Bloque'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    line_ids = fields.One2many(
        'clinker.global.order.line',
        'order_id',
        string='Lignes produits',
    )

    total_autorise = fields.Float(
        string='Total Autorise (T)',
        compute='_compute_totaux',
        store=True,
    )
    total_restant = fields.Float(
        string='Total Restant (T)',
        compute='_compute_totaux',
        store=True,
    )
    total_livre = fields.Float(
        string='Total Livre (T)',
        compute='_compute_totaux',
        store=True,
    )
    montant_total = fields.Float(
        string='Montant total (DA)',
        compute='_compute_totaux',
        store=True,
    )

    planning_ids = fields.One2many(
        'clinker.planning',
        'bcg_id',
        string='Planifications',
    )
    planning_count = fields.Integer(
        compute='_compute_planning_count',
        string='Nb Planifications',
    )

    bc_quotidien_ids = fields.One2many(
        'sale.order',
        'bcg_clinker_id',
        string='Bons de Commande Quotidiens',
    )
    bc_quotidien_count = fields.Integer(
        compute='_compute_bc_quotidien_count',
        string='Nb BC Quotidiens',
    )

    @api.depends('date_expiration', 'state')
    def _compute_expiration_proche(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_expiration and rec.state == 'actif':
                delta = (rec.date_expiration - today).days
                rec.expiration_proche = 0 <= delta <= 30
            else:
                rec.expiration_proche = False

    @api.depends(
        'line_ids.quantite_autorisee',
        'line_ids.quantite_restante',
        'line_ids.quantite_livree',
        'line_ids.montant_total',
    )
    def _compute_totaux(self):
        for rec in self:
            rec.total_autorise = sum(rec.line_ids.mapped('quantite_autorisee'))
            rec.total_livre    = sum(rec.line_ids.mapped('quantite_livree'))
            rec.total_restant  = rec.total_autorise - rec.total_livre
            rec.montant_total  = sum(rec.line_ids.mapped('montant_total'))

    @api.depends('planning_ids')
    def _compute_planning_count(self):
        for rec in self:
            rec.planning_count = len(rec.planning_ids)

    @api.depends('bc_quotidien_ids')
    def _compute_bc_quotidien_count(self):
        for rec in self:
            rec.bc_quotidien_count = len(rec.bc_quotidien_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'clinker.global.order'
                ) or 'Nouveau'
        return super().create(vals_list)

    @api.onchange('client_id')
    def _onchange_client_id(self):
        if not self.client_id:
            return
        bcg_actif = self.search([
            ('client_id', '=', self.client_id.id),
            ('state',     '=', 'actif'),
        ], limit=1)
        if bcg_actif and not self.id:
            return {
                'warning': {
                    'title':   'BCG Actif existant',
                    'message': f'Ce client a deja un BCG Clinker actif : {bcg_actif.name}.',
                }
            }

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        for line in self.line_ids:
            if line.product_tmpl_id:
                line.prix_unitaire = line._get_prix_from_pricelist()

    @api.constrains('date_expiration', 'date_commande')
    def _check_dates(self):
        for rec in self:
            if rec.date_expiration and rec.date_commande:
                if rec.date_expiration <= rec.date_commande:
                    raise ValidationError(
                        'La date d\'expiration doit etre posterieure a la date de commande.'
                    )

    @api.constrains('client_id', 'state')
    def _check_doublon_bcg(self):
        for rec in self:
            if rec.state == 'actif':
                doublon = self.search([
                    ('client_id', '=', rec.client_id.id),
                    ('state',     '=', 'actif'),
                    ('id',        '!=', rec.id),
                ])
                if doublon:
                    raise ValidationError(
                        f'Ce client a deja un BCG Clinker actif : {doublon[0].name}.\n'
                        'Terminez-le avant d\'en activer un nouveau.'
                    )

    @api.constrains('line_ids')
    def _check_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('Le BCG doit contenir au moins une ligne produit.')

    def action_soumettre(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError('Ajoutez au moins une ligne produit.')
            if not rec.date_expiration:
                raise ValidationError('La date d\'expiration est obligatoire.')
            rec.write({'state': 'soumis'})
            rec.message_post(
                body=f'BCG {rec.name} soumis a la production pour validation.'
            )
            rec._notifier_production()

    def action_activer(self):
        for rec in self:
            rec.write({'state': 'actif', 'motif_refus': False})
            rec.message_post(
                body=f'BCG {rec.name} valide par la production — statut Actif.'
            )
            rec._notifier_commercial('actif')

    def action_bloquer(self):
        for rec in self:
            if not rec.motif_refus:
                raise ValidationError(
                    'Le motif de refus/blocage est obligatoire.\n'
                    'Saisissez un motif avant de bloquer.'
                )
            rec.write({'state': 'bloque'})
            rec.message_post(body=f'BCG bloque — Motif : {rec.motif_refus}')
            rec._notifier_commercial('bloque')

    def action_resoumettre(self):
        for rec in self:
            if rec.state != 'bloque':
                raise ValidationError('Seul un BCG bloque peut etre re-soumis.')
            rec.write({'state': 'soumis', 'motif_refus': False})
            rec.message_post(
                body=f'BCG {rec.name} re-soumis a la production apres modification.'
            )
            rec._notifier_production()

    def action_terminer(self):
        for rec in self:
            rec.write({'state': 'termine'})
            rec.message_post(body=f'BCG Clinker {rec.name} termine.')

    def action_brouillon(self):
        for rec in self:
            if rec.state not in ('bloque',):
                raise ValidationError('Seul un BCG bloque peut revenir en brouillon.')
            rec.write({'state': 'brouillon'})

    def action_voir_planifications(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Planifications Clinker',
            'res_model': 'clinker.planning',
            'view_mode': 'list,form',
            'domain':    [('bcg_id', '=', self.id)],
            'context':   {'default_bcg_id': self.id},
        }

    def action_voir_bc_quotidiens(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bons de Commande Quotidiens',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain':    [('bcg_clinker_id', '=', self.id)],
        }

    def _notifier_production(self):
        self.ensure_one()
        self.message_post(
            body=f'BCG {self.name} soumis — en attente de validation production.',
            partner_ids=self._get_responsables_production(),
        )

    def _notifier_commercial(self, etat):
        self.ensure_one()
        if etat == 'actif':
            msg = f'BCG {self.name} active — vous pouvez soumettre des planifications.'
        else:
            msg = f'BCG {self.name} bloque — Motif : {self.motif_refus}'
        self.message_post(body=msg)

    def _get_responsables_production(self):
        groupe = self.env.ref('base.group_system', raise_if_not_found=False)
        if groupe:
            return groupe.users.mapped('partner_id').ids
        return []

    @api.model
    def _cron_check_expiration(self):
        today = fields.Date.today()
        expired = self.search([
            ('state',           '=', 'actif'),
            ('date_expiration', '<', today),
        ])
        if expired:
            expired.write({'state': 'termine'})
            for rec in expired:
                rec.message_post(
                    body=f'BCG Clinker expire automatiquement le {today}.'
                )

    def _check_cloture_automatique(self):
        for rec in self:
            rec.invalidate_recordset(['total_livre', 'total_restant', 'total_autorise'])
            if rec.state == 'actif' and rec.total_autorise > 0 and rec.total_restant <= 0:
                rec.write({'state': 'termine'})
                rec.message_post(
                    body=(
                        f'BCG Clinker cloture automatiquement : toute la quantite '
                        f'({rec.total_autorise:.0f} T) a ete livree.'
                    )
                )