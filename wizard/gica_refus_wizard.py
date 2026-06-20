# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaRefusLigneWizard(models.TransientModel):
    _name        = 'gica.refus.ligne.wizard'
    _description = 'Wizard de refus de ligne planification'

    ligne_id = fields.Many2one(
        'gica.planification.client.line',
        string='Ligne',
    )

    planning_clinker_id = fields.Many2one(
        'clinker.approbation.wizard.line',
        string='Ligne Clinker',
    )

    motif = fields.Text(
        string='Motif du refus',
        required=True,
    )

    def action_confirmer_refus(self):
        self.ensure_one()
        if not self.motif or not self.motif.strip():
            raise ValidationError('Le motif du refus est obligatoire.')

        if self.planning_clinker_id:
            self.planning_clinker_id.motif_refus = self.motif
            self.planning_clinker_id.planning_id._refuser(self.motif)
            # Recharger le wizard approbation
            wizard_id = self.planning_clinker_id.wizard_id.id
            return {
                'type':      'ir.actions.act_window',
                'res_model': 'clinker.approbation.wizard',
                'res_id':    wizard_id,
                'view_mode': 'form',
                'target':    'new',
            }

        if self.ligne_id:
            self.ligne_id.action_refuser_ligne_avec_motif(self.motif)
            return {
                'type': 'ir.actions.client',
                'tag':  'reload',
            }