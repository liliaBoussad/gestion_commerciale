# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClinkerPlanning(models.Model):
    _name        = 'clinker.planning'
    _description = 'Planification Clinker'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_chargement, id'

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    bcg_id = fields.Many2one(
        'clinker.global.order',
        string='BCG Clinker',
        required=True,
        tracking=True,
        domain="[('state', '=', 'actif')]",
    )

    client_id = fields.Many2one(
        related='bcg_id.client_id',
        string='Client',
        store=True,
        readonly=True,
    )

    code_client = fields.Char(
        related='bcg_id.client_id.ref',
        string='Code Client',
        store=True,
        readonly=True,
    )

    date_chargement = fields.Date(
        string='Date de Chargement',
        required=True,
        tracking=True,
    )

    estimation = fields.Float(
        string='Estimation (T)',
        required=True,
        tracking=True,
    )

    quantite_approuvee = fields.Float(
        string='Quantité Approuvée (T)',
        default=0.0,
        tracking=True,
    )

    quantite_livree = fields.Float(
        string='Quantité Livrée (T)',
        default=0.0,
        tracking=True,
    )

    motif_refus = fields.Text(string='Motif de Refus', tracking=True)

    approuve_par = fields.Many2one(
        'res.users',
        string='Approuvé par',
        readonly=True,
        tracking=True,
    )

    date_traitement = fields.Datetime(
        string='Date de Traitement',
        readonly=True,
        tracking=True,
    )

    bc_quotidien_id = fields.Many2one(
        'sale.order',
        string='BC-Quotidien (BC-C)',
        readonly=True,
        tracking=True,
    )

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('soumis',    'Soumis'),
        ('approuve',  'Approuvé'),
        ('refuse',    'Refusé'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    # ── Contraintes ───────────────────────────────────────────────────────
    @api.constrains('estimation')
    def _check_estimation(self):
        for rec in self:
            if rec.estimation <= 0:
                raise ValidationError('❌ L\'estimation doit être supérieure à 0.')

    @api.constrains('estimation', 'bcg_id')
    def _check_quantite_bcg(self):
        for rec in self:
            if not rec.bcg_id:
                continue
            autres = self.search([
                ('bcg_id', '=', rec.bcg_id.id),
                ('state',  'in', ['soumis', 'approuve']),
                ('id',     '!=', rec.id),
            ])
            total_planifie = sum(autres.mapped('estimation')) + rec.estimation
            if total_planifie > rec.bcg_id.total_restant:
                raise ValidationError(
                    f'❌ Quantité dépassée :\n'
                    f'  📦 Restant BCG    : {rec.bcg_id.total_restant:.2f} T\n'
                    f'  🛒 Total planifié : {total_planifie:.2f} T'
                )

    # CORRECTION : date_chargement peut être aujourd'hui
    @api.constrains('date_chargement')
    def _check_date_chargement(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_chargement and rec.date_chargement < today:
                raise ValidationError(
                    '❌ La date de chargement ne peut pas être dans le passé.'
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'clinker.planning'
                ) or 'Nouveau'
        return super().create(vals_list)

    def action_soumettre(self):
        for rec in self:
            if not rec.estimation:
                raise ValidationError('❌ L\'estimation est obligatoire.')
            rec.write({'state': 'soumis'})
            rec.message_post(
                body=f'📋 Planification soumise — {rec.estimation} T le {rec.date_chargement}'
            )

    def action_brouillon(self):
        for rec in self:
            if rec.state == 'soumis':
                rec.write({'state': 'brouillon'})
                rec.message_post(body='↩️ Remise en brouillon.')

    def _approuver(self, quantite_approuvee, user=None):
        self.ensure_one()
        self.write({
            'state':              'approuve',
            'quantite_approuvee': quantite_approuvee,
            'approuve_par':       (user or self.env.user).id,
            'date_traitement':    fields.Datetime.now(),
        })
        bc = self._generer_bc_quotidien(quantite_approuvee)
        self.message_post(
            body=f'✅ Approuvé — {quantite_approuvee} T — BC-C : {bc.name}'
        )
        return bc

    def _refuser(self, motif, user=None):
        self.ensure_one()
        self.write({
            'state':           'refuse',
            'motif_refus':     motif,
            'approuve_par':    (user or self.env.user).id,
            'date_traitement': fields.Datetime.now(),
        })
        self.message_post(body=f'❌ Refusé — Motif : {motif}')

    def _generer_bc_quotidien(self, quantite):
        self.ensure_one()
        product = self.bcg_id.line_ids[0].product_id if self.bcg_id.line_ids else False
        order = self.env['sale.order'].create({
            'partner_id':          self.client_id.id,
            'bcg_clinker_id':      self.bcg_id.id,
            'clinker_planning_id': self.id,
            'is_clinker':          True,
            'order_line': [(0, 0, {
                'product_id':      product.id if product else False,
                'product_uom_qty': quantite,
                'price_unit':      product.lst_price if product else 0.0,
                'name':            product.display_name if product else 'Clinker',
            })] if product else [],
        })
        order.action_confirm()
        self.write({'bc_quotidien_id': order.id})
        return order