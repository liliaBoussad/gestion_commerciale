# -*- coding: utf-8 -*-
from odoo import models, fields, api


# ═════════════════════════════════════════════════════════════════════════════
# 1. MODÈLE TEMPLATE
# ═════════════════════════════════════════════════════════════════════════════
class GicaDocumentTemplate(models.Model):
    _name        = 'gica.document.template'
    _description = 'Template de document requis — GICA'
    _order       = 'client_type, nature_client, section, sequence'

    name = fields.Char(string='Document requis', required=True)

    client_type = fields.Selection([
        ('realisation',    'Entreprise de réalisation'),
        ('investisseur',   'Investisseur'),
        ('promoteur',      'Promoteur immobilier'),
        ('transformateur', 'Transformateur'),
        ('broyage',        'Centre de broyage'),
        ('revendeur',      'Revendeur'),
        ('rev_agree',      'Revendeur agréé'),
        ('distributeur',   'Distributeur officiel'),
        ('conditionneur',  'Conditionneur'),
        ('exportateur',    'Exportateur'),
        ('auto_const',     'Auto-constructeur'),
        ('autres',         'Autres'),
        ('fab_etr',        'Fabricant étranger'),
        ('trader',         'Trader international'),
        ('ent_etr',        'Entreprise étrangère'),
    ], string='Type client', required=True)

    nature_client = fields.Selection([
        ('morale',   'Personne Morale'),
        ('physique', 'Personne Physique'),
        ('both',     'Les deux'),
    ], string='Nature client', required=True, default='both')

    section = fields.Selection([
        ('admin', 'Dossier administratif'),
        ('tech',  'Dossier technique'),
    ], string='Section', required=True)

    marche = fields.Selection([
        ('local',  'Marché local'),
        ('export', 'Exportation'),
    ], string='Marché', required=True, default='local')

    sequence = fields.Integer(default=10)
    active   = fields.Boolean(default=True)

    @api.model
    def _load_default_templates(self):
        if self.search_count([]) >= 50:
            return

        # (client_type, section, marche, nature, sequence, nom)
        TEMPLATES = [
            # ── Entreprise de réalisation ─────────────────────────────────
            ('realisation', 'admin', 'local', 'morale',  10, 'Copie des statuts'),
            ('realisation', 'admin', 'local', 'morale',  20, 'Registre de commerce électronique'),
            ('realisation', 'admin', 'local', 'morale',  30, "Numéro d'identification statistique (NIS)"),
            ('realisation', 'admin', 'local', 'morale',  40, "Numéro d'identification fiscale (NIF)"),
            ('realisation', 'admin', 'local', 'morale',  50, "Numéro d'article d'imposition (TIN)"),
            ('realisation', 'admin', 'local', 'morale',  60, "Pièce d'identité du représentant légal"),
            # ── Investisseur ──────────────────────────────────────────────
            ('investisseur', 'admin', 'local', 'morale',   10, 'Copie des statuts'),
            ('investisseur', 'admin', 'local', 'morale',   20, 'Registre de commerce électronique'),
            ('investisseur', 'admin', 'local', 'morale',   30, 'NIS / NIF / TIN'),
            ('investisseur', 'admin', 'local', 'morale',   40, "Pièce d'identité du représentant légal"),
            ('investisseur', 'admin', 'local', 'physique', 10, "Copie de la pièce d'identité"),
            ('investisseur', 'tech',  'local', 'both',     10, 'Permis de construire en cours de validité'),
            # ── Promoteur immobilier ──────────────────────────────────────
            ('promoteur', 'admin', 'local', 'morale',   10, 'Copie des statuts'),
            ('promoteur', 'admin', 'local', 'morale',   20, 'Registre de commerce électronique'),
            ('promoteur', 'admin', 'local', 'morale',   30, 'NIS / NIF / TIN'),
            ('promoteur', 'admin', 'local', 'morale',   40, "Pièce d'identité du représentant légal"),
            ('promoteur', 'admin', 'local', 'physique', 10, "Copie de la pièce d'identité"),
            ('promoteur', 'tech',  'local', 'both',     10, 'Permis de construire en cours de validité'),
            # ── Transformateur ────────────────────────────────────────────
            ('transformateur', 'admin', 'local', 'morale', 10, 'Copie des statuts'),
            ('transformateur', 'admin', 'local', 'morale', 20, 'Registre de commerce électronique'),
            ('transformateur', 'admin', 'local', 'morale', 30, 'NIS / NIF / TIN'),
            ('transformateur', 'admin', 'local', 'morale', 40, "Pièce d'identité du représentant légal"),
            # ── Centre de broyage ─────────────────────────────────────────
            ('broyage', 'admin', 'local', 'morale', 10, 'Copie des statuts'),
            ('broyage', 'admin', 'local', 'morale', 20, 'Registre de commerce électronique'),
            ('broyage', 'admin', 'local', 'morale', 30, 'NIS / NIF / TIN'),
            ('broyage', 'admin', 'local', 'morale', 40, "Pièce d'identité du représentant légal"),
            # ── Revendeur ─────────────────────────────────────────────────
            ('revendeur', 'admin', 'local', 'morale', 10, 'Copie des statuts'),
            ('revendeur', 'admin', 'local', 'morale', 20, 'Registre de commerce électronique'),
            ('revendeur', 'admin', 'local', 'morale', 30, 'NIS / NIF / TIN'),
            ('revendeur', 'admin', 'local', 'morale', 40, "Pièce d'identité du représentant légal"),
            # ── Revendeur agréé ───────────────────────────────────────────
            ('rev_agree', 'admin', 'local', 'morale', 10, 'Copie des statuts'),
            ('rev_agree', 'admin', 'local', 'morale', 20, 'Registre de commerce électronique'),
            ('rev_agree', 'admin', 'local', 'morale', 30, 'NIS / NIF / TIN'),
            ('rev_agree', 'admin', 'local', 'morale', 40, "Pièce d'identité du représentant légal"),
            ('rev_agree', 'tech',  'local', 'both',   10, 'Cahier des charges signé'),
            # ── Distributeur officiel ─────────────────────────────────────
            ('distributeur', 'admin', 'local', 'morale', 10, 'Copie des statuts'),
            ('distributeur', 'admin', 'local', 'morale', 20, 'Registre de commerce électronique'),
            ('distributeur', 'admin', 'local', 'morale', 30, 'NIS / NIF / TIN'),
            ('distributeur', 'admin', 'local', 'morale', 40, "Relevé d'identification bancaire (RIB)"),
            ('distributeur', 'admin', 'local', 'morale', 50, "Pièce d'identité du représentant légal"),
            ('distributeur', 'tech',  'local', 'both',   10, 'Cahier des charges signé'),
            # ── Conditionneur ─────────────────────────────────────────────
            ('conditionneur', 'admin', 'local', 'morale', 10, 'Copie des statuts'),
            ('conditionneur', 'admin', 'local', 'morale', 20, 'Registre de commerce électronique'),
            ('conditionneur', 'admin', 'local', 'morale', 30, 'NIS / NIF / TIN'),
            ('conditionneur', 'admin', 'local', 'morale', 40, "Pièce d'identité du représentant légal"),
            ('conditionneur', 'tech',  'local', 'both',   10, 'Cahier des charges signé'),
            # ── Exportateur ───────────────────────────────────────────────
            ('exportateur', 'admin', 'local', 'morale', 10, 'Copie des statuts'),
            ('exportateur', 'admin', 'local', 'morale', 20, 'Registre de commerce électronique'),
            ('exportateur', 'admin', 'local', 'morale', 30, 'NIS / NIF / TIN'),
            ('exportateur', 'admin', 'local', 'morale', 40, "Pièce d'identité du représentant légal"),
            # ── Auto-constructeur ─────────────────────────────────────────
            ('auto_const', 'admin', 'local', 'physique', 10, "Copie de la pièce d'identité"),
            ('auto_const', 'tech',  'local', 'physique', 10, 'Permis de construire (si applicable)'),
            # ── Autres ────────────────────────────────────────────────────
            ('autres', 'admin', 'local', 'both', 10, "Agrément ou statuts de l'association"),
            ('autres', 'tech',  'local', 'both', 10, 'Permis de construire (associations religieuses)'),
            # ── Export international ──────────────────────────────────────
            ('fab_etr', 'admin', 'export', 'morale', 10, 'Copie des statuts (personnes morales)'),
            ('fab_etr', 'admin', 'export', 'morale', 20, 'Registre de commerce électronique'),
            ('fab_etr', 'admin', 'export', 'morale', 30, "Numéro d'identification fiscale (VAT)"),
            ('fab_etr', 'admin', 'export', 'morale', 40, 'Numéro SWIFT et coordonnées bancaires'),
            ('fab_etr', 'tech',  'export', 'both',   10, 'Lettre de crédit irrévocable confirmée payable à vue (LC)'),
            ('fab_etr', 'tech',  'export', 'both',   20, 'Contrat de vente international signé'),
            ('trader',  'admin', 'export', 'morale', 10, 'Copie des statuts (personnes morales)'),
            ('trader',  'admin', 'export', 'morale', 20, 'Registre de commerce électronique'),
            ('trader',  'admin', 'export', 'morale', 30, "Numéro d'identification fiscale (VAT)"),
            ('trader',  'admin', 'export', 'morale', 40, 'Numéro SWIFT et coordonnées bancaires'),
            ('trader',  'tech',  'export', 'both',   10, 'Lettre de crédit irrévocable confirmée payable à vue (LC)'),
            ('trader',  'tech',  'export', 'both',   20, 'Contrat de vente international signé'),
            ('trader',  'tech',  'export', 'both',   30, 'Incoterm convenu (FOB, CIF, CFR, etc.)'),
            ('ent_etr', 'admin', 'export', 'morale', 10, 'Copie des statuts (personnes morales)'),
            ('ent_etr', 'admin', 'export', 'morale', 20, 'Registre de commerce électronique'),
            ('ent_etr', 'admin', 'export', 'morale', 30, "Numéro d'identification fiscale (VAT)"),
            ('ent_etr', 'admin', 'export', 'morale', 40, 'Numéro SWIFT et coordonnées bancaires'),
            ('ent_etr', 'tech',  'export', 'both',   10, 'Lettre de crédit irrévocable confirmée payable à vue (LC)'),
            ('ent_etr', 'tech',  'export', 'both',   20, 'Contrat de vente international signé'),
            ('ent_etr', 'tech',  'export', 'both',   30, "Documents d'expédition et de certification"),
        ]

        for client_type, section, marche, nature, seq, name in TEMPLATES:
            self.create({
                'client_type':   client_type,
                'section':       section,
                'marche':        marche,
                'nature_client': nature,
                'sequence':      seq,
                'name':          name,
            })


# ═════════════════════════════════════════════════════════════════════════════
# 2. DOCUMENT CLIENT — lié à res.partner via partner_id
# ═════════════════════════════════════════════════════════════════════════════
class GicaClientDocument(models.Model):
    _name        = 'gica.client.document'
    _description = 'Document client — Dossier GICA'
    _order       = 'section, sequence'

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        ondelete='cascade',
        index=True,
    )
    template_id = fields.Many2one(
        'gica.document.template', string='Template', ondelete='set null',
    )
    name    = fields.Char(string='Document requis', required=True)
    section = fields.Selection([
        ('admin', 'Dossier administratif'),
        ('tech',  'Dossier technique'),
    ], string='Section', required=True)
    marche = fields.Selection([
        ('local',  'Marché local'),
        ('export', 'Exportation'),
    ], string='Marché', required=True, default='local')
    sequence    = fields.Integer(default=10)
    fichier     = fields.Binary(string='Fichier joint', attachment=True)
    fichier_nom = fields.Char(string='Nom du fichier')
    state       = fields.Selection([
        ('manquant', 'Manquant'),
        ('fourni',   'Fourni'),
    ], string='État', default='manquant', required=True)

    @api.onchange('fichier')
    def _onchange_fichier(self):
        self.state = 'fourni' if self.fichier else 'manquant'

    def action_supprimer_fichier(self):
        self.write({'fichier': False, 'fichier_nom': False, 'state': 'manquant'})