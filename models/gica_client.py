from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class GicaClient(models.Model):
    _name = 'gica.client'
    _description = 'Client GICA'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']

    AGREMENT_TYPES = ['distributeur', 'conditionneur', 'rev_agree']

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        ondelete='cascade',
        auto_join=True,
    )

    commercial_id = fields.Many2one('res.users', string="Commercial")

    client_type = fields.Selection([
        ('realisation', 'Entreprise de réalisation'),
        ('investisseur', 'Investisseur'),
        ('promoteur', 'Promoteur immobilier'),
        ('transformateur', 'Transformateur'),
        ('broyage', 'Centre de broyage'),
        ('revendeur', 'Revendeur'),
        ('rev_agree', 'Revendeur agréé'),
        ('distributeur', 'Distributeur officiel'),
        ('conditionneur', 'Conditionneur'),
        ('exportateur', 'Exportateur'),
        ('auto_const', 'Auto constructeur'),
        ('autres', 'Autres'),
    ], string='Type client', required=True, tracking=True)

    sale_type = fields.Selection([
        ('comptant', 'Comptant'),
        ('terme', 'Vente à terme'),
    ], string='Type de vente', default='comptant', tracking=True)

    nature_id = fields.Many2one(
        'gica.client.nature',
        string="Nature du client",
        tracking=True,
    )

    # ── Agrément simple ───────────────────────────────────────────────────────
    agrement_number = fields.Char(string="N° Agrément")
    agrement_date_debut = fields.Date(string="Date début agrément")
    agrement_date_fin = fields.Date(string="Date fin agrément")
    agrement_state = fields.Selection([
        ('valide', 'Valide'),
        ('expire', 'Expiré'),
        ('retire', 'Retiré'),
    ], string="État agrément", compute='_compute_agrement_state', store=True)

    # ── Projets ───────────────────────────────────────────────────────────────
    project_id = fields.One2many('gica.project', 'client_id', string="Projets")
    project_line_ids = fields.One2many('gica.project.line', 'client_id', string="Lignes projets")

    # ── Classification ────────────────────────────────────────────────────────
    classification_actuelle_display = fields.Char(
        string='Classification',
        compute='_compute_classification_display',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # COMPUTED
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('agrement_date_fin')
    def _compute_agrement_state(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.agrement_date_fin:
                rec.agrement_state = False
            elif rec.agrement_date_fin >= today:
                rec.agrement_state = 'valide'
            else:
                rec.agrement_state = 'expire'

    @api.depends('partner_id.classification_actuelle')
    def _compute_classification_display(self):
        LABELS = {
            'platinum': 'PLATINUM',
            'gold': 'GOLD',
            'silver': 'SILVER',
            'bronze': 'BRONZE',
            False: 'N/A',
        }
        for rec in self:
            rec.classification_actuelle_display = LABELS.get(
                rec.partner_id.classification_actuelle, 'N/A'
            )

    # ─────────────────────────────────────────────────────────────────────────
    # ONCHANGE
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('agrement_date_debut')
    def _onchange_agrement_date_debut(self):
        if self.agrement_date_debut:
            self.agrement_date_fin = self.agrement_date_debut + relativedelta(years=2)
        else:
            self.agrement_date_fin = False

    @api.onchange('client_type')
    def _onchange_client_type(self):
        # 1. Réinitialiser agrément si non requis
        if self.client_type not in self.AGREMENT_TYPES:
            self.agrement_number = False
            self.agrement_date_debut = False
            self.agrement_date_fin = False

        # 2. Calculer le domain nature selon le type
        if not self.client_type:
            domain = [('type_nature', '=', 'utilise')]
        elif self.client_type in ('realisation', 'investisseur', 'promoteur',
                                  'transformateur', 'broyage', 'revendeur',
                                  'rev_agree', 'distributeur', 'conditionneur',
                                  'exportateur'):
            domain = [
                ('type_nature', '=', 'utilise'),
                ('parent_id', '=', False),
            ]
        elif self.client_type == 'auto_const':
            domain = [
                ('type_nature', '=', 'utilise'),
                ('parent_id.name', '=', 'Cas Particuliers'),
            ]
        elif self.client_type == 'autres':
            domain = [
                ('type_nature', '=', 'utilise'),
                ('parent_id.name', '=', 'Autres Clients'),
            ]
        else:
            domain = [('type_nature', '=', 'utilise')]

        # 3. Vider nature_id si elle ne correspond plus
        if self.nature_id and not self.env['gica.client.nature'].search_count(
            [('id', '=', self.nature_id.id)] + domain
        ):
            self.nature_id = False

        # 4. Retourner le domain à la vue
        return {'domain': {'nature_id': domain}}

    # ─────────────────────────────────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def action_calculer_classification(self):
        self.ensure_one()
        today = fields.Date.today()
        period_end = today
        period_start = today - relativedelta(months=6)
        record = self.env['gica.client.classification'].calculate_client_classification(
            self.id, period_start, period_end
        )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Classification',
            'res_model': 'gica.client.classification',
            'view_mode': 'form',
            'res_id': record.id,
        }
    nature_domain = fields.Char(
    compute='_compute_nature_domain',
)

    @api.depends('client_type')
    def _compute_nature_domain(self):
     for rec in self:
        if rec.client_type in ('realisation', 'investisseur', 'promoteur',
                               'transformateur', 'broyage', 'revendeur',
                               'rev_agree', 'distributeur', 'conditionneur',
                               'exportateur'):
            rec.nature_domain = '[["type_nature","=","utilise"],["parent_id","=",false]]'
        elif rec.client_type == 'auto_const':
            rec.nature_domain = '[["type_nature","=","utilise"],["parent_id.name","=","Cas Particuliers"]]'
        elif rec.client_type == 'autres':
            rec.nature_domain = '[["type_nature","=","utilise"],["parent_id.name","=","Autres Clients"]]'
        else:
            rec.nature_domain = '[["type_nature","=","utilise"]]'

class GicaClientAgrementMixin(models.Model):
    _inherit = 'gica.client'

    AGREMENT_TYPES = ['distributeur', 'conditionneur', 'rev_agree']

    agrement_ids = fields.One2many(
        'gica.client.agrement',
        'client_id',
        string='Agréments',
    )

    agrement_actif_id = fields.Many2one(
        'gica.client.agrement',
        string="Agrément actif",
        compute='_compute_agrement_actif',
        store=True,
    )

    agrement_numero = fields.Char(
        string="N° Agrément",
        related='agrement_actif_id.name',
        readonly=True,
    )

    agrement_expiration = fields.Date(
        string="Expiration agrément",
        related='agrement_actif_id.date_expiration',
        readonly=True,
    )

    agrement_statut = fields.Selection(
        related='agrement_actif_id.state',
        string="Statut agrément",
        readonly=True,
    )

    agrement_count = fields.Integer(
        string="Nombre d'agréments",
        compute='_compute_agrement_count',
    )

    need_agrement = fields.Boolean(
        string="Nécessite un agrément",
        compute='_compute_need_agrement',
        store=True,
    )

    @api.depends('agrement_ids', 'agrement_ids.state')
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

    @api.depends('client_type', 'agrement_ids', 'agrement_ids.state', 'agrement_ids.date_expiration')
    def _compute_need_agrement(self):
        for rec in self:
            rec.need_agrement = (
                rec.client_type in self.AGREMENT_TYPES
                and not rec.agrement_actif_id
            )

    def action_voir_agrements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Agréments',
            'res_model': 'gica.client.agrement',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }

    def action_creer_agrement(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Créer un agrément",
            'res_model': 'gica.client.agrement',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_client_id': self.id},
        }