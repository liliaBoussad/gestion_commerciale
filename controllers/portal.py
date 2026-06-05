# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import ValidationError, AccessError


class GicaPortal(CustomerPortal):

    # ── Tableau de bord — compteurs ───────────────────────────────────────
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'bcg_ciment_count' in counters:
            values['bcg_ciment_count'] = request.env['gica.commande.globale'].search_count([
                ('client_id', '=', partner.id)
            ])
        if 'planif_ciment_count' in counters:
            values['planif_ciment_count'] = request.env['gica.planification.client'].search_count([
                ('client_id', '=', partner.id)
            ])
        if 'bcg_clinker_count' in counters:
            values['bcg_clinker_count'] = request.env['clinker.global.order'].search_count([
                ('client_id', '=', partner.id)
            ])
        if 'planif_clinker_count' in counters:
            values['planif_clinker_count'] = request.env['clinker.planning'].search_count([
                ('client_id', '=', partner.id)
            ])
        if 'projet_count' in counters:
            values['projet_count'] = request.env['gica.project'].search_count([
                ('client_id', '=', partner.id)
            ])
        return values

    # ══════════════════════════════════════════════════════════════════════
    # UC2 — PROJETS
    # ══════════════════════════════════════════════════════════════════════

    @http.route(['/my/projets', '/my/projets/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_projets(self, page=1, **kw):
        partner = request.env.user.partner_id
        if partner.client_type != 'realisation':
            return request.redirect('/my')

        domain = [('client_id', '=', partner.id)]
        total = request.env['gica.project'].search_count(domain)
        pager = portal_pager(
            url='/my/projets', total=total, page=page, step=10,
        )
        projets = request.env['gica.project'].search(
            domain, limit=10, offset=pager['offset'], order='id desc'
        )
        return request.render('gestion_commerciale.portal_projets', {
            'projets': projets,
            'pager':   pager,
            'page_name': 'projets',
        })

    @http.route('/my/projets/new', type='http', auth='user', website=True)
    def portal_projet_new(self, **kw):
        partner = request.env.user.partner_id
        if partner.client_type != 'realisation':
            return request.redirect('/my')
        products = request.env['product.product'].search([
            ('product_tmpl_id.is_gica_product', '=', True)
        ])
        return request.render('gestion_commerciale.portal_projet_form', {
            'products': products,
            'page_name': 'projets',
        })

    @http.route('/my/projets/submit', type='http', auth='user', website=True, methods=['POST'])
    def portal_projet_submit(self, **kw):
        partner = request.env.user.partner_id
        try:
            projet = request.env['gica.project'].sudo().create({
                'client_id':  partner.id,
                'name':       kw.get('name'),
                'product_id': int(kw.get('product_id', 0)),
                'quantite_estimee': float(kw.get('quantite_estimee', 0)),
            })
            return request.redirect(f'/my/projets?success=1')
        except Exception as e:
            return request.redirect(f'/my/projets/new?error={str(e)}')

    # ══════════════════════════════════════════════════════════════════════
    # UC3 — BCG CIMENT
    # ══════════════════════════════════════════════════════════════════════

    @http.route(['/my/bcg-ciment', '/my/bcg-ciment/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_bcg_ciment(self, page=1, **kw):
        partner = request.env.user.partner_id
        domain  = [('client_id', '=', partner.id)]
        total   = request.env['gica.commande.globale'].search_count(domain)
        pager   = portal_pager(url='/my/bcg-ciment', total=total, page=page, step=10)
        bcgs    = request.env['gica.commande.globale'].search(
            domain, limit=10, offset=pager['offset'], order='id desc'
        )
        return request.render('gestion_commerciale.portal_bcg_ciment', {
            'bcgs':      bcgs,
            'pager':     pager,
            'page_name': 'bcg_ciment',
        })

    @http.route('/my/bcg-ciment/new', type='http', auth='user', website=True)
    def portal_bcg_ciment_new(self, **kw):
        partner  = request.env.user.partner_id
        contrats = request.env['gica.client.contract'].search([
            ('client_id', '=', partner.id),
            ('state',     '=', 'actif'),
        ])
        if not contrats:
            return request.render('gestion_commerciale.portal_no_contrat', {
                'page_name': 'bcg_ciment',
            })
        products = request.env['product.product'].search([
            ('product_tmpl_id.is_gica_product', '=', True)
        ])
        return request.render('gestion_commerciale.portal_bcg_ciment_form', {
            'contrats': contrats,
            'products': products,
            'page_name': 'bcg_ciment',
        })

    @http.route('/my/bcg-ciment/submit', type='http', auth='user', website=True, methods=['POST'])
    def portal_bcg_ciment_submit(self, **kw):
        partner = request.env.user.partner_id
        try:
            bcg = request.env['gica.commande.globale'].sudo().create({
                'client_id':  partner.id,
                'contrat_id': int(kw.get('contrat_id', 0)),
                'date_commande': kw.get('date_commande'),
                'date_expiration': kw.get('date_expiration'),
                'line_ids': [(0, 0, {
                    'product_id':     int(kw.get('product_id', 0)),
                    'quantity_tonne': float(kw.get('quantity_tonne', 0)),
                })],
            })
            return request.redirect('/my/bcg-ciment?success=1')
        except Exception as e:
            return request.redirect(f'/my/bcg-ciment/new?error={str(e)}')

    # ══════════════════════════════════════════════════════════════════════
    # UC3 — BCG CLINKER
    # ══════════════════════════════════════════════════════════════════════

    @http.route(['/my/bcg-clinker', '/my/bcg-clinker/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_bcg_clinker(self, page=1, **kw):
        partner = request.env.user.partner_id
        domain  = [('client_id', '=', partner.id)]
        total   = request.env['clinker.global.order'].search_count(domain)
        pager   = portal_pager(url='/my/bcg-clinker', total=total, page=page, step=10)
        bcgs    = request.env['clinker.global.order'].search(
            domain, limit=10, offset=pager['offset'], order='id desc'
        )
        return request.render('gestion_commerciale.portal_bcg_clinker', {
            'bcgs':      bcgs,
            'pager':     pager,
            'page_name': 'bcg_clinker',
        })

    @http.route('/my/bcg-clinker/new', type='http', auth='user', website=True)
    def portal_bcg_clinker_new(self, **kw):
        partner  = request.env.user.partner_id
        contrats = request.env['gica.client.contract'].search([
            ('client_id', '=', partner.id),
            ('state',     '=', 'actif'),
        ])
        if not contrats:
            return request.render('gestion_commerciale.portal_no_contrat', {
                'page_name': 'bcg_clinker',
            })
        products = request.env['product.product'].search([
            ('product_tmpl_id.type_ciment', '=', 'clinker')
        ])
        return request.render('gestion_commerciale.portal_bcg_clinker_form', {
            'contrats': contrats,
            'products': products,
            'page_name': 'bcg_clinker',
        })

    @http.route('/my/bcg-clinker/submit', type='http', auth='user', website=True, methods=['POST'])
    def portal_bcg_clinker_submit(self, **kw):
        partner = request.env.user.partner_id
        try:
            bcg = request.env['clinker.global.order'].sudo().create({
                'client_id':       partner.id,
                'date_commande':   kw.get('date_commande'),
                'date_expiration': kw.get('date_expiration'),
                'ref_bon_commande': kw.get('ref_bon_commande', ''),
                'line_ids': [(0, 0, {
                    'product_id':         int(kw.get('product_id', 0)),
                    'quantite_autorisee': float(kw.get('quantite_autorisee', 0)),
                })],
            })
            return request.redirect('/my/bcg-clinker?success=1')
        except Exception as e:
            return request.redirect(f'/my/bcg-clinker/new?error={str(e)}')

    # ══════════════════════════════════════════════════════════════════════
    # UC4 — PLANIFICATION CIMENT
    # ══════════════════════════════════════════════════════════════════════

    @http.route(['/my/planif-ciment', '/my/planif-ciment/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_planif_ciment(self, page=1, **kw):
        partner = request.env.user.partner_id
        domain  = [('client_id', '=', partner.id)]
        total   = request.env['gica.planification.client'].search_count(domain)
        pager   = portal_pager(url='/my/planif-ciment', total=total, page=page, step=10)
        planifs = request.env['gica.planification.client'].search(
            domain, limit=10, offset=pager['offset'], order='id desc'
        )
        return request.render('gestion_commerciale.portal_planif_ciment', {
            'planifs':   planifs,
            'pager':     pager,
            'page_name': 'planif_ciment',
        })

    @http.route('/my/planif-ciment/new', type='http', auth='user', website=True)
    def portal_planif_ciment_new(self, **kw):
        partner = request.env.user.partner_id
        bcgs    = request.env['gica.commande.globale'].search([
            ('client_id', '=', partner.id),
            ('state',     '=', 'en_cours'),
        ])
        return request.render('gestion_commerciale.portal_planif_ciment_form', {
            'bcgs':      bcgs,
            'page_name': 'planif_ciment',
        })

    @http.route('/my/planif-ciment/submit', type='http', auth='user', website=True, methods=['POST'])
    def portal_planif_ciment_submit(self, **kw):
        partner = request.env.user.partner_id
        try:
            planif = request.env['gica.planification.client'].sudo().create({
                'client_id':        partner.id,
                'commande_globale_id': int(kw.get('commande_globale_id', 0)),
                'date_enlevement':  kw.get('date_enlevement'),
                'source':           'portail',
            })
            return request.redirect('/my/planif-ciment?success=1')
        except Exception as e:
            return request.redirect(f'/my/planif-ciment/new?error={str(e)}')

    # ══════════════════════════════════════════════════════════════════════
    # UC4 — PLANIFICATION CLINKER
    # ══════════════════════════════════════════════════════════════════════

    @http.route(['/my/planif-clinker', '/my/planif-clinker/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_planif_clinker(self, page=1, **kw):
        partner = request.env.user.partner_id
        domain  = [('client_id', '=', partner.id)]
        total   = request.env['clinker.planning'].search_count(domain)
        pager   = portal_pager(url='/my/planif-clinker', total=total, page=page, step=10)
        planifs = request.env['clinker.planning'].search(
            domain, limit=10, offset=pager['offset'], order='id desc'
        )
        return request.render('gestion_commerciale.portal_planif_clinker', {
            'planifs':   planifs,
            'pager':     pager,
            'page_name': 'planif_clinker',
        })

    @http.route('/my/planif-clinker/new', type='http', auth='user', website=True)
    def portal_planif_clinker_new(self, **kw):
        partner = request.env.user.partner_id
        bcgs    = request.env['clinker.global.order'].search([
            ('client_id', '=', partner.id),
            ('state',     '=', 'actif'),
        ])
        return request.render('gestion_commerciale.portal_planif_clinker_form', {
            'bcgs':      bcgs,
            'page_name': 'planif_clinker',
        })

    @http.route('/my/planif-clinker/submit', type='http', auth='user', website=True, methods=['POST'])
    def portal_planif_clinker_submit(self, **kw):
        partner = request.env.user.partner_id
        try:
            planif = request.env['clinker.planning'].sudo().create({
                'bcg_id':           int(kw.get('bcg_id', 0)),
                'date_chargement':  kw.get('date_chargement'),
                'estimation':       float(kw.get('estimation', 0)),
            })
            return request.redirect('/my/planif-clinker?success=1')
        except Exception as e:
            return request.redirect(f'/my/planif-clinker/new?error={str(e)}')

    # ══════════════════════════════════════════════════════════════════════
    # UC5 — HISTORIQUE
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/my/historique', type='http', auth='user', website=True)
    def portal_historique(self, **kw):
        partner = request.env.user.partner_id
        bcgs_ciment  = request.env['gica.commande.globale'].search([
            ('client_id', '=', partner.id)
        ], order='id desc', limit=10)
        bcgs_clinker = request.env['clinker.global.order'].search([
            ('client_id', '=', partner.id)
        ], order='id desc', limit=10)
        planifs_ciment  = request.env['gica.planification.client'].search([
            ('client_id', '=', partner.id)
        ], order='id desc', limit=10)
        planifs_clinker = request.env['clinker.planning'].search([
            ('client_id', '=', partner.id)
        ], order='id desc', limit=10)

        return request.render('gestion_commerciale.portal_historique', {
            'bcgs_ciment':     bcgs_ciment,
            'bcgs_clinker':    bcgs_clinker,
            'planifs_ciment':  planifs_ciment,
            'planifs_clinker': planifs_clinker,
            'page_name':       'historique',
        })