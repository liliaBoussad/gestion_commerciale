# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date
import qrcode
import base64
from io import BytesIO


class GicaBonCirculation(models.Model):
    _name        = 'gica.bon.circulation'
    _description = 'Bon de Circulation GICA'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'name desc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Commande de Vente',
        required=True,
        ondelete='cascade',
        tracking=True,
        readonly=True,
    )
    planification_line_id = fields.Many2one(
        'gica.planification.client.line',
        string='Ligne Planification',
        ondelete='set null',
        readonly=True,
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Bon de Livraison',
        readonly=True,
        tracking=True,
    )

    # Lien vers la facture immediate (mode comptant)
    invoice_id = fields.Many2one(
        'account.move',
        string='Facture',
        readonly=True,
        tracking=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        related='sale_order_id.partner_id',
        string='Client',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        readonly=True,
        tracking=True,
    )
    conditionnement = fields.Char(
        string='Conditionnement',
        compute='_compute_conditionnement',
        store=True,
        readonly=True,
    )

    @api.depends('product_id')
    def _compute_conditionnement(self):
        for rec in self:
            if rec.product_id:
                attr_line = rec.product_id.product_template_attribute_value_ids.filtered(
                    lambda v: v.attribute_id.name == 'Conditionnement'
                )
                rec.conditionnement = attr_line[0].name if attr_line else ''
            else:
                rec.conditionnement = ''

    quantite_prevue = fields.Float(string='Quantite Prevue (T)', readonly=True, tracking=True)
    nbr_paquets     = fields.Integer(string='Nombre de Paquets', readonly=True)
    numero_rotation = fields.Integer(string='N Rotation', readonly=True)
    numero_chaine   = fields.Char(string='N de Chaine', readonly=True, tracking=True)

    chauffeur      = fields.Char(string='Chauffeur',         tracking=True)
    matricule      = fields.Char(string='Matricule',         tracking=True)
    camion         = fields.Char(string='Camion',            tracking=True)
    remorque       = fields.Char(string='Remorque',          tracking=True)
    prestataire    = fields.Char(string='Prestataire',       tracking=True)
    lieu_livraison = fields.Char(string='Lieu de Livraison', tracking=True)
    numero_permis  = fields.Char(string='N Permis',          tracking=True)

    tare_p1       = fields.Float(string='Tare P1 (T)',        tracking=True)
    poids_brut_p2 = fields.Float(string='Poids Brut P2 (T)', tracking=True)
    poids_net     = fields.Float(
        string='Poids Net (T)',
        compute='_compute_poids_net',
        store=True,
        tracking=True,
    )

    ecart_poids = fields.Float(string='Ecart (T)', compute='_compute_ecart_poids', store=True)
    ecart_type  = fields.Selection([
        ('ok',      'Conforme'),
        ('surplus', 'Surplus'),
        ('manque',  'Manque'),
    ], string='Type ecart', compute='_compute_ecart_poids', store=True)

    pesee_ids = fields.One2many('gica.pesee', 'bon_circulation_id', string='Historique pesees', readonly=True)

    @api.depends('poids_net', 'quantite_prevue')
    def _compute_ecart_poids(self):
        for rec in self:
            if rec.poids_net and rec.quantite_prevue:
                ecart = rec.poids_net - rec.quantite_prevue
                rec.ecart_poids = ecart
                if abs(ecart) <= rec.quantite_prevue * 0.02:
                    rec.ecart_type = 'ok'
                elif ecart > 0:
                    rec.ecart_type = 'surplus'
                else:
                    rec.ecart_type = 'manque'
            else:
                rec.ecart_poids = 0.0
                rec.ecart_type  = 'ok'

    qr_code = fields.Binary(string='Code QR', compute='_compute_qr_code', store=True)

    @api.depends('name')
    def _compute_qr_code(self):
        for rec in self:
            if rec.name and rec.name != 'Nouveau':
                qr = qrcode.QRCode(version=1, box_size=6, border=2)
                qr.add_data(rec.name)
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white')
                buf = BytesIO()
                img.save(buf, format='PNG')
                rec.qr_code = base64.b64encode(buf.getvalue())
            else:
                rec.qr_code = False

    state = fields.Selection([
        ('brouillon',     'Brouillon'),
        ('transmis_tare', 'Transmis a la tare'),
        ('pesee_entree',  'Pesee Entree'),
        ('chargement',    'Chargement'),
        ('pesee_sortie',  'Pesee Sortie'),
        ('termine',       'Termine'),
        ('annule',        'Annule'),
    ], string='Etat', default='brouillon', tracking=True, required=True)

    # ── Workflow ──────────────────────────────────────────────────────────

    def action_transmettre_tare(self):
        for rec in self:
            rec.write({'state': 'transmis_tare'})
            rec.message_post(body=f'Bon de circulation {rec.name} transmis a la tare.')

    def action_pesee_entree(self):
        for rec in self:
            if not rec.chauffeur:
                raise ValidationError('Veuillez saisir le nom du chauffeur avant de valider la pesee.')
            if not rec.matricule:
                raise ValidationError('Veuillez saisir le matricule du camion avant de valider la pesee.')
            if not rec.tare_p1 or rec.tare_p1 <= 0:
                raise ValidationError('Veuillez saisir la Tare P1 avant de valider.')
            rec.write({'state': 'pesee_entree'})
            self.env['gica.pesee'].create({
                'bon_circulation_id': rec.id,
                'type_pesee':         'vide',
                'poids':              rec.tare_p1,
                'agent_pesage_id':    self.env.user.id,
                'note':               'Pesee initiale a vide (Tare)',
            })
            rec.message_post(
                body=f'Pesee entree validee - Tare P1 : {rec.tare_p1} T - '
                     f'Chauffeur : {rec.chauffeur} - Matricule : {rec.matricule}'
            )

    def action_chargement(self):
        for rec in self:
            if not rec.tare_p1 or rec.tare_p1 <= 0:
                raise ValidationError('La Tare P1 doit etre saisie et validee avant le chargement.')
            rec.write({'state': 'chargement'})
            rec.message_post(body='Chargement en cours.')

    def action_pesee_sortie(self):
        for rec in self:
            if not rec.poids_brut_p2 or rec.poids_brut_p2 <= 0:
                raise ValidationError('Veuillez saisir le Poids Brut P2 avant de valider.')
            if rec.poids_brut_p2 <= rec.tare_p1:
                raise ValidationError(
                    f'Le Poids Brut P2 ({rec.poids_brut_p2} T) doit etre '
                    f'superieur a la Tare P1 ({rec.tare_p1} T).'
                )
            nb_p2 = self.env['gica.pesee'].search_count([
                ('bon_circulation_id', '=', rec.id),
                ('type_pesee', '=', 'charge'),
            ])
            note = f'Pesee en charge N{nb_p2 + 1}'
            if nb_p2 > 0:
                note += ' (apres correction)'
            rec.write({'state': 'pesee_sortie'})
            self.env['gica.pesee'].create({
                'bon_circulation_id': rec.id,
                'type_pesee':         'charge',
                'poids':              rec.poids_brut_p2,
                'agent_pesage_id':    self.env.user.id,
                'note':               note,
            })
            rec.message_post(body=f'Pesee sortie validee - Poids Brut P2 : {rec.poids_brut_p2} T')

    @api.depends('tare_p1', 'poids_brut_p2')
    def _compute_poids_net(self):
        for rec in self:
            rec.poids_net = max(0.0, rec.poids_brut_p2 - rec.tare_p1)

    def _creer_bon_livraison(self):
        """
        Cree un BL Odoo (stock.picking) automatiquement
        1 pesee terminee = 1 BL
        """
        self.ensure_one()
        if self.picking_id:
            return
        if not self.product_id or not self.poids_net:
            return

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id.company_id', '=', self.env.company.id),
        ], limit=1)

        if not picking_type:
            return

        location_src  = picking_type.default_location_src_id
        location_dest = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)

        if not location_src or not location_dest:
            return

        uom = self.product_id.uom_id

        picking = self.env['stock.picking'].create({
            'partner_id':       self.partner_id.id,
            'picking_type_id':  picking_type.id,
            'location_id':      location_src.id,
            'location_dest_id': location_dest.id,
            'origin':           self.name,
            'sale_id':          self.sale_order_id.id if self.sale_order_id else False,
            'note':             f'BC : {self.name} | Chauffeur : {self.chauffeur or ""} | Matricule : {self.matricule or ""}',
            'move_ids': [(0, 0, {
                'name':             self.product_id.display_name,
                'product_id':       self.product_id.id,
                'product_uom_qty':  self.poids_net,
                'product_uom':      uom.id,
                'location_id':      location_src.id,
                'location_dest_id': location_dest.id,
            })],
        })

        picking.action_confirm()
        picking.action_assign()

        for move_line in picking.move_line_ids:
            move_line.quantity = self.poids_net

        picking.with_context(
            skip_backorder=True,
            immediate_transfer=True,
        ).button_validate()

        self.write({'picking_id': picking.id})
        self.message_post(
            body=f'Bon de Livraison cree : {picking.name} - Quantite : {self.poids_net:.3f} T'
        )

    def _creer_facture_immediate(self):
        """
        Cree une facture immediate apres chaque pesee terminee.
        Utilise uniquement pour le mode de paiement COMPTANT.
        1 rotation terminee = 1 facture basee sur le poids net reel.
        """
        self.ensure_one()
        if self.invoice_id:
            return
        if not self.sale_order_id or not self.poids_net:
            return

        # Recuperer le journal de vente
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not journal:
            return

        # Recuperer le compte produit
        account = (
            self.product_id.property_account_income_id
            or self.product_id.categ_id.property_account_income_categ_id
        )

        if not account:
            return

        # Prix unitaire depuis la ligne du BC de vente
        prix_unit = 0.0
        if self.sale_order_id.order_line:
            prix_unit = self.sale_order_id.order_line[0].price_unit

        invoice = self.env['account.move'].create({
            'move_type':         'out_invoice',
            'partner_id':        self.partner_id.id,
            'journal_id':        journal.id,
            'invoice_origin':    f'{self.sale_order_id.name} / {self.name}',
            'invoice_line_ids': [(0, 0, {
                'product_id':  self.product_id.id,
                'name':        f'{self.product_id.display_name} — Rotation {self.numero_rotation} — {self.name}',
                'quantity':    self.poids_net,
                'price_unit':  prix_unit,
                'account_id':  account.id,
            })],
        })

        self.write({'invoice_id': invoice.id})
        self.message_post(
            body=f'Facture immediate creee : {invoice.name} - '
                 f'Quantite : {self.poids_net:.3f} T - '
                 f'Montant : {invoice.amount_total:.2f} DA'
        )

        # Notifier dans le BC de vente
        if self.sale_order_id:
            self.sale_order_id.message_post(
                body=f'Facture immediate creee pour rotation {self.numero_rotation} : '
                     f'{invoice.name} - {self.poids_net:.3f} T'
            )

    def _notifier_commercial(self):
        """Notifie le commercial via le chatter du bon de commande"""
        self.ensure_one()
        if not self.sale_order_id:
            return
        bcs      = self.sale_order_id.bon_circulation_ids
        total    = len(bcs)
        termines = len(bcs.filtered(lambda b: b.state == 'termine'))

        # Message selon le mode de paiement
        mode = ''
        contrat = self.sale_order_id.commande_globale_id.contrat_id
        if contrat:
            mode = contrat.mode_paiement

        msg = (
            f'Rotation {self.numero_rotation}/{total} terminee — '
            f'Poids net : {self.poids_net:.3f} T | '
            f'BL : {self.picking_id.name if self.picking_id else "N/A"} | '
            f'Rotations terminees : {termines}/{total}'
        )

        if mode == 'comptant' and self.invoice_id:
            msg += f' | Facture : {self.invoice_id.name}'
        elif termines == total and mode == 'terme':
            msg += ' — TOUTES LES ROTATIONS TERMINEES. Vous pouvez generer la facture globale.'

        self.sale_order_id.message_post(body=msg)

    def _finaliser_terminer(self):
        """
        Actions communes apres terminaison :
        1. Date reelle enlevement
        2. Cloture BCG si necessaire
        3. BL automatique
        4. Facture immediate si mode comptant
        5. Notification commercial
        """
        self.ensure_one()

        # 1 + 2
        if self.sale_order_id:
            self.sale_order_id.write({'date_reelle_enlevement': fields.Date.today()})
            if self.sale_order_id.commande_globale_id:
                self.sale_order_id.commande_globale_id._check_cloture_automatique()

        # 3 — BL
        self._creer_bon_livraison()

        # 4 — Facture immediate si comptant
        contrat = self.sale_order_id.commande_globale_id.contrat_id if self.sale_order_id else False
        if contrat and contrat.mode_paiement == 'comptant':
            self._creer_facture_immediate()

        # 5 — Notification
        self._notifier_commercial()

    def action_terminer(self):
        for rec in self:
            if not rec.poids_brut_p2:
                raise ValidationError('Veuillez saisir le Poids Brut P2 avant de terminer.')
            rec.write({'state': 'termine'})
            rec._finaliser_terminer()
            rec.message_post(
                body=f'Termine - Poids Net : {rec.poids_net:.2f} T '
                     f'(P1={rec.tare_p1}T / P2={rec.poids_brut_p2}T)'
            )

    def action_accepter_surplus(self):
        for rec in self:
            rec.env['gica.pesee'].create({
                'bon_circulation_id': rec.id,
                'type_pesee':         'charge',
                'poids':              rec.poids_net,
                'agent_pesage_id':    rec.env.user.id,
            })
            rec.write({'state': 'termine'})
            rec._finaliser_terminer()
            rec.message_post(
                body=f'Surplus accepte - Poids Net : {rec.poids_net:.2f} T '
                     f'(prevu {rec.quantite_prevue:.2f} T, ecart +{rec.ecart_poids:.2f} T)'
            )

    def action_decharger_surplus(self):
        for rec in self:
            rec.write({'state': 'chargement', 'poids_brut_p2': 0.0})
            rec.message_post(body=f'Dechargement du surplus - Ecart : +{rec.ecart_poids:.2f} T. Retour au chargement.')

    def action_recharger_manque(self):
        for rec in self:
            rec.write({'state': 'chargement', 'poids_brut_p2': 0.0})
            rec.message_post(body=f'Rechargement demande - Manque : {abs(rec.ecart_poids):.2f} T. Retour au chargement.')

    def action_accepter_manque(self):
        for rec in self:
            rec.write({'state': 'termine'})
            rec._finaliser_terminer()
            rec.message_post(
                body=f'Quantite partielle acceptee - Poids Net : {rec.poids_net:.2f} T '
                     f'(prevu {rec.quantite_prevue:.2f} T, manque {abs(rec.ecart_poids):.2f} T)'
            )

    def action_annuler(self):
        for rec in self:
            rec.write({'state': 'annule'})
            rec.message_post(body='Bon de circulation annule.')

    def action_voir_bc_from_circ(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bon de Commande',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id':    self.sale_order_id.id,
        }

    def action_voir_bon_livraison(self):
        self.ensure_one()
        if not self.picking_id:
            return
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bon de Livraison',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id':    self.picking_id.id,
        }

    def action_voir_facture(self):
        """Ouvre la facture immediate depuis la bascule"""
        self.ensure_one()
        if not self.invoice_id:
            return
        return {
            'type':      'ir.actions.act_window',
            'name':      'Facture',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id':    self.invoice_id.id,
        }

    def action_imprimer_bon_livraison(self):
        self.ensure_one()
        if not self.picking_id:
            raise ValidationError('Aucun bon de livraison genere pour ce bon de circulation.')
        return self.env.ref('stock.action_report_delivery').report_action(self.picking_id)

    def action_retour_brouillon(self):
        for rec in self:
            rec.write({'state': 'brouillon'})
            rec.message_post(body='Retour en brouillon.')

    def action_retour_transmis(self):
        for rec in self:
            rec.write({'state': 'transmis_tare', 'tare_p1': 0.0})
            rec.message_post(body='Correction - Tare P1 reinitialisee.')

    def action_retour_pesee_entree(self):
        for rec in self:
            rec.write({'state': 'pesee_entree'})
            rec.message_post(body='Retour a la pesee entree.')

    def action_retour_chargement(self):
        for rec in self:
            rec.write({'state': 'chargement', 'poids_brut_p2': 0.0})
            rec.message_post(body='Correction - Poids Brut P2 reinitialise.')

    @api.model_create_multi
    def create(self, vals_list):
        today = date.today()
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('gica.bon.circulation') or 'Nouveau'
            if not vals.get('numero_chaine'):
                seq = self.env['ir.sequence'].next_by_code('gica.bon.circulation.chaine') or '0000'
                vals['numero_chaine'] = f"{today.year}/{today.month:02d}/{today.day:02d}/CIM/{seq}"
        return super().create(vals_list)