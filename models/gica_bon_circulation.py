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

    # Liens
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

    # Infos commande (related)
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

    quantite_prevue = fields.Float(
        string='Quantite Prevue (T)',
        readonly=True,
        tracking=True,
    )
    nbr_paquets = fields.Integer(
        string='Nombre de Paquets',
        readonly=True,
    )
    numero_rotation = fields.Integer(
        string='N Rotation',
        readonly=True,
    )

    # N de Chaine
    numero_chaine = fields.Char(
        string='N de Chaine',
        readonly=True,
        tracking=True,
    )

    # Logistique et Camion
    # Saisis par l'agent bascule quand le camion arrive physiquement
    chauffeur      = fields.Char(string='Chauffeur',         tracking=True)
    matricule      = fields.Char(string='Matricule',         tracking=True)
    camion         = fields.Char(string='Camion',            tracking=True)
    remorque       = fields.Char(string='Remorque',          tracking=True)
    prestataire    = fields.Char(string='Prestataire',       tracking=True)
    lieu_livraison = fields.Char(string='Lieu de Livraison', tracking=True)
    numero_permis  = fields.Char(string='N Permis',          tracking=True)

    # Bascule - Pesees
    tare_p1       = fields.Float(string='Tare P1 (T)',        tracking=True)
    poids_brut_p2 = fields.Float(string='Poids Brut P2 (T)', tracking=True)
    poids_net     = fields.Float(
        string='Poids Net (T)',
        compute='_compute_poids_net',
        store=True,
        tracking=True,
    )

    # Ecart pesee
    ecart_poids = fields.Float(
        string='Ecart (T)',
        compute='_compute_ecart_poids',
        store=True,
    )
    ecart_type = fields.Selection([
        ('ok',      'Conforme'),
        ('surplus', 'Surplus'),
        ('manque',  'Manque'),
    ], string='Type ecart', compute='_compute_ecart_poids', store=True)

    pesee_ids = fields.One2many(
        'gica.pesee',
        'bon_circulation_id',
        string='Historique pesees',
        readonly=True,
    )

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

    # Code QR
    qr_code = fields.Binary(
        string='Code QR',
        compute='_compute_qr_code',
        store=True,
    )

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

    # Statut
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
        """
        Commercial transmet le BC a la tare.
        Pas de verification chauffeur/camion ici —
        c'est l'agent bascule qui les saisit quand le camion arrive.
        """
        for rec in self:
            rec.write({'state': 'transmis_tare'})
            rec.message_post(
                body=f'Bon de circulation {rec.name} transmis a la tare.'
            )

    def action_pesee_entree(self):
        """
        Agent bascule saisit les infos du camion + tare P1.
        Chauffeur et matricule sont obligatoires ici —
        l'agent les voit physiquement avant de peser.
        """
        for rec in self:
            # Verification : chauffeur et matricule obligatoires
            if not rec.chauffeur:
                raise ValidationError(
                    'Veuillez saisir le nom du chauffeur avant de valider la pesee.'
                )
            if not rec.matricule:
                raise ValidationError(
                    'Veuillez saisir le matricule du camion avant de valider la pesee.'
                )
            # Verification : tare P1 obligatoire
            if not rec.tare_p1 or rec.tare_p1 <= 0:
                raise ValidationError(
                    'Veuillez saisir la Tare P1 avant de valider.'
                )
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
                raise ValidationError(
                    'La Tare P1 doit etre saisie et validee avant le chargement.'
                )
            rec.write({'state': 'chargement'})
            rec.message_post(body='Chargement en cours.')

    def action_pesee_sortie(self):
        for rec in self:
            if not rec.poids_brut_p2 or rec.poids_brut_p2 <= 0:
                raise ValidationError(
                    'Veuillez saisir le Poids Brut P2 avant de valider.'
                )
            if rec.poids_brut_p2 <= rec.tare_p1:
                raise ValidationError(
                    f'Le Poids Brut P2 ({rec.poids_brut_p2} T) doit etre '
                    f'superieur a la Tare P1 ({rec.tare_p1} T).'
                )
            nb_p2 = self.env['gica.pesee'].search_count([
                ('bon_circulation_id', '=', rec.id),
                ('type_pesee',         '=', 'charge'),
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
            rec.message_post(
                body=f'Pesee sortie validee - Poids Brut P2 : {rec.poids_brut_p2} T'
            )

    @api.depends('tare_p1', 'poids_brut_p2')
    def _compute_poids_net(self):
        for rec in self:
            rec.poids_net = max(0.0, rec.poids_brut_p2 - rec.tare_p1)

    def action_terminer(self):
        for rec in self:
            if not rec.poids_brut_p2:
                raise ValidationError(
                    'Veuillez saisir le Poids Brut P2 avant de terminer.'
                )
            rec.write({'state': 'termine'})
            # Mettre a jour date reelle enlevement sur sale.order
            if rec.sale_order_id:
                rec.sale_order_id.write({
                    'date_reelle_enlevement': fields.Date.today()
                })
                if rec.sale_order_id.commande_globale_id:
                    rec.sale_order_id.commande_globale_id._check_cloture_automatique()
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
            if rec.sale_order_id:
                rec.sale_order_id.write({
                    'date_reelle_enlevement': fields.Date.today()
                })
                if rec.sale_order_id.commande_globale_id:
                    rec.sale_order_id.commande_globale_id._check_cloture_automatique()
            rec.message_post(
                body=f'Surplus accepte - Poids Net : {rec.poids_net:.2f} T '
                     f'(prevu {rec.quantite_prevue:.2f} T, ecart +{rec.ecart_poids:.2f} T)'
            )

    def action_decharger_surplus(self):
        for rec in self:
            rec.write({'state': 'chargement', 'poids_brut_p2': 0.0})
            rec.message_post(
                body=f'Dechargement du surplus - '
                     f'Ecart : +{rec.ecart_poids:.2f} T. Retour au chargement.'
            )

    def action_recharger_manque(self):
        for rec in self:
            rec.write({'state': 'chargement', 'poids_brut_p2': 0.0})
            rec.message_post(
                body=f'Rechargement demande - '
                     f'Manque : {abs(rec.ecart_poids):.2f} T. Retour au chargement.'
            )

    def action_accepter_manque(self):
        for rec in self:
            rec.write({'state': 'termine'})
            if rec.sale_order_id:
                rec.sale_order_id.write({
                    'date_reelle_enlevement': fields.Date.today()
                })
                if rec.sale_order_id.commande_globale_id:
                    rec.sale_order_id.commande_globale_id._check_cloture_automatique()
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

    # Retour arriere
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

    # Creation avec sequence
    @api.model_create_multi
    def create(self, vals_list):
        today = date.today()
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.bon.circulation'
                ) or 'Nouveau'
            if not vals.get('numero_chaine'):
                seq = self.env['ir.sequence'].next_by_code(
                    'gica.bon.circulation.chaine'
                ) or '0000'
                vals['numero_chaine'] = (
                    f"{today.year}/{today.month:02d}/{today.day:02d}/CIM/{seq}"
                )
        return super().create(vals_list)