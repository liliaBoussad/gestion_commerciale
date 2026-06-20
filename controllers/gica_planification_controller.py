# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class GicaPlanificationController(http.Controller):

    @http.route(
        '/gica/periodes_verrouillees',
        type='json',
        auth='user',
        methods=['POST'],
    )
    def periodes_verrouillees(self, **kwargs):
        """
        Retourne la liste des périodes usine confirmées (verrouillées).
        Appelé par le widget JS pour griser les dates interdites dans le datepicker.
        """
        periodes = request.env['gica.planification.usine'].search([
            ('state', '=', 'confirmee'),
            ('date_debut', '!=', False),
            ('date_fin',   '!=', False),
        ])
        return [
            {
                'from': p.date_debut.isoformat(),
                'to':   p.date_fin.isoformat(),
                'name': p.name,
            }
            for p in periodes
        ]