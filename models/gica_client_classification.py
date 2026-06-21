# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class GicaClientClassification(models.Model):
    _name = 'gica.client.classification'
    _description = 'Classification Client GICA'
    _order = 'date_classification desc'
    _rec_name = 'partner_id'

    # ── Identité ──────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        ondelete='cascade',
        domain=[('is_gica_client', '=', True)],
    )
    date_classification = fields.Date(
        string='Date classification', required=True, default=fields.Date.today,
    )
    period_start = fields.Date(string='Début période', required=True)
    period_end   = fields.Date(string='Fin période',   required=True)
    nb_mois      = fields.Integer(string='Nombre de mois')

    config_x = fields.Monetary(string='X utilisé', currency_field='currency_id')
    config_y = fields.Monetary(string='Y utilisé', currency_field='currency_id')

    score_ca          = fields.Float(string='Score CA (/ 40)')
    score_paiement    = fields.Float(string='Score Paiement (/ 30)')
    score_enlevement  = fields.Float(string='Score Enlèvement (/ 20)')
    score_exclusivite = fields.Float(string='Score Exclusivité (/ 10)')
    score_total = fields.Float(
        string='Score Total (/ 100)',
        compute='_compute_score_total', store=True,
    )

    classification = fields.Selection(
        [('platinum', 'PLATINUM'), ('gold', 'GOLD'),
         ('silver', 'SILVER'),    ('bronze', 'BRONZE')],
        string='Niveau',
        compute='_compute_classification', store=True,
    )

    ca_total         = fields.Monetary(string='CA Total',         currency_field='currency_id')
    ca_mensuel_moyen = fields.Monetary(string='CA Mensuel Moyen', currency_field='currency_id')

    montant_facture        = fields.Monetary(string='Montant Facturé',        currency_field='currency_id')
    montant_paye_a_temps   = fields.Monetary(string='Montant Payé à Temps',   currency_field='currency_id')
    paiement_mensuel_moyen = fields.Monetary(string='Paiement Mensuel Moyen', currency_field='currency_id')
    taux_paiement = fields.Float(
        string='Taux Paiement (%)', compute='_compute_taux_paiement', store=True,
    )

    total_bc           = fields.Integer(string='Total BC')
    bc_enleves_a_temps = fields.Integer(string='BC Enlevés à Temps')
    taux_enlevement = fields.Float(
        string='Taux Enlèvement (%)', compute='_compute_taux_enlevement', store=True,
    )

    exclusivite_gica = fields.Boolean(
        string='Exclusivité GICA',
        related='partner_id.exclusivite_gica', store=True,
    )

    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id,
    )
    note = fields.Text(string='Notes')

    # ── Computes ──────────────────────────────────────────────────────────

    @api.depends('score_ca', 'score_paiement', 'score_enlevement', 'score_exclusivite')
    def _compute_score_total(self):
        for rec in self:
            rec.score_total = (
                rec.score_ca + rec.score_paiement
                + rec.score_enlevement + rec.score_exclusivite
            )

    @api.depends('score_total')
    def _compute_classification(self):
        config = self.env['gica.classification.config'].search(
            [('active', '=', True)], limit=1
        )
        seuil_platinum = config.seuil_platinum if config else 90.0
        seuil_gold     = config.seuil_gold     if config else 75.0
        seuil_silver   = config.seuil_silver   if config else 50.0

        for rec in self:
            if rec.score_total >= seuil_platinum:
                rec.classification = 'platinum'
            elif rec.score_total >= seuil_gold:
                rec.classification = 'gold'
            elif rec.score_total >= seuil_silver:
                rec.classification = 'silver'
            else:
                rec.classification = 'bronze'

    @api.depends('montant_facture', 'montant_paye_a_temps')
    def _compute_taux_paiement(self):
        for rec in self:
            rec.taux_paiement = (
                (rec.montant_paye_a_temps / rec.montant_facture) * 100
                if rec.montant_facture else 0.0
            )

    @api.depends('total_bc', 'bc_enleves_a_temps')
    def _compute_taux_enlevement(self):
        for rec in self:
            rec.taux_enlevement = (
                (rec.bc_enleves_a_temps / rec.total_bc) * 100
                if rec.total_bc else 0.0
            )

    # ── Helpers ───────────────────────────────────────────────────────────

    @api.model
    def _get_nb_mois(self, period_start, period_end):
        delta = relativedelta(period_end, period_start)
        return max(delta.years * 12 + delta.months, 1)

    # ── Calcul principal ──────────────────────────────────────────────────

    @api.model
    def calculate_client_classification(self, partner_id, period_start, period_end):
        config  = self.env['gica.classification.config'].get_active_config()
        partner = self.env['res.partner'].browse(partner_id)
        X       = config.seuil_ca_par_point
        Y       = config.seuil_paiement_par_point
        nb_mois = self._get_nb_mois(period_start, period_end)

        # 1. Score CA — 40 pts max
        bcgs = self.env['gica.commande.globale'].search([
            ('client_id',    '=',       partner_id),
            ('date_commande','>=',      period_start),
            ('date_commande','<=',      period_end),
            ('state',        'not in', ['annulee']),
        ])
        ca_total         = sum(bcgs.mapped('montant_total'))
        ca_mensuel_moyen = ca_total / nb_mois
        score_ca         = min(ca_mensuel_moyen / X, 40.0) if X else 0.0

        # 2. Score Paiement — 30 pts max
        # TODO : remplacer par les données réelles de account.move
        montant_facture        = ca_total
        montant_paye_a_temps   = ca_total * 0.9
        paiement_mensuel_moyen = montant_paye_a_temps / nb_mois
        score_paiement         = min(paiement_mensuel_moyen / Y, 30.0) if Y else 0.0

        # 3. Score Enlèvement — 20 pts max
        bons_circulation = self.env['gica.bon.circulation'].search([
            ('partner_id', '=', partner_id),
            ('state',      '=', 'termine'),
        ])
        bons_periode = bons_circulation.filtered(
            lambda b: (
                b.sale_order_id
                and b.sale_order_id.date_prevue_enlevement
                and period_start <= b.sale_order_id.date_prevue_enlevement <= period_end
            )
        )
        total_bc    = len(bons_periode)
        tolerance   = timedelta(days=config.tolerance_enlevement_jours)
        bc_enleves_a_temps = len(bons_periode.filtered(
            lambda b: (
                b.sale_order_id.date_reelle_enlevement
                and b.sale_order_id.date_prevue_enlevement
                and b.sale_order_id.date_reelle_enlevement
                    <= b.sale_order_id.date_prevue_enlevement + tolerance
            )
        ))
        taux_enl         = (bc_enleves_a_temps / total_bc) if total_bc else 0.0
        score_enlevement = round(taux_enl * 20.0, 2)

        # 4. Score Exclusivité — 10 pts max
        score_exclusivite = 10.0 if partner.exclusivite_gica else 0.0

        vals = {
            'partner_id':             partner_id,
            'date_classification':    fields.Date.today(),
            'period_start':           period_start,
            'period_end':             period_end,
            'nb_mois':                nb_mois,
            'config_x':               X,
            'config_y':               Y,
            'score_ca':               score_ca,
            'score_paiement':         score_paiement,
            'score_enlevement':       score_enlevement,
            'score_exclusivite':      score_exclusivite,
            'ca_total':               ca_total,
            'ca_mensuel_moyen':       ca_mensuel_moyen,
            'montant_facture':        montant_facture,
            'montant_paye_a_temps':   montant_paye_a_temps,
            'paiement_mensuel_moyen': paiement_mensuel_moyen,
            'total_bc':               total_bc,
            'bc_enleves_a_temps':     bc_enleves_a_temps,
        }

        existing = self.search([
            ('partner_id',   '=', partner_id),
            ('period_start', '=', period_start),
            ('period_end',   '=', period_end),
        ], limit=1)

        if existing:
            existing.write(vals)
            record = existing
        else:
            record = self.create(vals)

        partner.write({
            'classification_actuelle':      record.classification,
            'score_actuel':                 record.score_total,
            'date_derniere_classification': fields.Date.today(),
        })

        return record

    # ── Actions ───────────────────────────────────────────────────────────

    def action_recalculer(self):
        """Recalcule la classification sur la même période que l'enregistrement."""
        self.ensure_one()
        self.calculate_client_classification(
            self.partner_id.id, self.period_start, self.period_end
        )

    @api.model
    def action_reclassifier_en_masse(self, partner_ids):
        """Appelé depuis l'action serveur sur la liste des contacts."""
        config       = self.env['gica.classification.config'].get_active_config()
        today        = fields.Date.today()
        period_end   = today
        period_start = today - relativedelta(months=config.periode_mois)

        for pid in partner_ids:
            self.calculate_client_classification(pid, period_start, period_end)

        return {'type': 'ir.actions.act_window_close'}

    # ── Cron ──────────────────────────────────────────────────────────────

    @api.model
    def cron_classify_all_clients(self):
        config       = self.env['gica.classification.config'].get_active_config()
        today        = fields.Date.today()
        period_end   = today
        period_start = today - relativedelta(months=config.periode_mois)
        seuil_date   = today - relativedelta(weeks=config.frequence_cron_semaines)

        clients = self.env['res.partner'].search([
            ('is_gica_client', '=', True),
            '|',
            ('date_derniere_classification', '=',  False),
            ('date_derniere_classification', '<=', seuil_date),
        ])

        for partner in clients:
            has_contracts = self.env['gica.client.contract'].search_count([
                ('client_id',  '=',  partner.id),
                ('date_start', '<=', period_end),
                ('date_end',   '>=', period_start),
                ('state', 'in', ['actif', 'en_cours', 'expire']),
            ])
            if has_contracts:
                self.calculate_client_classification(
                    partner.id, period_start, period_end
                )

        return True