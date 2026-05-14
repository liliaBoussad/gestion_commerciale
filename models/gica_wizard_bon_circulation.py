# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaWizardBonCirculation(models.TransientModel):
    _name        = 'gica.wizard.bon.circulation'
    _description = 'Wizard Génération Bon de Circulation'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Commande de Vente',
        readonly=True,
    )
    circulation_line_id = fields.Many2one(
        'gica.circulation.line',
        string='Ligne de rotation',
        readonly=True,
    )

    # ── Infos affichées ───────────────────────────────────────────────────
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        readonly=True,
    )
    quantite    = fields.Float(string='Quantité (T)',      readonly=True)
    nbr_paquets = fields.Integer(string='Nb Paquets',     readonly=True)

    # ── Saisie chauffeur / camion ─────────────────────────────────────────
    chauffeur      = fields.Char(string='Chauffeur',         required=True)
    matricule      = fields.Char(string='Matricule Camion',  required=True)
    camion         = fields.Char(string='N° Camion')
    remorque       = fields.Char(string='Remorque')
    numero_permis  = fields.Char(string='N° Permis')
    prestataire    = fields.Char(string='Prestataire')
    lieu_livraison = fields.Char(string='Lieu de Livraison')

    def action_generer(self):
        self.ensure_one()
        line = self.circulation_line_id

        circ = self.env['gica.bon.circulation'].create({
            'sale_order_id':        self.sale_order_id.id,
            'planification_line_id': line.planification_line_id.id if line.planification_line_id else False,
            'product_id':           self.product_id.id,
            'quantite_prevue':      self.quantite,
            'nbr_paquets':          self.nbr_paquets,
            'numero_rotation':      line.numero_rotation,
            'chauffeur':            self.chauffeur,
            'matricule':            self.matricule,
            'camion':               self.camion,
            'remorque':             self.remorque,
            'numero_permis':        self.numero_permis,
            'prestataire':          self.prestataire,
            'lieu_livraison':       self.lieu_livraison,
        })

        # Lier le CIRC à la ligne de rotation
        line.write({
            'bon_circulation_id': circ.id,
            'state':              'genere',
            'chauffeur':          self.chauffeur,
            'matricule':          self.matricule,
        })

        return {
            'type':      'ir.actions.act_window',
            'name':      'Bon de Circulation',
            'res_model': 'gica.bon.circulation',
            'view_mode': 'form',
            'res_id':    circ.id,
        }


class GicaCirculationLine(models.Model):
    """Lignes de rotation dans l'onglet BC — 1 ligne par rotation"""
    _name        = 'gica.circulation.line'
    _description = 'Ligne Rotation Bon de Circulation'
    _order       = 'numero_rotation'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Bon de Commande',
        required=True,
        ondelete='cascade',
    )
    planification_line_id = fields.Many2one(
        'gica.planification.client.line',
        string='Ligne Planification',
        readonly=True,
    )

    numero_rotation = fields.Integer(string='Rotation N°', readonly=True)
    product_id      = fields.Many2one('product.product', string='Produit', readonly=True)
    conditionnement = fields.Selection(
        related='product_id.conditionnement_gica',
        string='Conditionnement',
        store=True,
        readonly=True,
    )
    quantite        = fields.Float(string='Quantité (T)',  readonly=True)
    nbr_paquets     = fields.Integer(string='Nb Paquets', readonly=True)

    chauffeur  = fields.Char(string='Chauffeur')
    matricule  = fields.Char(string='Matricule')

    state = fields.Selection([
        ('planifie', 'Planifié'),
        ('genere',   'Bon généré'),
    ], string='État', default='planifie')

    bon_circulation_id = fields.Many2one(
        'gica.bon.circulation',
        string='Bon de Circulation',
        readonly=True,
    )

    def action_ouvrir_wizard(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Générer Bon de Circulation',
            'res_model': 'gica.wizard.bon.circulation',
            'view_mode': 'form',
            'target':    'new',
            'context': {
                'default_sale_order_id':        self.sale_order_id.id,
                'default_circulation_line_id':  self.id,
                'default_product_id':           self.product_id.id,
                'default_quantite':             self.quantite,
                'default_nbr_paquets':          self.nbr_paquets,
            },
        }

    def action_voir_bon(self):
        self.ensure_one()
        if not self.bon_circulation_id:
            return
        return {
            'type':      'ir.actions.act_window',
            'name':      'Bon de Circulation',
            'res_model': 'gica.bon.circulation',
            'view_mode': 'form',
            'res_id':    self.bon_circulation_id.id,
        }