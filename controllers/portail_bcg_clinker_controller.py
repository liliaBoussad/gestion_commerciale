# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError


class GicaBcgClinkerPortal(http.Controller):

    CLIENT_TYPES_CLINKER = ('transformateur', 'broyage', 'exportateur')

    # ── Liste des BCG Clinker ─────────────────────────────────────────────
    @http.route(['/my/gica/bcg-clinker'], type='http', auth='user', website=True)
    def portail_bcg_clinker_liste(self, **kwargs):
        partner = request.env.user.partner_id

        bcgs = request.env['clinker.global.order'].sudo().search(
            [('client_id', '=', partner.id)],
            order='date_commande desc',
        )

        peut_creer = partner.client_type in self.CLIENT_TYPES_CLINKER

        return request.render('gestion_commerciale.portail_gica_bcg_clinker', {
            'partner':    partner,
            'bcgs':       bcgs,
            'peut_creer': peut_creer,
        })

    # ── Detail d'un BCG Clinker ───────────────────────────────────────────
    @http.route(['/my/gica/bcg-clinker/<int:bcg_id>'], type='http', auth='user', website=True)
    def portail_bcg_clinker_detail(self, bcg_id, **kwargs):
        partner = request.env.user.partner_id

        bcg = request.env['clinker.global.order'].sudo().browse(bcg_id)
        if not bcg.exists() or bcg.client_id.id != partner.id:
            return request.redirect('/my/gica/bcg-clinker')

        return request.render('gestion_commerciale.portail_gica_bcg_clinker_detail', {
            'partner': partner,
            'bcg':     bcg,
        })

    # ── Formulaire nouveau BCG Clinker ────────────────────────────────────
    @http.route(['/my/gica/bcg-clinker/nouveau'], type='http', auth='user', website=True)
    def portail_bcg_clinker_nouveau(self, **kwargs):
        partner = request.env.user.partner_id

        if partner.client_type not in self.CLIENT_TYPES_CLINKER:
            return request.redirect('/my/gica/bcg-clinker')

        produits = request.env['product.template'].sudo().search(
            [('type_ciment', '=', 'clinker')]
        )

        return request.render('gestion_commerciale.portail_gica_bcg_clinker_form', {
            'partner':  partner,
            'produits': produits,
        })

    @http.route(['/my/gica/bcg-clinker/soumettre'], type='http', auth='user',
            website=True, methods=['POST'])
    def portail_bcg_clinker_soumettre(self, **kwargs):
        import logging
        _logger = logging.getLogger(__name__)
        
        partner = request.env.user.partner_id
        _logger.info("=== BCG CLINKER SOUMETTRE === partner=%s client_type=%s",
                    partner.id, partner.client_type)

        if partner.client_type not in self.CLIENT_TYPES_CLINKER:
            return request.redirect('/my/gica/bcg-clinker')

        date_expiration = kwargs.get('date_expiration')
        _logger.info("date_expiration=%s kwargs=%s", date_expiration, dict(kwargs))
        
        if not date_expiration:
            return request.redirect('/my/gica/bcg-clinker/nouveau?erreur=date_manquante')

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
            if qty > 0 and product_id:
                lines.append((0, 0, {
                    'product_tmpl_id':    int(product_id),
                    'quantite_autorisee': qty,
                }))
            i += 1

        _logger.info("Total lignes valides: %s", len(lines))

        if not lines:
            return request.redirect(
                '/my/gica/bcg-clinker/nouveau?erreur=lignes_vides'
            )

        try:
            bcg = request.env['clinker.global.order'].sudo().create({
                'client_id':       partner.id,
                'date_expiration': date_expiration,
                'line_ids':        lines,
                'state':           'brouillon',
            })
            _logger.info("BCG cree avec succes: id=%s name=%s", bcg.id, bcg.name)
            bcg.message_post(
                body='Demande BCG Clinker soumise par le client via le portail.'
            )
        except Exception as e:
            _logger.error("ERREUR creation BCG Clinker: %s", str(e))
            return request.redirect(
                '/my/gica/bcg-clinker/nouveau?erreur=validation'
            )

        return request.redirect(
            '/my/gica/bcg-clinker?succes=bcg_soumis&ref={}'.format(bcg.name)
        )