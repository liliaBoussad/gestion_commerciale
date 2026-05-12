# -*- coding: utf-8 -*-
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

# Natures possibles par catégorie
NATURE_PAR_TYPE = {
    'realisation':    ['morale'],
    'investisseur':   ['morale', 'physique'],
    'promoteur':      ['morale', 'physique'],
    'transformateur': ['morale'],
    'broyage':        ['morale'],
    'revendeur':      ['morale'],
    'rev_agree':      ['morale'],
    'distributeur':   ['morale'],
    'conditionneur':  ['morale'],
    'exportateur':    ['morale'],
    'auto_const':     ['physique'],
    'autres':         ['morale', 'physique'],
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Identification GICA ───────────────────────────────────────────────
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
    ], string='Type client', tracking=True)

    nature_client = fields.Selection([
        ('morale',   'Personne Morale'),
        ('physique', 'Personne Physique'),
    ], string='Nature (interne)', tracking=True)

    nature_id = fields.Many2one(
        'gica.client.nature',
        string='Nature du client',
        tracking=True,
    )

    nature_domain_view = fields.Char(
        compute='_compute_nature_domain_view',
    )

    commercial_id = fields.Many2one(
        'res.users', string='Commercial', tracking=True,
    )

    sale_type = fields.Selection([
        ('comptant', 'Comptant'),
        ('terme',    'Vente à terme'),
    ], string='Type de vente', default='comptant', tracking=True)

    is_gica_client = fields.Boolean(
        string='Client GICA',
        compute='_compute_is_gica_client',
        store=True,
    )

    # ── Agrément ──────────────────────────────────────────────────────────
    AGREMENT_TYPES = ['distributeur', 'conditionneur', 'rev_agree']

    agrement_ids = fields.One2many(
        'gica.client.agrement', 'partner_id', string='Agréments',
    )
    agrement_actif_id = fields.Many2one(
        'gica.client.agrement',
        string='Agrément actif',
        compute='_compute_agrement_actif',
        store=True,
    )
    agrement_numero = fields.Char(
        related='agrement_actif_id.name', string='N° Agrément', readonly=True,
    )
    agrement_expiration = fields.Date(
        related='agrement_actif_id.date_expiration', string='Expiration', readonly=True,
    )
    agrement_statut = fields.Selection(
        related='agrement_actif_id.state', string='Statut agrément', readonly=True,
    )
    agrement_count = fields.Integer(
        compute='_compute_agrement_count', string="Nombre d'agréments",
    )
    need_agrement = fields.Boolean(
        compute='_compute_need_agrement', store=True, string='Agrément manquant',
    )

    @api.depends('agrement_ids.state')
    def _compute_agrement_actif(self):
        for rec in self:
            actif = rec.agrement_ids.filtered(
                lambda a: a.state == 'actif'
            ).sorted('date_debut', reverse=True)
            rec.agrement_actif_id = actif[0] if actif else False

    @api.depends('agrement_ids')
    def _compute_agrement_count(self):
        for rec in self:
            rec.agrement_count = len(rec.agrement_ids)

    @api.depends('client_type', 'agrement_actif_id')
    def _compute_need_agrement(self):
        for rec in self:
            rec.need_agrement = (
                rec.client_type in self.AGREMENT_TYPES
                and not rec.agrement_actif_id
            )

    # ── Documents ─────────────────────────────────────────────────────────
    document_ids = fields.One2many(
        'gica.client.document', 'partner_id', string='Documents du dossier',
    )
    document_admin_ids = fields.One2many(
        'gica.client.document', 'partner_id',
        string='Documents administratifs',
        domain=[('section', '=', 'admin')],
    )
    document_tech_ids = fields.One2many(
        'gica.client.document', 'partner_id',
        string='Documents techniques',
        domain=[('section', '=', 'tech')],
    )
    doc_total      = fields.Integer(compute='_compute_doc_stats', store=True, string='Total')
    doc_fournis    = fields.Integer(compute='_compute_doc_stats', store=True, string='Fournis')
    doc_manquants  = fields.Integer(compute='_compute_doc_stats', store=True, string='Manquants')
    dossier_valide = fields.Boolean(
        string='Dossier validé', default=False, tracking=True,
    )

    @api.depends('document_ids.state')
    def _compute_doc_stats(self):
        for rec in self:
            docs    = rec.document_ids
            fournis = docs.filtered(lambda d: d.state == 'fourni')
            rec.doc_total     = len(docs)
            rec.doc_fournis   = len(fournis)
            rec.doc_manquants = len(docs) - len(fournis)

    # ── Classification ────────────────────────────────────────────────────
    exclusivite_gica = fields.Boolean(
        string='Exclusivité GICA', default=False, tracking=True,
        help='Le client achète exclusivement des produits GICA (+10 pts).',
    )
    classification_actuelle = fields.Selection([
        ('platinum', 'PLATINUM'),
        ('gold',     'GOLD'),
        ('silver',   'SILVER'),
        ('bronze',   'BRONZE'),
    ], string='Classification Actuelle', readonly=True, tracking=True)

    score_actuel = fields.Float(
        string='Score Actuel (/100)', readonly=True, tracking=True,
    )
    date_derniere_classification = fields.Date(
        string='Dernière Classification', readonly=True,
    )
    classification_ids = fields.One2many(
        'gica.client.classification', 'partner_id',
        string='Historique Classifications',
    )
    delai_paiement = fields.Integer(
        string='Délai de paiement (jours)',
        compute='_compute_delai_paiement',
        store=True,
        help='PLATINUM=30j | GOLD=15j | SILVER/BRONZE=0j',
    )

    @api.depends('classification_actuelle')
    def _compute_delai_paiement(self):
        DELAIS = {'platinum': 30, 'gold': 15, 'silver': 0, 'bronze': 0}
        for partner in self:
            partner.delai_paiement = DELAIS.get(
                partner.classification_actuelle or '', 0
            )

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends('client_type')
    def _compute_is_gica_client(self):
        for rec in self:
            rec.is_gica_client = bool(rec.client_type)

    @api.depends('client_type')
    def _compute_nature_domain_view(self):
        for rec in self:
            if rec.client_type == 'auto_const':
                rec.nature_domain_view = "[('type_nature','=','utilise'),('parent_id.name','=','Cas Particuliers')]"
            elif rec.client_type == 'autres':
                rec.nature_domain_view = "[('type_nature','=','utilise'),('parent_id.name','=','Autres Clients')]"
            elif rec.client_type:
                rec.nature_domain_view = "[('type_nature','=','utilise'),('parent_id','=',False)]"
            else:
                rec.nature_domain_view = "[('type_nature','=','utilise')]"

    # ── Onchange ──────────────────────────────────────────────────────────
    @api.onchange('client_type')
    def _onchange_client_type(self):
        self.nature_client = False
        self.nature_id = False
        if self.client_type:
            natures = NATURE_PAR_TYPE.get(self.client_type, [])
            if len(natures) == 1:
                self.nature_client = natures[0]

    @api.onchange('nature_id')
    def _onchange_nature_id(self):
        """Synchronise nature_client depuis nature_id."""
        if self.nature_id:
            if 'physique' in self.nature_id.name.lower():
                self.nature_client = 'physique'
            else:
                self.nature_client = 'morale'
        else:
            self.nature_client = False

    @api.onchange('nature_client')
    def _onchange_nature_client(self):
        """Rien — les documents sont générés via bouton ou au create."""
        pass

    # ── Génération documents ──────────────────────────────────────────────
    def _generer_documents_templates(self):
        """Génère les documents (onchange) depuis gica.document.template."""
        if not self.client_type or not self.nature_client:
            return
        Tmpl = self.env['gica.document.template']
        Tmpl._load_default_templates()
        templates = Tmpl.search([
            ('client_type',   '=', self.client_type),
            ('nature_client', 'in', [self.nature_client, 'both']),
        ], order='section, sequence')
        new_lines = [(5, 0, 0)]
        for tmpl in templates:
            new_lines.append((0, 0, {
                'template_id': tmpl.id,
                'name':        tmpl.name,
                'section':     tmpl.section,
                'sequence':    tmpl.sequence,
                'state':       'manquant',
            }))
        self.document_ids = new_lines

    def _generate_documents(self):
        """Génère et sauvegarde les documents en base (appelé au create)."""
        self.ensure_one()
        Tmpl = self.env['gica.document.template']
        Tmpl._load_default_templates()
        templates = Tmpl.search([
            ('client_type',   '=', self.client_type),
            ('nature_client', 'in', [self.nature_client, 'both']),
        ], order='section, sequence')
        if not templates:
            return
        self.document_ids.unlink()
        for tmpl in templates:
            self.env['gica.client.document'].create({
                'partner_id':  self.id,
                'template_id': tmpl.id,
                'name':        tmpl.name,
                'section':     tmpl.section,
                'sequence':    tmpl.sequence,
                'state':       'manquant',
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.client_type and rec.nature_client:
                rec._generate_documents()
        return records

    # ── Actions ───────────────────────────────────────────────────────────
    def action_generer_documents(self):
        self.ensure_one()
        self._generate_documents()

    def action_valider_dossier(self):
        self.ensure_one()
        self.dossier_valide = True

    def action_reinitialiser_dossier(self):
        self.ensure_one()
        self.dossier_valide = False

    def action_creer_agrement(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      "Créer un agrément",
            'res_model': 'gica.client.agrement',
            'view_mode': 'form',
            'target':    'new',
            'context':   {'default_partner_id': self.id},
        }

    def action_voir_agrements(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Agréments',
            'res_model': 'gica.client.agrement',
            'view_mode': 'list,form',
            'domain':    [('partner_id', '=', self.id)],
            'context':   {'default_partner_id': self.id},
        }

    def action_calculer_classification(self):
        self.ensure_one()
        today        = fields.Date.today()
        period_end   = today
        period_start = today - relativedelta(months=6)
        gica = self.env['gica.client'].search(
            [('partner_id', '=', self.id)], limit=1
        )
        if not gica:
            return
        record = self.env['gica.client.classification'].calculate_client_classification(
            gica.id, period_start, period_end
        )
        return {
            'type':      'ir.actions.act_window',
            'name':      'Classification',
            'res_model': 'gica.client.classification',
            'view_mode': 'form',
            'res_id':    record.id,
        }