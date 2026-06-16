# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import logging
_logger = logging.getLogger(__name__)
class GicaCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if gica_client:
            values['devis_count'] = request.env['sale.order'].sudo().search_count([
                ('gica_client_id', '=', gica_client.id),
                ('state', 'in', ['draft', 'sent', 'sale']),
                ('commande_globale_id', '=', False),
            ])
            values['contract_count'] = request.env['gica.client.contract'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            )
            values['bcg_count'] = request.env['gica.commande.globale'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            )
            values['planification_count'] = request.env['gica.planification.client'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            )
            values['project_count'] = request.env['gica.project'].sudo().search_count(
                [('client_id', '=', gica_client.id)]
            
            )
            
            values['is_entreprise_realisation'] = gica_client.client_type == 'realisation'
        else:
            values.update({
                'devis_count': 0,
                'contract_count': 0,
                'bcg_count': 0,
                'planification_count': 0,
                'project_count': 0,
                'is_entreprise_realisation': False,
            })
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

        nb_contrats = request.env['gica.client.contract'].sudo().search_count(
            [('client_id', '=', gica_client.id)]
        )
        nb_bcgs = request.env['gica.commande.globale'].sudo().search_count(
            [('client_id', '=', gica_client.id)]
        )
        nb_planifications = request.env['gica.planification.client'].sudo().search_count(
            [('client_id', '=', gica_client.id)]
        )
        nb_projets = request.env['gica.project'].sudo().search_count(
            [('client_id', '=', gica_client.id)]
        )
        nb_devis = request.env['sale.order'].sudo().search_count([
            '|',
            ('gica_client_id', '=', gica_client.id),
            ('partner_id', '=', gica_client.partner_id.id),
            ('state', 'in', ['draft', 'sent', 'sale']),
            ('commande_globale_id', '=', False),
        ])

        bcgs = request.env['gica.commande.globale'].sudo().search(
            [('client_id', '=', gica_client.id)]
        )
        contrats = request.env['gica.client.contract'].sudo().search(
            [('client_id', '=', gica_client.id)]
        )
        contrats_avec_bcg = bcgs.filtered(
            lambda b: b.state not in ['annulee', 'cloturee']
        ).mapped('contrat_id').ids
        bcgs_disponibles_pour_creation = contrats.filtered(
            lambda c: c.state in ['actif', 'en_cours']
            and c.id not in contrats_avec_bcg
        )
        bcgs_en_cours = bcgs.filtered(
            lambda b: b.state == 'en_cours' and b.quantity_restante > 0
        )

        return request.render('gestion_commerciale.portail_gica_accueil', {
            'gica_client':                    gica_client,
            'nb_contrats':                    nb_contrats,
            'nb_bcgs':                        nb_bcgs,
            'nb_planifications':              nb_planifications,
            'nb_projets':                     nb_projets,
            'nb_devis':                       nb_devis,
            'bcgs_disponibles_pour_creation': bcgs_disponibles_pour_creation,
            'bcgs_en_cours':                  bcgs_en_cours,
        })

    # ── Devis ─────────────────────────────────────────────────────────────

    @http.route(['/my/gica/devis'], type='http', auth='user', website=True)
    def portail_gica_devis(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        devis = request.env['sale.order'].sudo().search([
            '|',
            ('gica_client_id', '=', gica_client.id),
            ('partner_id', '=', gica_client.partner_id.id),
            ('state', 'in', ['draft', 'sent', 'sale', 'cancel']),
            ('commande_globale_id', '=', False),
        ], order='id desc')

        return request.render('gestion_commerciale.portail_gica_devis', {
            'gica_client': gica_client,
            'devis':       devis,
        })

    # ── Projets ───────────────────────────────────────────────────────────
# ── Liste des projets ─────────────────────────────────────────────────
    @http.route(['/my/gica/projets'], type='http', auth='user', website=True)
    def portail_gica_projets(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')
        
        if gica_client.client_type != 'realisation':
            return request.redirect('/my/home')

        projets = request.env['gica.project'].sudo().search(
            [('client_id', '=', gica_client.id)]
        )
        return request.render('gestion_commerciale.portail_gica_projets', {
            'gica_client': gica_client,
            'projets':     projets,
        })

    # ── Detail d'un projet ────────────────────────────────────────────────
    @http.route(['/my/gica/projets/<int:projet_id>'], type='http', auth='user', website=True)
    def portail_gica_projet_detail(self, projet_id, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')
        
        if gica_client.client_type != 'realisation':
            return request.redirect('/my/home')

        projet = request.env['gica.project'].sudo().browse(projet_id)
        if (not projet.exists()
                or projet.client_id.id != gica_client.id):
            return request.redirect('/my/gica/projets')

        return request.render('gestion_commerciale.portail_gica_projet_detail', {
            'gica_client': gica_client,
            'projet':      projet,
        })

    # ── Formulaire nouveau projet ─────────────────────────────────────────



    @http.route(['/my/gica/projets/nouveau'], type='http', auth='user', website=True)
    def portail_gica_projet_nouveau(self, **kwargs):
        if request.httprequest.method == 'POST':
            partner = request.env.user.partner_id
            gica_client = request.env['gica.client'].sudo().search(
                [('partner_id', '=', partner.id)], limit=1
            )
            _logger.info("=== CREATION PROJET === partner=%s gica_client=%s kwargs=%s",
                        partner.id, gica_client.id if gica_client else None, dict(kwargs))

            if not gica_client:
                _logger.warning("Pas de gica_client trouve pour partner_id=%s", partner.id)
                return request.redirect('/my/gica/projets?erreur=pas_client')

            if gica_client.client_type != 'realisation':
                _logger.warning("Client %s n'est pas de type realisation (type=%s)",
                                gica_client.id, gica_client.client_type)
                return request.redirect('/my/home')

            lines = []
            i = 0
            while True:
                product_id = kwargs.get('product_{}'.format(i))
                if product_id is None:
                    break
                qty_str = kwargs.get('qty_{}'.format(i), '0').replace(',', '.')
                try:
                    qty = float(qty_str)
                except (ValueError, TypeError):
                    qty = 0.0
                _logger.info("Ligne %s: product_id=%s qty=%s", i, product_id, qty)
                if product_id and qty > 0:
                    lines.append((0, 0, {
                        'product_tmpl_id': int(product_id),
                        'quantity':        qty,
                    }))
                i += 1

            _logger.info("Total lignes valides: %s", len(lines))

            if not lines:
                _logger.warning("Aucune ligne valide, redirection avec erreur")
                return request.redirect('/my/gica/projets/nouveau?erreur=lignes_vides')

            try:
                projet = request.env['gica.project'].sudo().create({
                    'client_id': gica_client.id,
                    'name':      kwargs.get('name'),
                    'line_ids':  lines,
                })
                _logger.info("Projet cree avec succes: id=%s name=%s", projet.id, projet.name)
            except Exception as e:
                _logger.error("ERREUR creation projet: %s", str(e))
                return request.redirect('/my/gica/projets/nouveau?erreur=creation_echec')

            return request.redirect('/my/gica/projets')

        # GET — afficher le formulaire
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client or gica_client.client_type != 'realisation':
            return request.redirect('/my/home')

        produits = []
        produits_raw = request.env['product.template'].sudo().search(
            [('is_gica_product', '=', True)]
        )
        for tmpl in produits_raw:
            conds = []
            seen = set()
            for variant in tmpl.product_variant_ids:
                for ptav in variant.product_template_attribute_value_ids:
                    if (ptav.attribute_id.id == 4
                            and ptav.product_attribute_value_id.id not in seen):
                        seen.add(ptav.product_attribute_value_id.id)
                        conds.append({
                            'id':   ptav.product_attribute_value_id.id,
                            'name': ptav.product_attribute_value_id.name,
                        })
            if conds:
                produits.append({
                    'tmpl_id': tmpl.id,
                    'name':    tmpl.name,
                    'conds':   conds,
                })

        return request.render('gestion_commerciale.portail_gica_projet_form', {
            'produits': produits,
        })
    # ── Planifications ────────────────────────────────────────────────────

    @http.route(['/my/gica/planifications'], type='http', auth='user', website=True)
    def portail_gica_planifications(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        planifications = request.env['gica.planification.client'].sudo().search(
            [('client_id', '=', gica_client.id)],
            order='name desc',
        )
        bcgs_disponibles = request.env['gica.commande.globale'].sudo().search([
            ('client_id', '=', gica_client.id),
            ('state', '=', 'en_cours'),
            ('quantity_restante', '>', 0),
        ])
        return request.render('gestion_commerciale.portail_gica_planifications', {
            'gica_client':      gica_client,
            'planifications':   planifications,
            'peut_planifier':   bool(bcgs_disponibles),
        })

    # ── Contrats ──────────────────────────────────────────────────────────

    # ── Liste des contrats ────────────────────────────────────────────────
    @http.route(['/my/gica/contrats'], type='http', auth='user', website=True)
    def portail_gica_contrats(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        contrats = request.env['gica.client.contract'].sudo().search(
            [('client_id', '=', gica_client.id)],
            order='date_start desc',
        )
        return request.render('gestion_commerciale.portail_gica_contrats', {
            'gica_client': gica_client,
            'contrats':    contrats,
        })

    # ── Detail d'un contrat ───────────────────────────────────────────────
    @http.route(['/my/gica/contrats/<int:contrat_id>'], type='http', auth='user', website=True)
    def portail_gica_contrat_detail(self, contrat_id, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        contrat = request.env['gica.client.contract'].sudo().browse(contrat_id)
        if (not contrat.exists()
                or contrat.client_id.id != gica_client.id):
            return request.redirect('/my/gica/contrats')

        return request.render('gestion_commerciale.portail_gica_contrat_detail', {
            'gica_client': gica_client,
            'contrat':     contrat,
        })
    @http.route(['/my/gica/devis/demande'], type='http', auth='user', website=True)
    def portail_devis_demande(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')
        produits = request.env['product.template'].sudo().search(
            [('is_gica_product', '=', True)]
        )
        return request.render('gestion_commerciale.portail_gica_devis_demande', {
            'gica_client': gica_client,
            'produits':    produits,
        })

    @http.route(['/my/gica/devis/conditionnements'], type='json', auth='user', website=True)
    def portail_devis_conditionnements(self, product_tmpl_id=None, **kwargs):
        if not product_tmpl_id:
            return {'conditionnements': []}
        tmpl = request.env['product.template'].sudo().browse(int(product_tmpl_id))
        if not tmpl.exists() or not tmpl.is_gica_product:
            return {'conditionnements': []}
        conds = []
        seen = set()
        for variant in tmpl.product_variant_ids:
            for ptav in variant.product_template_attribute_value_ids:
                if (ptav.attribute_id.id == 4
                        and ptav.product_attribute_value_id.id not in seen):
                    seen.add(ptav.product_attribute_value_id.id)
                    conds.append({
                        'id':   ptav.product_attribute_value_id.id,
                        'name': ptav.product_attribute_value_id.name,
                    })
        return {'conditionnements': conds}

    @http.route(['/my/gica/devis/soumettre'], type='http', auth='user',
                website=True, methods=['POST'])
    def portail_devis_soumettre(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.redirect('/my/quotes')
        lines = []
        i = 0
        while True:
            product_id = kwargs.get('product_{}'.format(i))
            if product_id is None:
                break
            cond_id = kwargs.get('cond_{}'.format(i), '')
            qty_str = kwargs.get('qty_{}'.format(i), '0').replace(',', '.')
            try:
                qty = float(qty_str)
            except (ValueError, TypeError):
                qty = 0.0
            if qty > 0 and cond_id and product_id:
                tmpl = request.env['product.template'].sudo().browse(int(product_id))
                cond = request.env['product.attribute.value'].sudo().browse(int(cond_id))
                variant = tmpl.product_variant_ids.filtered(
                    lambda v: any(
                        a.attribute_id.id == 4 and
                        a.product_attribute_value_id.id == cond.id
                        for a in v.product_template_attribute_value_ids
                    )
                )
                if variant:
                    lines.append((0, 0, {
                        'product_id':      variant[0].id,
                        'product_uom_qty': qty,
                        'price_unit':      variant[0].lst_price,
                        'name':            variant[0].display_name,
                    }))
            i += 1
        if not lines:
            return request.redirect('/my/gica/devis/demande?erreur=lignes_vides')
        observations = kwargs.get('observations', '')
        order = request.env['sale.order'].sudo().create({
            'partner_id':     partner.id,
            'gica_client_id': gica_client.id,
            'note':           observations,
            'order_line':     lines,
        })
        return request.redirect('/my/quotes?succes=devis_soumis&ref={}'.format(order.name))