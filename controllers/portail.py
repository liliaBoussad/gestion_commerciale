# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class GicaCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )

        if 'contract_count' in counters:
            values['contract_count'] = request.env['gica.client.contract'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            ) if gica_client else 0

        if 'bcg_count' in counters:
            values['bcg_count'] = request.env['gica.commande.globale'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            ) if gica_client else 0

        if 'planification_count' in counters:
            values['planification_count'] = request.env['gica.planification.client'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            ) if gica_client else 0

        if 'project_count' in counters:
            values['project_count'] = request.env['gica.project'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            ) if gica_client else 0

        return values

    # ── Dashboard ─────────────────────────────────────────────────────────
    @http.route(['/my/gica'], type='http', auth='user', website=True)
    def portail_gica_accueil(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        contrats = request.env['gica.client.contract'].sudo().search(
            [('client_id', '=', gica_client.id)]
        )
        bcgs = request.env['gica.commande.globale'].sudo().search(
            [('client_id', '=', gica_client.id)]
        )
        planifications = request.env['gica.planification.client'].sudo().search(
            [('client_id', '=', gica_client.id)]
        )
        projets = request.env['gica.project'].sudo().search(
            [('client_id', '=', gica_client.id)]
        )

        return request.render('gestion_commerciale.portail_gica_accueil', {
            'gica_client':    gica_client,
            'contrats':       contrats,
            'bcgs':           bcgs,
            'planifications': planifications,
            'projets':        projets,
        })

    # ── Projets ───────────────────────────────────────────────────────────
    @http.route(['/my/gica/projets'], type='http', auth='user', website=True)
    def portail_gica_projets(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        projets = request.env['gica.project'].sudo().search(
            [('client_id', '=', gica_client.id)]
        ) if gica_client else []

        return request.render('gestion_commerciale.portail_gica_projets', {
            'gica_client': gica_client,
            'projets':     projets,
        })

    @http.route(['/my/gica/projets/nouveau'], type='http', auth='user', website=True)
    def portail_gica_projet_nouveau(self, **kwargs):
        if request.httprequest.method == 'POST':
            partner = request.env.user.partner_id
            gica_client = request.env['gica.client'].sudo().search(
                [('partner_id', '=', partner.id)], limit=1
            )
            if gica_client:
                request.env['gica.project'].sudo().create({
                    'client_id': gica_client.id,
                    'name':      kwargs.get('name'),
                })
            return request.redirect('/my/gica/projets')

        return request.render('gestion_commerciale.portail_gica_projet_form', {})

    # ── Planifications ────────────────────────────────────────────────────
    @http.route(['/my/gica/planifications'], type='http', auth='user', website=True)
    def portail_gica_planifications(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        planifications = request.env['gica.planification.client'].sudo().search(
            [('client_id', '=', gica_client.id)]
        ) if gica_client else []

        return request.render('gestion_commerciale.portail_gica_planifications', {
            'gica_client':    gica_client,
            'planifications': planifications,
        })

    # ── Contrats ──────────────────────────────────────────────────────────
    @http.route(['/my/gica/contrats'], type='http', auth='user', website=True)
    def portail_gica_contrats(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        contrats = request.env['gica.client.contract'].sudo().search(
            [('client_id', '=', gica_client.id)]
        ) if gica_client else []

        return request.render('gestion_commerciale.portail_gica_contrats', {
            'gica_client': gica_client,
            'contrats':    contrats,
        })

    # ── BCG ───────────────────────────────────────────────────────────────
    @http.route(['/my/gica/bcg'], type='http', auth='user', website=True)
    def portail_gica_bcg(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        bcgs = request.env['gica.commande.globale'].sudo().search(
            [('client_id', '=', gica_client.id)]
        ) if gica_client else []

        return request.render('gestion_commerciale.portail_gica_bcg', {
            'gica_client': gica_client,
            'bcgs':        bcgs,
        })