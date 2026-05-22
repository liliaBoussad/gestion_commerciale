# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClinkerApprobationWizardLine(models.TransientModel):
    _name        = 'clinker.approbation.wizard.line'
    _description = 'Ligne Wizard Approbation Clinker'

    wizard_id = fields.Many2one(
        'clinker.approbation.wizard',
        string='Wizard',
        ondelete='cascade',
    )

    planning_id = fields.Many2one(
        'clinker.planning',
        string='Planification',
        readonly=True,
    )

    client_id = fields.Many2one(
        related='planning_id.client_id',
        string='Client',
        readonly=True,
    )

    bcg_id = fields.Many2one(
        related='planning_id.bcg_id',
        string='BCG',
        readonly=True,
    )

    estimation = fields.Float(
        related='planning_id.estimation',
        string='Estimation (T)',
        readonly=True,
    )

    quantite_approuvee = fields.Float(
        string='Quantité Approuvée (T)',
    )

    action = fields.Selection([
        ('approuver', 'Approuver'),
        ('refuser',   'Refuser'),
    ], string='Action', default='approuver')

    motif_refus = fields.Char(string='Motif de Refus')

    dans_cadence = fields.Boolean(
        string='Dans cadence',
        readonly=True,
    )

    # AJOUT : déjà approuvé ce jour
    deja_approuve = fields.Boolean(
        string='Déjà approuvé',
        readonly=True,
    )


class ClinkerApprobationWizard(models.TransientModel):
    _name        = 'clinker.approbation.wizard'
    _description = 'Wizard Approbation Planning Clinker'

    date_approbation = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
    )

    cadence_id = fields.Many2one(
        'clinker.cadence',
        string='Cadence active',
        readonly=True,
    )

    cadence_quantite  = fields.Float(string='Cadence (T/jour)', readonly=True)
    cadence_min       = fields.Float(string='Min (T)',          readonly=True)
    cadence_max       = fields.Float(string='Max (T)',          readonly=True)

    # AJOUT : capacité restante du jour
    capacite_utilisee = fields.Float(string='Déjà approuvé ce jour (T)', readonly=True)
    capacite_restante = fields.Float(string='Capacité restante (T)',      readonly=True)

    total_demande  = fields.Float(
        string='Total demandé (T)',
        compute='_compute_totaux',
        readonly=True,
    )
    total_approuve = fields.Float(
        string='Total approuvé (T)',
        compute='_compute_totaux',
        readonly=True,
    )
    taux_utilisation = fields.Float(
        string='Utilisation (%)',
        compute='_compute_totaux',
        readonly=True,
    )
    alerte_80 = fields.Boolean(
        string='Alerte 80%',
        compute='_compute_totaux',
        readonly=True,
    )

    line_ids = fields.One2many(
        'clinker.approbation.wizard.line',
        'wizard_id',
        string='Planifications',
    )

    @api.depends('line_ids.estimation', 'line_ids.quantite_approuvee', 'cadence_quantite', 'capacite_utilisee')
    def _compute_totaux(self):
        for rec in self:
            rec.total_demande  = sum(rec.line_ids.mapped('estimation'))
            rec.total_approuve = sum(rec.line_ids.mapped('quantite_approuvee'))
            total_jour = rec.capacite_utilisee + rec.total_approuve
            if rec.cadence_quantite > 0:
                rec.taux_utilisation = (total_jour / rec.cadence_quantite) * 100
            else:
                rec.taux_utilisation = 0.0
            rec.alerte_80 = rec.taux_utilisation >= 80

    def action_charger_planifications(self):
        self.ensure_one()

        # Vérifier cadence active pour cette date
        cadence = self.env['clinker.cadence'].get_cadence_active(self.date_approbation)
        if not cadence:
            raise ValidationError(
                '❌ Aucune cadence active pour cette date.\n'
                '👉 Créez et validez une cadence avant d\'approuver.'
            )

        # CORRECTION : tenir compte des planifs déjà approuvées ce jour
        deja_approuvees = self.env['clinker.planning'].search([
            ('date_chargement', '=', self.date_approbation),
            ('state',           '=', 'approuve'),
        ])
        capacite_utilisee = sum(deja_approuvees.mapped('quantite_approuvee'))
        capacite_restante = max(0.0, cadence.quantite_max - capacite_utilisee)

        # Charger planifications soumises du jour — FIFO
        planifications = self.env['clinker.planning'].search([
            ('date_chargement', '=', self.date_approbation),
            ('state',           '=', 'soumis'),
        ], order='id asc')

        if not planifications:
            raise ValidationError(
                f'❌ Aucune planification soumise pour le {self.date_approbation}.'
            )

        lines = []
        cumul = 0.0

        for planif in planifications:
            cumul += planif.estimation
            reste = max(0.0, capacite_restante - (cumul - planif.estimation))
            qte_approuvee = min(planif.estimation, reste)
            dans_cadence = (capacite_utilisee + cumul) <= cadence.quantite_max

            lines.append((0, 0, {
                'planning_id':        planif.id,
                'quantite_approuvee': qte_approuvee,
                'action':             'approuver' if qte_approuvee > 0 else 'refuser',
                'dans_cadence':       dans_cadence,
                'deja_approuve':      False,
            }))

        self.write({
            'cadence_id':        cadence.id,
            'cadence_quantite':  cadence.quantite,
            'cadence_min':       cadence.quantite_min,
            'cadence_max':       cadence.quantite_max,
            'capacite_utilisee': capacite_utilisee,
            'capacite_restante': capacite_restante,
            'line_ids':          [(5, 0, 0)] + lines,
        })

        return {
            'type':      'ir.actions.act_window',
            'res_model': 'clinker.approbation.wizard',
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
        }

    def action_valider(self):
        self.ensure_one()
        if not self.line_ids:
            raise ValidationError('❌ Chargez d\'abord les planifications.')

        for line in self.line_ids:
            if line.action == 'approuver':
                if line.quantite_approuvee <= 0:
                    raise ValidationError(
                        f'❌ Quantité approuvée doit être > 0 pour {line.planning_id.name}.'
                    )
                line.planning_id._approuver(line.quantite_approuvee)
            else:
                motif = line.motif_refus or 'Dépassement de cadence'
                line.planning_id._refuser(motif)

        return {'type': 'ir.actions.act_window_close'}