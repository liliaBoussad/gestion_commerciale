from odoo import models, fields, api


# ═════════════════════════════════════════════════════════════════════════════
# 1. MODÈLE TEMPLATE
# ═════════════════════════════════════════════════════════════════════════════
class GicaDocumentTemplate(models.Model):
    _name = 'gica.document.template'
    _description = 'Template de document requis — GICA'
    _order = 'client_type, marche, section, sequence'

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

    section = fields.Selection([
        ('admin', 'Dossier administratif'),
        ('tech',  'Dossier technique'),
    ], string='Section', required=True)

    marche = fields.Selection([
        ('local',  'Marché local'),
        ('export', 'Exportation'),
    ], string='Marché', required=True, default='local')

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.model
    def _load_default_templates(self):
        if self.search_count([]) > 0:
            return

        TEMPLATES = [
            # Entreprise de réalisation
            ('realisation', 'admin', 'local', 10, 'Copie des statuts'),
            ('realisation', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('realisation', 'admin', 'local', 30, "Numéro d'identification statistique (NIS)"),
            ('realisation', 'admin', 'local', 40, "Numéro d'identification fiscale (NIF)"),
            ('realisation', 'admin', 'local', 50, "Numéro d'article d'imposition (TIN)"),
            ('realisation', 'admin', 'local', 60, "Pièce d'identité du représentant légal"),
            ('realisation', 'tech',  'local', 10, "Bon de commande global (infos projet et maître d'ouvrage)"),
            # Investisseur
            ('investisseur', 'admin', 'local', 10, 'Copie des statuts'),
            ('investisseur', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('investisseur', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('investisseur', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('investisseur', 'tech',  'local', 10, 'Permis de construire en cours de validité'),
            ('investisseur', 'tech',  'local', 20, 'Bon de commande'),
            # Promoteur immobilier
            ('promoteur', 'admin', 'local', 10, 'Copie des statuts'),
            ('promoteur', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('promoteur', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('promoteur', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('promoteur', 'tech',  'local', 10, 'Permis de construire en cours de validité'),
            ('promoteur', 'tech',  'local', 20, 'Bon de commande'),
            # Transformateur
            ('transformateur', 'admin', 'local', 10, 'Copie des statuts'),
            ('transformateur', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('transformateur', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('transformateur', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('transformateur', 'tech',  'local', 10, 'Bon de commande'),
            # Centre de broyage
            ('broyage', 'admin', 'local', 10, 'Copie des statuts'),
            ('broyage', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('broyage', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('broyage', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('broyage', 'tech',  'local', 10, 'Bon de commande'),
            # Revendeur
            ('revendeur', 'admin', 'local', 10, 'Copie des statuts'),
            ('revendeur', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('revendeur', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('revendeur', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('revendeur', 'tech',  'local', 10, 'Bon de commande'),
            # Revendeur agréé
            ('rev_agree', 'admin', 'local', 10, 'Copie des statuts'),
            ('rev_agree', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('rev_agree', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('rev_agree', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('rev_agree', 'tech',  'local', 10, 'Cahier des charges signé'),
            ('rev_agree', 'tech',  'local', 20, 'Bon de commande'),
            # Distributeur officiel
            ('distributeur', 'admin', 'local', 10, 'Copie des statuts'),
            ('distributeur', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('distributeur', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('distributeur', 'admin', 'local', 40, "Relevé d'identification bancaire (RIB)"),
            ('distributeur', 'admin', 'local', 50, "Pièce d'identité du représentant légal"),
            ('distributeur', 'tech',  'local', 10, 'Cahier des charges signé'),
            ('distributeur', 'tech',  'local', 20, 'Bon de commande'),
            # Conditionneur
            ('conditionneur', 'admin', 'local', 10, 'Copie des statuts'),
            ('conditionneur', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('conditionneur', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('conditionneur', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('conditionneur', 'tech',  'local', 10, 'Cahier des charges signé'),
            ('conditionneur', 'tech',  'local', 20, 'Bon de commande'),
            # Exportateur
            ('exportateur', 'admin', 'local', 10, 'Copie des statuts'),
            ('exportateur', 'admin', 'local', 20, 'Registre de commerce électronique'),
            ('exportateur', 'admin', 'local', 30, 'NIS / NIF / TIN'),
            ('exportateur', 'admin', 'local', 40, "Pièce d'identité du représentant légal"),
            ('exportateur', 'tech',  'local', 10, 'Bon de commande'),
            # Auto-constructeur
            ('auto_const', 'admin', 'local', 10, "Copie de la pièce d'identité"),
            ('auto_const', 'tech',  'local', 10, 'Permis de construire en cours de validité (si applicable)'),
            # Autres
            ('autres', 'admin', 'local', 10, "Agrément ou statuts de l'association"),
            ('autres', 'admin', 'local', 20, "Bon de commande (collectivités / institutions d'État)"),
            ('autres', 'tech',  'local', 10, 'Permis de construire (associations religieuses)'),
            # Export international
            ('fab_etr', 'admin', 'export', 10, 'Copie des statuts (personnes morales)'),
            ('fab_etr', 'admin', 'export', 20, 'Registre de commerce électronique'),
            ('fab_etr', 'admin', 'export', 30, "Numéro d'identification fiscale (VAT)"),
            ('fab_etr', 'admin', 'export', 40, 'Numéro SWIFT et coordonnées bancaires'),
            ('fab_etr', 'tech',  'export', 10, 'Lettre de crédit irrévocable confirmée payable à vue (LC)'),
            ('fab_etr', 'tech',  'export', 20, 'Contrat de vente international signé'),
            ('trader', 'admin', 'export', 10, 'Copie des statuts (personnes morales)'),
            ('trader', 'admin', 'export', 20, 'Registre de commerce électronique'),
            ('trader', 'admin', 'export', 30, "Numéro d'identification fiscale (VAT)"),
            ('trader', 'admin', 'export', 40, 'Numéro SWIFT et coordonnées bancaires'),
            ('trader', 'tech',  'export', 10, 'Lettre de crédit irrévocable confirmée payable à vue (LC)'),
            ('trader', 'tech',  'export', 20, 'Contrat de vente international signé'),
            ('trader', 'tech',  'export', 30, 'Incoterm convenu (FOB, CIF, CFR, etc.)'),
            ('ent_etr', 'admin', 'export', 10, 'Copie des statuts (personnes morales)'),
            ('ent_etr', 'admin', 'export', 20, 'Registre de commerce électronique'),
            ('ent_etr', 'admin', 'export', 30, "Numéro d'identification fiscale (VAT)"),
            ('ent_etr', 'admin', 'export', 40, 'Numéro SWIFT et coordonnées bancaires'),
            ('ent_etr', 'tech',  'export', 10, 'Lettre de crédit irrévocable confirmée payable à vue (LC)'),
            ('ent_etr', 'tech',  'export', 20, 'Contrat de vente international signé'),
            ('ent_etr', 'tech',  'export', 30, "Documents d'expédition et de certification"),
        ]

        for client_type, section, marche, seq, name in TEMPLATES:
            self.create({
                'client_type': client_type,
                'section':     section,
                'marche':      marche,
                'sequence':    seq,
                'name':        name,
            })


# ═════════════════════════════════════════════════════════════════════════════
# 2. MODÈLE DOCUMENT CLIENT
# ═════════════════════════════════════════════════════════════════════════════
class GicaClientDocument(models.Model):
    _name = 'gica.client.document'
    _description = 'Document client — Dossier GICA'
    _order = 'section, sequence'

    client_id = fields.Many2one(
        'gica.client', string='Client',
        required=True, ondelete='cascade', index=True,
    )
    template_id = fields.Many2one(
        'gica.document.template', string='Template', ondelete='set null',
    )
    name = fields.Char(string='Document requis', required=True)

    section = fields.Selection([
        ('admin', 'Dossier administratif'),
        ('tech',  'Dossier technique'),
    ], string='Section', required=True)

    marche = fields.Selection([
        ('local',  'Marché local'),
        ('export', 'Exportation'),
    ], string='Marché', required=True, default='local')

    sequence = fields.Integer(default=10)

    fichier     = fields.Binary(string='Fichier joint', attachment=True)
    fichier_nom = fields.Char(string='Nom du fichier')

    state = fields.Selection([
        ('manquant', 'Manquant'),
        ('fourni',   'Fourni'),
    ], string='État', default='manquant', required=True)

    @api.onchange('fichier')
    def _onchange_fichier(self):
        if self.fichier:
            self.state = 'fourni'
        else:
            self.state = 'manquant'

    def action_supprimer_fichier(self):
        self.write({
            'fichier':     False,
            'fichier_nom': False,
            'state':       'manquant',
        })


# ═════════════════════════════════════════════════════════════════════════════
# 3. HÉRITAGE gica.client
# ═════════════════════════════════════════════════════════════════════════════
class GicaClientDocumentMixin(models.Model):
    _inherit = 'gica.client'

    document_ids = fields.One2many(
        'gica.client.document', 'client_id',
        string='Documents du dossier',
    )
    document_admin_ids = fields.One2many(
        'gica.client.document', 'client_id',
        string='Documents administratifs',
        domain=[('section', '=', 'admin')],
    )
    document_tech_ids = fields.One2many(
        'gica.client.document', 'client_id',
        string='Documents techniques',
        domain=[('section', '=', 'tech')],
    )

    doc_total = fields.Integer(
        string='Total', compute='_compute_doc_stats', store=True,
    )
    doc_fournis = fields.Integer(
        string='Fournis', compute='_compute_doc_stats', store=True,
    )
    doc_manquants = fields.Integer(
        string='Manquants', compute='_compute_doc_stats', store=True,
    )
    dossier_valide = fields.Boolean(
        string='Dossier validé', default=False, tracking=True,
    )

    @api.depends('document_ids.state')
    def _compute_doc_stats(self):
        for rec in self:
            docs              = rec.document_ids
            total             = len(docs)
            fournis           = len(docs.filtered(lambda d: d.state == 'fourni'))
            rec.doc_total     = total
            rec.doc_fournis   = fournis
            rec.doc_manquants = total - fournis

    # ── Méthode centrale de génération (utilisée par create + bouton) ─────────
    def _generate_documents(self):
        self.ensure_one()
        Tmpl = self.env['gica.document.template']
        Tmpl._load_default_templates()

        templates = Tmpl.search([
            ('client_type', '=', self.client_type),
            ('marche',      '=', 'local'),
        ], order='section, sequence')

        if not templates:
            return

        # Supprimer les anciennes lignes puis recréer
        self.document_ids.unlink()
        Doc = self.env['gica.client.document']
        for tmpl in templates:
            Doc.create({
                'client_id':   self.id,
                'template_id': tmpl.id,
                'name':        tmpl.name,
                'section':     tmpl.section,
                'marche':      tmpl.marche,
                'sequence':    tmpl.sequence,
                'state':       'manquant',
            })

    # ── Override create : génération automatique à la 1ère sauvegarde ─────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.client_type:
                rec._generate_documents()
        return records

    # ── Onchange : génération en mémoire pendant la saisie ───────────────────
    @api.onchange('client_type')
    def _onchange_client_type_documents(self):
        if not self.client_type:
            return
        Tmpl = self.env['gica.document.template']
        Tmpl._load_default_templates()
        templates = Tmpl.search([
            ('client_type', '=', self.client_type),
            ('marche',      '=', 'local'),
        ], order='section, sequence')
        if not templates:
            return
        new_lines = [(5, 0, 0)]
        for tmpl in templates:
            new_lines.append((0, 0, {
                'template_id': tmpl.id,
                'name':        tmpl.name,
                'section':     tmpl.section,
                'marche':      tmpl.marche,
                'sequence':    tmpl.sequence,
                'state':       'manquant',
            }))
        self.document_ids = new_lines

    # ── Bouton manuel pour clients existants sans documents ───────────────────
    def action_generer_documents(self):
        self.ensure_one()
        self._generate_documents()

    # ── Validation globale ────────────────────────────────────────────────────
    def action_valider_dossier(self):
        self.ensure_one()
        self.dossier_valide = True

    def action_reinitialiser_dossier(self):
        self.ensure_one()
        self.dossier_valide = False