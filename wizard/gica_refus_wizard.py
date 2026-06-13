# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaRefusLigneWizard(models.TransientModel):
    _name        = 'gica.refus.ligne.wizard'
    _description = 'Wizard de refus de ligne planification'

    ligne_id = fields.Many2one(
        'gica.planification.client.line',
        string='Ligne',
        required=True,
    )
    motif = fields.Text(
        string='Motif du refus',
        required=True,
    )

    def action_confirmer_refus(self):
        self.ensure_one()
        if not self.motif or not self.motif.strip():
            raise ValidationError('❌ Le motif du refus est obligatoire.')
        self.ligne_id.action_refuser_ligne_avec_motif(self.motif)
        return {
            'type': 'ir.actions.client',
            'tag':  'reload',
        }