from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class GicaClient(models.Model):
    _name = 'gica.client'
    _description = 'Client GICA'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']

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



    # ── Agrément ──────────────────────────────────────────────────────────────
    agrement_number = fields.Char(string="N° Agrément")
    agrement_date_debut = fields.Date(string="Date début agrément")
    agrement_date_fin = fields.Date(string="Date fin agrément")
    agrement_state = fields.Selection([
        ('valide', 'Valide'),
        ('expire', 'Expiré'),
        ('retire', 'Retiré'),
    ], string="État agrément", compute='_compute_agrement_state', store=True)

    # Types de clients nécessitant un agrément
    AGREMENT_TYPES = ['distributeur', 'conditionneur', 'rev_agree']

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

    @api.onchange('agrement_date_debut')
    def _onchange_agrement_date_debut(self):
        """Calcule automatiquement la date de fin à +2 ans."""
        if self.agrement_date_debut:
            self.agrement_date_fin = self.agrement_date_debut + relativedelta(years=2)
        else:
            self.agrement_date_fin = False

    @api.onchange('client_type')
    def _onchange_client_type(self):
        """Réinitialise les champs agrément si le type ne le requiert pas."""
        if self.client_type not in self.AGREMENT_TYPES:
            self.agrement_number = False
            self.agrement_date_debut = False
            self.agrement_date_fin = False

    # ── Projets ───────────────────────────────────────────────────────────────
    project_id = fields.One2many(
    'gica.project',
    'client_id',
    string="Projets"
    )

    project_line_ids = fields.One2many(
    'gica.project.line',
    'client_id',   # ← à ajouter dans GicaProjectLine
    string="Projets"
    )

   




# ── À ajouter dans la classe GicaClient de gica_client.py ────────────────
# Colle ces deux blocs juste avant la ligne :
#   class GicaClientAgrementMixin(models.Model):

    # Champ affichage classification dans le smart button
    classification_actuelle_display = fields.Char(
        string='Classification',
        compute='_compute_classification_display',
    )

    @api.depends('partner_id.classification_actuelle')
    def _compute_classification_display(self):
        LABELS = {
            'platinum': 'PLATINUM',
            'gold':     'GOLD',
            'silver':   'SILVER',
            'bronze':   'BRONZE',
            False:      'N/A',
        }
        for rec in self:
            rec.classification_actuelle_display = LABELS.get(
                rec.partner_id.classification_actuelle, 'N/A'
            )

    def action_calculer_classification(self):
        """
        Bouton dans la fiche gica.client :
        Calcule la classification pour les 6 derniers mois
        et ouvre l'enregistrement créé.
        """
        from dateutil.relativedelta import relativedelta
        self.ensure_one()
        today        = fields.Date.today()
        period_end   = today
        period_start = today - relativedelta(months=6)

        record = self.env['gica.client.classification'].calculate_client_classification(
            self.id, period_start, period_end
        )

        return {
            'type':      'ir.actions.act_window',
            'name':      'Classification',
            'res_model': 'gica.client.classification',
            'view_mode': 'form',
            'res_id':    record.id,
        }
##########

 # ── Nature du client ──────────────────────────────────────────────────────
        # ── Nature du client ──────────────────────────────────────────────────────
    nature_id = fields.Many2one(
        'gica.client.nature',
        string="Nature du client",
        tracking=True,
    )

    # Filtrage dynamique selon le type de client
    @api.onchange('client_type')
    def _onchange_client_type_nature(self):
        """Filtre automatiquement les natures compatibles selon le type client"""
        if not self.client_type:
            domain = [('type_nature', '=', 'utilise')]
        elif self.client_type in ('realisation', 'investisseur', 'promoteur', 'transformateur',
                                  'broyage', 'revendeur', 'rev_agree', 'distributeur',
                                  'conditionneur', 'exportateur'):
            # Standard : Personne Morale + Personne Physique
            domain = [
                ('type_nature', '=', 'utilise'),
                ('parent_id', '=', False)
            ]
        elif self.client_type == 'auto_const':
            # Seulement Auto-constructeurs
            domain = [
                ('type_nature', '=', 'utilise'),
                ('parent_id.name', '=', 'Cas Particuliers'),
                ('name', '=', 'Auto-constructeurs')
            ]
        elif self.client_type == 'autres':
            # Sous "Autres Clients"
            domain = [
                ('type_nature', '=', 'utilise'),
                ('parent_id.name', '=', 'Autres Clients')
            ]
        else:
            domain = [('type_nature', '=', 'utilise')]

        # Réinitialise la nature si elle n'est plus valide
        if self.nature_id and not self.env['gica.client.nature'].search_count(
            [('id', '=', self.nature_id.id)] + domain
        ):
            self.nature_id = False

   

   # ─────────────────────────────────────────────────────────────────────────────
# À AJOUTER à la fin de gica_client.py
# Héritage gica.client — lien avec les agréments
# ─────────────────────────────────────────────────────────────────────────────
class GicaClientAgrementMixin(models.Model):
    _inherit = 'gica.client'

    # Types de clients qui nécessitent un agrément
    AGREMENT_TYPES = ['distributeur', 'conditionneur', 'rev_agree']

    agrement_ids = fields.One2many(
        'gica.client.agrement',
        'client_id',
        string='Agréments',
    )

    # Agrément actif courant (le plus récent actif)
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
            'type':      'ir.actions.act_window',
            'name':      'Agréments',
            'res_model': 'gica.client.agrement',
            'view_mode': 'list,form',
            'domain':    [('client_id', '=', self.id)],
            'context':   {'default_client_id': self.id},
        }

    def action_creer_agrement(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      "Créer un agrément",
            'res_model': 'gica.client.agrement',
            'view_mode': 'form',
            'target':    'new',
            'context':   {'default_client_id': self.id},
        }