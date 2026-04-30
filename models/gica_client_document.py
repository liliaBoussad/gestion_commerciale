from odoo import models, fields, api


class GicaDocumentTemplate(models.Model):
    _name = 'gica.document.template'
    _description = 'Template de document requis — GICA'
    _order = 'section, sequence'

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
    ], string='Type client')

    nature_type = fields.Selection([
        ('personne_morale',   'Personne Morale'),
        ('personne_physique', 'Personne Physique'),
        ('filiale_gica',      'Filiale GICA'),
        ('auto_const',        'Auto-constructeur'),
        ('association_rel',   'Association religieuse'),
        ('collectivite',      'Collectivité / Institution'),
    ], string='Nature (admin)')

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
        if self.search_count([('section', '=', 'tech')]) > 0:
            return

        TECH_TEMPLATES = [
            ('realisation',    'tech', 'local', 10, "Bon de commande global (précisant les informations du projet et du maître d'ouvrage)"),
            ('investisseur',   'tech', 'local', 10, 'Copie du permis de construire en cours de validité'),
            ('investisseur',   'tech', 'local', 20, 'Bon de commande'),
            ('promoteur',      'tech', 'local', 10, 'Copie du permis de construire en cours de validité'),
            ('promoteur',      'tech', 'local', 20, 'Bon de commande'),
            ('transformateur', 'tech', 'local', 10, 'Bon de commande'),
            ('broyage',        'tech', 'local', 10, 'Bon de commande'),
            ('revendeur',      'tech', 'local', 10, 'Bon de commande'),
            ('rev_agree',      'tech', 'local', 10, 'Cahier des charges'),
            ('rev_agree',      'tech', 'local', 20, 'Bon de commande'),
            ('distributeur',   'tech', 'local', 10, 'Cahier des charges'),
            ('distributeur',   'tech', 'local', 20, 'Bon de commande'),
            ('conditionneur',  'tech', 'local', 10, 'Cahier des charges'),
            ('conditionneur',  'tech', 'local', 20, 'Bon de commande'),
            ('exportateur',    'tech', 'local', 10, 'Bon de commande'),
            ('autres',         'tech', 'local', 10, 'Bon de commande'),
            ('auto_const',     'tech', 'local', 10, 'Bon de commande'),
        ]

        for client_type, section, marche, seq, name in TECH_TEMPLATES:
            self.create({
                'client_type': client_type,
                'section':     section,
                'marche':      marche,
                'sequence':    seq,
                'name':        name,
            })


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
    name        = fields.Char(string='Document requis', required=True)
    section     = fields.Selection([
        ('admin', 'Dossier administratif'),
        ('tech',  'Dossier technique'),
    ], string='Section', required=True)
    marche      = fields.Selection([
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
    doc_total      = fields.Integer(compute='_compute_doc_stats', store=True)
    doc_fournis    = fields.Integer(compute='_compute_doc_stats', store=True)
    doc_manquants  = fields.Integer(compute='_compute_doc_stats', store=True)
    dossier_valide = fields.Boolean(string='Dossier validé', default=False, tracking=True)

    @api.depends('document_ids.state')
    def _compute_doc_stats(self):
        for rec in self:
            docs              = rec.document_ids
            fournis           = len(docs.filtered(lambda d: d.state == 'fourni'))
            rec.doc_total     = len(docs)
            rec.doc_fournis   = fournis
            rec.doc_manquants = len(docs) - fournis

    def _generate_documents(self):
        self.ensure_one()
        self.document_ids.unlink()
        Doc = self.env['gica.client.document']

        # Documents ADMIN depuis nature_id.document_ids
        if self.nature_id and self.nature_id.document_ids:
            for tmpl in self.nature_id.document_ids.sorted('sequence'):
                Doc.create({
                    'client_id':   self.id,
                    'template_id': tmpl.id,
                    'name':        tmpl.name,
                    'section':     'admin',
                    'marche':      'local',
                    'sequence':    tmpl.sequence,
                    'state':       'manquant',
                })

        # Documents TECH depuis client_type
        if self.client_type:
            Tmpl = self.env['gica.document.template']
            Tmpl._load_default_templates()
            tech_tmpls = Tmpl.search([
                ('client_type', '=', self.client_type),
                ('section', '=', 'tech'),
                ('marche', '=', 'local'),
            ], order='sequence')
            for tmpl in tech_tmpls:
                Doc.create({
                    'client_id':   self.id,
                    'template_id': tmpl.id,
                    'name':        tmpl.name,
                    'section':     'tech',
                    'marche':      'local',
                    'sequence':    tmpl.sequence,
                    'state':       'manquant',
                })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.client_type:
                rec._generate_documents()
        return records

    @api.onchange('client_type', 'nature_id')
    def _onchange_regenerer_documents(self):
        if not self.client_type:
            return
        new_lines = [(5, 0, 0)]

        # Admin depuis nature
        if self.nature_id and self.nature_id.document_ids:
            for tmpl in self.nature_id.document_ids.sorted('sequence'):
                new_lines.append((0, 0, {
                    'template_id': tmpl.id,
                    'name':        tmpl.name,
                    'section':     'admin',
                    'marche':      'local',
                    'sequence':    tmpl.sequence,
                    'state':       'manquant',
                }))

        # Tech depuis client_type
        if self.client_type:
            Tmpl = self.env['gica.document.template']
            Tmpl._load_default_templates()
            tech_tmpls = Tmpl.search([
                ('client_type', '=', self.client_type),
                ('section', '=', 'tech'),
                ('marche', '=', 'local'),
            ], order='sequence')
            for tmpl in tech_tmpls:
                new_lines.append((0, 0, {
                    'template_id': tmpl.id,
                    'name':        tmpl.name,
                    'section':     'tech',
                    'marche':      'local',
                    'sequence':    tmpl.sequence,
                    'state':       'manquant',
                }))

        self.document_ids = new_lines

    def action_generer_documents(self):
        self.ensure_one()
        self._generate_documents()

    def action_valider_dossier(self):
        self.ensure_one()
        self.dossier_valide = True

    def action_reinitialiser_dossier(self):
        self.ensure_one()
        self.dossier_valide = False