# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError


class GicaBcgPortal(http.Controller):

    # ── Liste des BCG ─────────────────────────────────────────────────────
    @http.route(['/my/gica/bcg'], type='http', auth='user', website=True)
    def portail_gica_bcg(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        bcgs = request.env['gica.commande.globale'].sudo().search(
            [('client_id', '=', gica_client.id)],
            order='date_commande desc',
        )

        contrats_avec_bcg_actif = request.env['gica.commande.globale'].sudo().search(
            [
                ('client_id', '=', gica_client.id),
                ('state', 'not in', ['annulee', 'cloturee']),
            ]
        ).mapped('contrat_id').ids

        contrats_disponibles = request.env['gica.client.contract'].sudo().search(
            [
                ('client_id', '=', gica_client.id),
                ('state', 'in', ['actif', 'en_cours']),
                ('id', 'not in', contrats_avec_bcg_actif),
            ]
        )

        return request.render('gestion_commerciale.portail_gica_bcg', {
            'gica_client':          gica_client,
            'bcgs':                 bcgs,
            'contrats_disponibles': contrats_disponibles,
            'peut_creer_bcg':       bool(contrats_disponibles),
        })

    # ── Formulaire creation BCG ───────────────────────────────────────────
    @http.route(['/my/gica/bcg/nouveau'], type='http', auth='user', website=True)
    def portail_gica_bcg_nouveau(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.redirect('/my/gica/bcg')

        contrats_avec_bcg_actif = request.env['gica.commande.globale'].sudo().search(
            [
                ('client_id', '=', gica_client.id),
                ('state', 'not in', ['annulee', 'cloturee']),
            ]
        ).mapped('contrat_id').ids

        contrats_disponibles = request.env['gica.client.contract'].sudo().search(
            [
                ('client_id', '=', gica_client.id),
                ('state', 'in', ['actif', 'en_cours']),
                ('id', 'not in', contrats_avec_bcg_actif),
            ]
        )

        if not contrats_disponibles:
            return request.redirect('/my/gica/bcg?erreur=aucun_contrat')

        contrat_selectionne = None
        lignes_avec_conds = []
        contrat_id = kwargs.get('contrat_id')
        if contrat_id:
            contrat_selectionne = request.env['gica.client.contract'].sudo().browse(
                int(contrat_id)
            )
            if (not contrat_selectionne.exists()
                    or contrat_selectionne.client_id.id != gica_client.id
                    or contrat_selectionne.state not in ('actif', 'en_cours')):
                contrat_selectionne = None
            else:
                lignes_avec_conds = self._get_lignes_avec_conds(contrat_selectionne)

        return request.render('gestion_commerciale.portail_gica_bcg_form', {
            'gica_client':          gica_client,
            'contrats_disponibles': contrats_disponibles,
            'contrat_selectionne':  contrat_selectionne,
            'lignes_avec_conds':    lignes_avec_conds,
        })

    def _get_lignes_avec_conds(self, contrat):
        """Retourne les lignes du contrat avec les conditionnements disponibles par produit."""
        result = []
        for line in contrat.line_ids:
            tmpl = line.product_tmpl_id
            # Conditionnements disponibles = ceux des variantes existantes de ce produit
            conds = []
            seen_ids = set()
            for variant in tmpl.product_variant_ids:
                for ptav in variant.product_template_attribute_value_ids:
                    if (ptav.attribute_id.id == 4
                            and ptav.product_attribute_value_id.id not in seen_ids):
                        seen_ids.add(ptav.product_attribute_value_id.id)
                        conds.append({
                            'id':   ptav.product_attribute_value_id.id,
                            'name': ptav.product_attribute_value_id.name,
                        })
            result.append({
                'product_tmpl_id': tmpl.id,
                'product_name':    tmpl.name,
                'quantity_tonne':  line.quantity_tonne,
                'conditionnements': conds,
            })
        return result

    # ── AJAX : lignes du contrat selectionne ─────────────────────────────
    @http.route(['/my/gica/bcg/lignes_contrat'], type='json', auth='user', website=True)
    def portail_gica_bcg_lignes(self, contrat_id=None, **kwargs):
        if not contrat_id:
            return {'lignes': []}

        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return {'lignes': []}

        contrat = request.env['gica.client.contract'].sudo().browse(int(contrat_id))
        if (not contrat.exists()
                or contrat.client_id.id != gica_client.id
                or contrat.state not in ('actif', 'en_cours')):
            return {'lignes': []}

        lignes = self._get_lignes_avec_conds(contrat)

        mode_label = dict(
            contrat._fields['mode_paiement'].selection
        ).get(contrat.mode_paiement, '') if contrat.mode_paiement else ''

        return {
            'lignes':          lignes,
            'date_expiration': contrat.date_end and contrat.date_end.strftime('%d/%m/%Y') or '',
            'mode_paiement':   mode_label,
        }
# ── Detail d'un BCG ───────────────────────────────────────────────────
    @http.route(['/my/gica/bcg/<int:bcg_id>'], type='http', auth='user', website=True)
    def portail_gica_bcg_detail(self, bcg_id, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        bcg = request.env['gica.commande.globale'].sudo().browse(bcg_id)
        if (not bcg.exists()
                or bcg.client_id.id != gica_client.id):
            return request.redirect('/my/gica/bcg')

        return request.render('gestion_commerciale.portail_gica_bcg_detail', {
            'gica_client': gica_client,
            'bcg':         bcg,
        })


    # ── Soumission POST ───────────────────────────────────────────────────
    @http.route(['/my/gica/bcg/soumettre'], type='http', auth='user',
                website=True, methods=['POST'])
    def portail_gica_bcg_soumettre(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = request.env['gica.client'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not gica_client:
            return request.redirect('/my/gica/bcg')

        contrat_id = kwargs.get('contrat_id')
        if not contrat_id:
            return request.redirect('/my/gica/bcg/nouveau?erreur=contrat_manquant')

        contrat = request.env['gica.client.contract'].sudo().browse(int(contrat_id))
        if (not contrat.exists()
                or contrat.client_id.id != gica_client.id
                or contrat.state not in ('actif', 'en_cours')):
            return request.redirect('/my/gica/bcg?erreur=contrat_invalide')

        existing = request.env['gica.commande.globale'].sudo().search([
            ('contrat_id', '=', contrat.id),
            ('state', 'not in', ['annulee', 'cloturee']),
        ], limit=1)
        if existing:
            return request.redirect('/my/gica/bcg?erreur=bcg_existant')

        lines = []
        for line in contrat.line_ids:
            pid = line.product_tmpl_id.id
            qty_str = kwargs.get('qty_{}'.format(pid), '0').replace(',', '.')
            cond_id = kwargs.get('cond_{}'.format(pid), '')

            try:
                qty = float(qty_str)
            except (ValueError, TypeError):
                qty = 0.0

            if qty <= 0 or not cond_id:
                continue

            if qty > line.quantity_tonne:
                qty = line.quantity_tonne

            lines.append((0, 0, {
                'product_tmpl_id':    pid,
                'conditionnement_id': int(cond_id),
                'quantity_tonne':     qty,
                'prix_unitaire':      0.0,
            }))

        if not lines:
            return request.redirect(
                '/my/gica/bcg/nouveau?contrat_id={}&erreur=lignes_vides'.format(contrat_id)
            )

        observations = kwargs.get('observations', '')
        try:
            bcg = request.env['gica.commande.globale'].sudo().create({
                'client_id':    gica_client.id,
                'contrat_id':   contrat.id,
                'state':        'soumis',
                'observations': observations,
                'line_ids':     lines,
            })
            bcg.message_post(
                body='BCG soumis par le client depuis le portail - en attente de validation commerciale.'
            )
        except ValidationError:
            return request.redirect(
                '/my/gica/bcg/nouveau?contrat_id={}&erreur=validation'.format(contrat_id)
            )

        return request.redirect('/my/gica/bcg?succes=bcg_soumis&ref={}'.format(bcg.name))