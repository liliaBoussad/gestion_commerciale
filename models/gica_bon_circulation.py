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
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
        tracking=True,
    )

    # ── Liens ─────────────────────────────────────────────────────────────
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

    # ── Infos commande (related) ───────────────────────────────────────────
    client_id = fields.Many2one(
        'gica.client',
        related='sale_order_id.gica_client_id',
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
    conditionnement = fields.Selection(
        related='product_id.conditionnement_gica',
        string='Conditionnement',
        store=True,
        readonly=True,
    )
    quantite_prevue = fields.Float(
        string='Quantité Prévue (T)',
        readonly=True,
        tracking=True,
    )
    nbr_paquets = fields.Integer(
        string='Nombre de Paquets',
        readonly=True,
    )
    numero_rotation = fields.Integer(
        string='N° Rotation',
        readonly=True,
    )

    # ── N° de Chaîne ──────────────────────────────────────────────────────
    numero_chaine = fields.Char(
        string='N° de Chaîne',
        readonly=True,
        tracking=True,
    )

    # ── Logistique & Camion ───────────────────────────────────────────────
    chauffeur       = fields.Char(string='Chauffeur',        tracking=True)
    matricule       = fields.Char(string='Matricule',        tracking=True)
    camion          = fields.Char(string='Camion',           tracking=True)
    remorque        = fields.Char(string='Remorque',         tracking=True)
    prestataire     = fields.Char(string='Prestataire',      tracking=True)
    lieu_livraison  = fields.Char(string='Lieu de Livraison', tracking=True)
    numero_permis   = fields.Char(string='N° Permis',        tracking=True)

    # ── Bascule — Pesées ──────────────────────────────────────────────────
    tare_p1      = fields.Float(string='Tare P1 (T)',       tracking=True)
    poids_brut_p2 = fields.Float(string='Poids Brut P2 (T)', tracking=True)
    poids_net    = fields.Float(
        string='Poids Net (T)',
        compute='_compute_poids_net',
        store=True,
        tracking=True,
    )

    @api.depends('tare_p1', 'poids_brut_p2')
    def _compute_poids_net(self):
        for rec in self:
            rec.poids_net = max(0.0, rec.poids_brut_p2 - rec.tare_p1)

    # ── Code QR ───────────────────────────────────────────────────────────
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

    # ── Statut ────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('brouillon',          'Brouillon'),
        ('transmis_tare',      'Transmis à la tare'),
        ('pesee_entree',       'Pesée Entrée'),
        ('chargement',         'Chargement'),
        ('pesee_sortie',       'Pesée Sortie'),
        ('termine',            'Terminé'),
        ('annule',             'Annulé'),
    ], string='État', default='brouillon', tracking=True, required=True)

    # ── Actions workflow ──────────────────────────────────────────────────
    def action_transmettre_tare(self):
        for rec in self:
            if not rec.chauffeur or not rec.camion:
                raise ValidationError(
                    '❌ Veuillez renseigner le chauffeur et le camion avant de transmettre.'
                )
            rec.write({'state': 'transmis_tare'})
            rec.message_post(body='🚛 Bon transmis à la tare — en attente du camion.')

    def action_pesee_entree(self):
        for rec in self:
            if not rec.tare_p1 or rec.tare_p1 <= 0:
                raise ValidationError(
                    '❌ Veuillez saisir la Tare P1 avant de valider.'
                )
            rec.write({'state': 'pesee_entree'})
            self.env['gica.pesee'].create({
                'bon_circulation_id': rec.id,
                'type_pesee':         'vide',
                'poids':              rec.tare_p1,
                'agent_pesage_id':    self.env.user.id,
            })
            rec.message_post(body=f'⚖️ Pesée entrée (Tare P1) : {rec.tare_p1} T')

    def action_chargement(self):
        for rec in self:
            if not rec.tare_p1 or rec.tare_p1 <= 0:
                raise ValidationError(
                    '❌ La Tare P1 doit être saisie et validée avant le chargement.'
                )
            rec.write({'state': 'chargement'})
            rec.message_post(body='🏭 Chargement en cours.')

    def action_pesee_sortie(self):
        for rec in self:
            if not rec.poids_brut_p2 or rec.poids_brut_p2 <= 0:
                raise ValidationError(
                    '❌ Veuillez saisir le Poids Brut P2 avant de valider.'
                )
            if rec.poids_brut_p2 <= rec.tare_p1:
                raise ValidationError(
                    f'❌ Le Poids Brut P2 ({rec.poids_brut_p2} T) doit être '
                    f'supérieur à la Tare P1 ({rec.tare_p1} T).'
                )
            rec.write({'state': 'pesee_sortie'})
            self.env['gica.pesee'].create({
                'bon_circulation_id': rec.id,
                'type_pesee':         'charge',
                'poids':              rec.poids_brut_p2,
                'agent_pesage_id':    self.env.user.id,
            })
            rec.message_post(body=f'⚖️ Pesée sortie (Brut P2) : {rec.poids_brut_p2} T')

    def action_terminer(self):
        for rec in self:
            if not rec.poids_brut_p2:
                raise ValidationError('❌ Veuillez saisir le Poids Brut P2 avant de terminer.')
            # Alerte si poids net différent de quantité prévue
            ecart = abs(rec.poids_net - rec.quantite_prevue)
            tolerance = rec.quantite_prevue * 0.05  # 5% de tolérance
            if ecart > tolerance:
                raise ValidationError(
                    f'⚠️ Écart de poids détecté !\n'
                    f'  Quantité prévue : {rec.quantite_prevue:.2f} T\n'
                    f'  Poids Net réel  : {rec.poids_net:.2f} T\n'
                    f'  Écart           : {ecart:.2f} T\n\n'
                    f'Veuillez vérifier les pesées avant de terminer.'
                )
            rec.write({'state': 'termine'})
            rec.message_post(
                body=f'✅ Terminé — Poids Net : {rec.poids_net:.2f} T '
                     f'(P1={rec.tare_p1}T / P2={rec.poids_brut_p2}T)'
            )

    def action_annuler(self):
        for rec in self:
            rec.write({'state': 'annule'})
            rec.message_post(body='❌ Bon de circulation annulé.')

    def action_voir_bc_from_circ(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bon de Commande',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id':    self.sale_order_id.id,
        }

    # ── Retour arrière ────────────────────────────────────────────────────
    def action_retour_brouillon(self):
        """Retour de transmis_tare → brouillon"""
        for rec in self:
            rec.write({'state': 'brouillon'})
            rec.message_post(body='↩️ Retour en brouillon.')

    def action_retour_transmis(self):
        """Retour de pesee_entree → transmis_tare (corriger P1)"""
        for rec in self:
            rec.write({'state': 'transmis_tare', 'tare_p1': 0.0})
            # Supprimer la pesée P1 enregistrée
            pesees = self.env['gica.pesee'].search([
                ('bon_circulation_id', '=', rec.id),
                ('type_pesee', '=', 'vide'),
            ])
            pesees.unlink()
            rec.message_post(body='↩️ Correction — Tare P1 réinitialisée.')

    def action_retour_pesee_entree(self):
        """Retour de chargement → pesee_entree"""
        for rec in self:
            rec.write({'state': 'pesee_entree'})
            rec.message_post(body='↩️ Retour à la pesée entrée.')

    def action_retour_chargement(self):
        """Retour de pesee_sortie → chargement (corriger P2)"""
        for rec in self:
            rec.write({'state': 'chargement', 'poids_brut_p2': 0.0})
            # Supprimer la pesée P2 enregistrée
            pesees = self.env['gica.pesee'].search([
                ('bon_circulation_id', '=', rec.id),
                ('type_pesee', '=', 'charge'),
            ])
            pesees.unlink()
            rec.message_post(body='↩️ Correction — Poids Brut P2 réinitialisé.')

    # ── Création avec séquence ────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        today = date.today()
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gica.bon.circulation'
                ) or 'Nouveau'
            # Générer N° de Chaîne : YYYY/MM/DD/CIM/XXXX
            if not vals.get('numero_chaine'):
                seq = self.env['ir.sequence'].next_by_code(
                    'gica.bon.circulation.chaine'
                ) or '0000'
                vals['numero_chaine'] = (
                    f"{today.year}/{today.month:02d}/{today.day:02d}/CIM/{seq}"
                )
        return super().create(vals_list)