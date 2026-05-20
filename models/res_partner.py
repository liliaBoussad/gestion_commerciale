# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

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

AGREMENT_TYPES = ['distributeur', 'conditionneur', 'rev_agree']


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

    # ── Informations fiscales ─────────────────────────────────────────────
    nrc        = fields.Char(string='N° RC')
    nif        = fields.Char(string='N.I.F')
    nis        = fields.Char(string='N.I.S')
    ai         = fields.Char(string='A.I')
    fax        = fields.Char(string='Fax')
    rib        = fields.Char(string='RIB/RIP')
    swift      = fields.Char(string='SWIFT')
    nrc_valide = fields.Boolean(string='NRC Validé', default=False)
    nif_valide = fields.Boolean(string='NIF Validé', default=False)
    nis_valide = fields.Boolean(string='NIS Validé', default=False)
    nin        = fields.Char(string='N° Identification Nationale (NIN)')

    # ── Agrément ──────────────────────────────────────────────────────────
    agrement_ids = fields.One2many(
        'gica.client.agrement', 'partner_id', string='Agréments',
    )
    agrement_actif_id = fields.Many2one(
        'gica.client.agrement',
        string='Agrément en cours',
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
        compute='_compute_agrement_count', string="Agrément(s)",
    )
    need_agrement = fields.Boolean(
        compute='_compute_need_agrement', store=True, string='Agrément manquant',
    )

    @api.depends('agrement_ids.state')
    def _compute_agrement_actif(self):
        for rec in self:
            actif = rec.agrement_ids.filtered(
                lambda a: a.state == 'en_cours'
            ).sorted('date_debut', reverse=True)
            rec.agrement_actif_id = actif[0] if actif else False

    @api.depends('agrement_ids.state')
    def _compute_agrement_count(self):
        for rec in self:
            rec.agrement_count = len(
                rec.agrement_ids.filtered(lambda a: a.state == 'en_cours')
            )

    @api.depends('client_type', 'agrement_actif_id')
    def _compute_need_agrement(self):
        for rec in self:
            rec.need_agrement = (
                rec.client_type in AGREMENT_TYPES
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
        if self.nature_id:
            if 'physique' in self.nature_id.name.lower():
                self.nature_client = 'physique'
            else:
                self.nature_client = 'morale'
        else:
            self.nature_client = False

    @api.onchange('nature_client')
    def _onchange_nature_client(self):
        pass

    # ── Validation métier ─────────────────────────────────────────────────
    def _verifier_dossier_client(self):
        for rec in self:
            if not rec.client_type:
                continue
            erreurs = []
            if rec.nature_client == 'morale':
                if not rec.nrc:
                    erreurs.append('N° RC manquant')
                elif not rec.nrc_valide:
                    erreurs.append('N° RC non validé')
                if not rec.nif:
                    erreurs.append('N.I.F manquant')
                elif not rec.nif_valide:
                    erreurs.append('N.I.F non validé')
                if not rec.nis:
                    erreurs.append('N.I.S manquant')
                elif not rec.nis_valide:
                    erreurs.append('N.I.S non validé')
            elif rec.nature_client == 'physique':
                if not rec.nin:
                    erreurs.append('N° Identification Nationale (NIN) manquant')
            if rec.document_ids:
                manquants = rec.document_ids.filtered(lambda d: d.state != 'fourni')
                if manquants:
                    erreurs.append(
                        f'{len(manquants)} document(s) non fourni(s) : '
                        + ', '.join(manquants.mapped('name'))
                    )
            if rec.client_type in AGREMENT_TYPES and not rec.agrement_actif_id:
                erreurs.append('Agrément actif obligatoire pour ce type de client')
            if erreurs:
                raise ValidationError(
                    'Impossible de sauvegarder ce client :\n\n'
                    + '\n'.join(f'• {e}' for e in erreurs)
                )

    @api.constrains('nrc_valide', 'nif_valide', 'nis_valide', 'dossier_valide')
    def _check_fiscal_avant_validation(self):
        for rec in self:
            if rec.dossier_valide and rec.nature_client == 'morale':
                if not rec.nrc_valide:
                    raise ValidationError('N° RC doit être vérifié avant de valider le dossier.')
                if not rec.nif_valide:
                    raise ValidationError('N.I.F doit être vérifié avant de valider le dossier.')
                if not rec.nis_valide:
                    raise ValidationError('N.I.S doit être vérifié avant de valider le dossier.')

    # ── Génération documents ──────────────────────────────────────────────
    def _generer_documents_templates(self):
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
        if self.nature_client == 'morale':
            manquants   = []
            non_valides = []
            if not self.nrc:
                manquants.append('N° RC')
            elif not self.nrc_valide:
                non_valides.append('N° RC')
            if not self.nif:
                manquants.append('N.I.F')
            elif not self.nif_valide:
                non_valides.append('N.I.F')
            if not self.nis:
                manquants.append('N.I.S')
            elif not self.nis_valide:
                non_valides.append('N.I.S')
            if manquants:
                raise ValidationError(
                    f'Champs obligatoires manquants : {", ".join(manquants)}'
                )
            if non_valides:
                raise ValidationError(
                    f'Validez d\'abord ces champs fiscaux : {", ".join(non_valides)}'
                )
        self.dossier_valide = True

    def action_reinitialiser_dossier(self):
        self.ensure_one()
        self.dossier_valide = False

    def action_creer_agrement(self):
        self.ensure_one()
        agrement_en_cours = self.agrement_ids.filtered(
            lambda a: a.state == 'en_cours'
        )
        if agrement_en_cours:
            raise ValidationError(
                f'❌ Ce client possède déjà un agrément en cours : '
                f'{agrement_en_cours[0].name}.\n'
                f'👉 Veuillez d\'abord le résilier avant d\'en créer un nouveau.'
            )
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

    def action_creer_contrat(self):
        self.ensure_one()
        gica_client = self.env['gica.client'].search(
            [('partner_id', '=', self.id)], limit=1
        )
        if not gica_client:
            raise ValidationError(
                "Ce partenaire n'est pas enregistré comme client GICA."
            )
        return {
            'type':      'ir.actions.act_window',
            'name':      'Créer un contrat',
            'res_model': 'gica.client.contract',
            'view_mode': 'form',
            'target':    'current',
            'context':   {'default_client_id': gica_client.id},
        }

    def action_verifier_nrc(self):
        self.ensure_one()
        return {
            'type':   'ir.actions.act_url',
            'url':    'https://sidjilcom.cnrc.dz/group/sidjilcom/repertoire-des-commercants',
            'target': 'new',
        }

    def action_verifier_nif(self):
        self.ensure_one()
        return {
            'type':   'ir.actions.act_url',
            'url':    'https://www.mfdgi.gov.dz/',
            'target': 'new',
        }

    def action_verifier_nis(self):
        self.ensure_one()
        return {
            'type':   'ir.actions.act_url',
            'url':    'https://www.ons.dz/',
            'target': 'new',
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