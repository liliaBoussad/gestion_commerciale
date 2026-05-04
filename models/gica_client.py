# -*- coding: utf-8 -*-
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class GicaClient(models.Model):
    _name        = 'gica.client'
    _description = 'Client GICA'
    _inherits    = {'res.partner': 'partner_id'}
    _inherit     = ['mail.thread', 'mail.activity.mixin']

    AGREMENT_TYPES = ['distributeur', 'conditionneur', 'rev_agree']

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        ondelete='cascade',
        auto_join=True,
    )

    # ── Projets ───────────────────────────────────────────────────────────
    project_id = fields.One2many(
        'gica.project', 'client_id', string='Projets',
    )

    # ── Nature domain ─────────────────────────────────────────────────────
    nature_domain = fields.Char(
        compute='_compute_nature_domain',
    )

    # ── Classification display ────────────────────────────────────────────
    classification_actuelle_display = fields.Char(
        string='Classification',
        compute='_compute_classification_display',
    )

    # ─────────────────────────────────────────────────────────────────────
    # COMPUTED
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('partner_id.client_type')
    def _compute_nature_domain(self):
        for rec in self:
            ct = rec.partner_id.client_type
            if ct in ('realisation', 'investisseur', 'promoteur',
                      'transformateur', 'broyage', 'revendeur',
                      'rev_agree', 'distributeur', 'conditionneur',
                      'exportateur'):
                rec.nature_domain = '[["type_nature","=","utilise"],["parent_id","=",false]]'
            elif ct == 'auto_const':
                rec.nature_domain = '[["type_nature","=","utilise"],["parent_id.name","=","Cas Particuliers"]]'
            elif ct == 'autres':
                rec.nature_domain = '[["type_nature","=","utilise"],["parent_id.name","=","Autres Clients"]]'
            else:
                rec.nature_domain = '[["type_nature","=","utilise"]]'

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

    # ─────────────────────────────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────────────────────────────

    def action_calculer_classification(self):
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