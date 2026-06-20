# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClinkerPlanning(models.Model):
    _name        = 'clinker.planning'
    _description = 'Planification Clinker'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_chargement, id'

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
        options="{'no_create': True}",
    )

    bcg_id = fields.Many2one(
        'clinker.global.order',
        string='BCG Clinker',
        required=True,
        tracking=True,
        domain="[('client_id', '=', client_id), ('state', '=', 'actif')]",
    )

    code_client = fields.Char(
        related='client_id.ref',
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

    rotation = fields.Integer(
        string='Nombre de rotations (camions)',
        required=True,
        default=1,
        tracking=True,
        help='Nombre de camions prevus pour ce chargement. '
             'Chaque rotation genere 1 bon de circulation.',
    )

    quantite_approuvee = fields.Float(
        string='Quantite Approuvee (T)',
        default=0.0,
        tracking=True,
    )

    quantite_livree = fields.Float(
        string='Quantite Livree (T)',
        default=0.0,
        tracking=True,
    )

    motif_refus = fields.Text(string='Motif de Refus', tracking=True)

    approuve_par = fields.Many2one(
        'res.users',
        string='Approuve par',
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
        ('approuve',  'Approuve'),
        ('refuse',    'Refuse'),
    ], string='Statut', default='brouillon', tracking=True, required=True)

    # ── Onchanges ─────────────────────────────────────────────────────────

    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.bcg_id = False
        if self.client_id:
            bcg = self.env['clinker.global.order'].search([
                ('client_id', '=', self.client_id.id),
                ('state',     '=', 'actif'),
            ], limit=1)
            if bcg:
                self.bcg_id = bcg
            else:
                return {
                    'warning': {
                        'title':   'Aucun BCG actif',
                        'message': 'Ce client n\'a pas de BCG Clinker actif.',
                    }
                }

    @api.onchange('bcg_id')
    def _onchange_bcg_id(self):
        if self.bcg_id and not self.client_id:
            self.client_id = self.bcg_id.client_id

    # ── Contraintes ───────────────────────────────────────────────────────

    @api.constrains('estimation')
    def _check_estimation(self):
        for rec in self:
            if rec.estimation <= 0:
                raise ValidationError('L\'estimation doit etre superieure a 0.')

    @api.constrains('rotation')
    def _check_rotation(self):
        for rec in self:
            if rec.rotation <= 0:
                raise ValidationError('Le nombre de rotations doit etre superieur a 0.')

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
                    f'Quantite depassee :\n'
                    f'  Restant BCG    : {rec.bcg_id.total_restant:.2f} T\n'
                    f'  Total planifie : {total_planifie:.2f} T'
                )

    @api.constrains('date_chargement')
    def _check_date_chargement(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_chargement and rec.date_chargement < today:
                raise ValidationError(
                    'La date de chargement ne peut pas etre dans le passe.'
                )

    # ── Create ────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'clinker.planning'
                ) or 'Nouveau'
        return super().create(vals_list)

    # ── Actions ───────────────────────────────────────────────────────────

    def action_soumettre(self):
        for rec in self:
            if not rec.estimation:
                raise ValidationError('L\'estimation est obligatoire.')
            rec.write({'state': 'soumis'})
            rec.message_post(
                body=f'Planification soumise — {rec.estimation} T '
                     f'({rec.rotation} rotation(s)) le {rec.date_chargement}'
            )

    def action_brouillon(self):
        for rec in self:
            if rec.state == 'soumis':
                rec.write({'state': 'brouillon'})
                rec.message_post(body='Remise en brouillon.')

    def action_resoumettre(self):
        for rec in self:
            if rec.state != 'refuse':
                raise ValidationError(
                    'Seule une planification refusee peut etre resoumise.'
                )
            rec.write({'state': 'soumis', 'motif_refus': False})
            rec.message_post(
                body=f'Planification resoumise apres correction — '
                     f'{rec.estimation} T le {rec.date_chargement}'
            )

    def action_voir_bc_quotidien(self):
        self.ensure_one()
        if not self.bc_quotidien_id:
            return
        return {
            'type':      'ir.actions.act_window',
            'name':      'BC Quotidien',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id':    self.bc_quotidien_id.id,
        }

    # ── Approbation ───────────────────────────────────────────────────────

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
            body=f'Approuve — {quantite_approuvee} T — BC-C : {bc.name} '
                 f'({self.rotation} rotation(s))'
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
        self.message_post(body=f'Refuse — Motif : {motif}')

    def _generer_bc_quotidien(self, quantite):
        self.ensure_one()

        product   = self.bcg_id.line_ids[0].product_id if self.bcg_id.line_ids else False
        prix_unit = self.bcg_id.line_ids[0].prix_unitaire if self.bcg_id.line_ids else 0.0
        if not prix_unit and product:
            prix_unit = product.lst_price

        order = self.env['sale.order'].with_context(no_recompute=True).create({
            'partner_id':             self.client_id.id,
            'bcg_clinker_id':         self.bcg_id.id,
            'clinker_planning_id':    self.id,
            'is_clinker':             True,
            'date_prevue_enlevement': self.date_chargement,
            'order_line': [(0, 0, {
                'product_id':      product.id if product else False,
                'product_uom_qty': quantite,
                'price_unit':      prix_unit,
                'name':            product.display_name if product else 'Clinker',
            })] if product else [],
        })
        order.action_confirm()
        self.write({'bc_quotidien_id': order.id})

        nbr_rotations         = max(1, self.rotation)
        quantite_par_rotation = round(quantite / nbr_rotations, 3)

        for i in range(nbr_rotations):
            qte = (
                round(quantite - quantite_par_rotation * (nbr_rotations - 1), 3)
                if i == nbr_rotations - 1
                else quantite_par_rotation
            )
            self.env['gica.bon.circulation'].create({
                'sale_order_id':         order.id,
                'planification_line_id': False,
                'product_id':            product.id if product else False,
                'quantite_prevue':       qte,
                'nbr_paquets':           0,
                'numero_rotation':       i + 1,
            })

        order.message_post(
            body=f'BC Clinker genere depuis la planification {self.name} — '
                 f'{nbr_rotations} rotation(s) de {quantite_par_rotation:.2f} T chacune.'
        )
        return order