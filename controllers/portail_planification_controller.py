# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from datetime import datetime


class GicaPlanificationPortal(http.Controller):

    # ── Liste des planifications ──────────────────────────────────────────
    @http.route(['/my/gica/planifications'], type='http', auth='user', website=True)
    def portail_planifications(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = partner if partner.is_gica_client else False

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
            'bcgs_disponibles': bcgs_disponibles,
            'peut_planifier':   bool(bcgs_disponibles),
        })

    # ── Formulaire nouvelle planification ─────────────────────────────────
    @http.route(['/my/gica/planifications/nouveau'], type='http', auth='user', website=True)
    def portail_planification_nouveau(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = partner if partner.is_gica_client else False

        if not gica_client:
            return request.redirect('/my/gica/planifications')

        bcgs_disponibles = request.env['gica.commande.globale'].sudo().search([
            ('client_id', '=', gica_client.id),
            ('state', '=', 'en_cours'),
            ('quantity_restante', '>', 0),
        ])
        if not bcgs_disponibles:
            return request.redirect('/my/gica/planifications?erreur=aucun_bcg')

        bcg_selectionne = None
        lignes_bcg = []
        bcg_id = kwargs.get('bcg_id')
        if bcg_id:
            bcg_selectionne = request.env['gica.commande.globale'].sudo().browse(int(bcg_id))
            if (not bcg_selectionne.exists()
                    or bcg_selectionne.client_id.id != gica_client.id
                    or bcg_selectionne.state != 'en_cours'):
                bcg_selectionne = None
            else:
                lignes_bcg = self._get_lignes_bcg(bcg_selectionne)

        return request.render('gestion_commerciale.portail_gica_planification_form', {
            'gica_client':      gica_client,
            'bcgs_disponibles': bcgs_disponibles,
            'bcg_selectionne':  bcg_selectionne,
            'lignes_bcg':       lignes_bcg,
        })

    def _get_lignes_bcg(self, bcg):
        result = []
        for line in bcg.line_ids:
            if line.quantity_restante <= 0:
                continue
            conds = [{
                'id':   line.conditionnement_id.id,
                'name': line.conditionnement_id.name,
            }] if line.conditionnement_id else []
            result.append({
                'product_tmpl_id':       line.product_tmpl_id.id,
                'product_name':          line.product_tmpl_id.name,
                'conditionnement_id':    line.conditionnement_id.id,
                'conditionnement':       line.conditionnement_id.name,
                'quantity_restante':     line.quantity_restante,
                'conditionnements':      conds,
                'conditionnements_json': json.dumps(conds),
            })
        return result

    # ── AJAX : lignes BCG ─────────────────────────────────────────────────
    @http.route(['/my/gica/planifications/lignes_bcg'], type='json', auth='user', website=True)
    def portail_planification_lignes_bcg(self, bcg_id=None, **kwargs):
        if not bcg_id:
            return {'lignes': []}

        partner = request.env.user.partner_id
        gica_client = partner if partner.is_gica_client else False

        if not gica_client:
            return {'lignes': []}

        bcg = request.env['gica.commande.globale'].sudo().browse(int(bcg_id))
        if (not bcg.exists()
                or bcg.client_id.id != gica_client.id
                or bcg.state != 'en_cours'):
            return {'lignes': []}

        return {
            'lignes':          self._get_lignes_bcg(bcg),
            'date_expiration': bcg.date_expiration and bcg.date_expiration.strftime('%d/%m/%Y') or '',
        }

    # ── Soumission POST ───────────────────────────────────────────────────
    @http.route(['/my/gica/planifications/soumettre'], type='http', auth='user',
                website=True, methods=['POST'])
    def portail_planification_soumettre(self, **kwargs):
        partner = request.env.user.partner_id
        gica_client = partner if partner.is_gica_client else False

        if not gica_client:
            return request.redirect('/my/gica/planifications')

        bcg_id = kwargs.get('bcg_id')
        if not bcg_id:
            return request.redirect('/my/gica/planifications/nouveau?erreur=bcg_manquant')

        bcg = request.env['gica.commande.globale'].sudo().browse(int(bcg_id))
        if (not bcg.exists()
                or bcg.client_id.id != gica_client.id
                or bcg.state != 'en_cours'):
            return request.redirect('/my/gica/planifications?erreur=bcg_invalide')

        lines = []
        i = 0
        while True:
            product_id = kwargs.get('product_{}'.format(i))
            if product_id is None:
                break
            cond_id  = kwargs.get('cond_{}'.format(i), '')
            date_str = kwargs.get('date_{}'.format(i), '')
            qty_str  = kwargs.get('qty_{}'.format(i), '0').replace(',', '.')
            rot_str  = kwargs.get('rotation_{}'.format(i), '1')
            try:
                qty = float(qty_str)
            except (ValueError, TypeError):
                qty = 0.0
            try:
                rotation = int(rot_str)
            except (ValueError, TypeError):
                rotation = 1
            if qty > 0 and cond_id and date_str and product_id:
                lines.append((0, 0, {
                    'product_tmpl_id':    int(product_id),
                    'conditionnement_id': int(cond_id),
                    'date_enlevement':    date_str,
                    'quantity_tonne':     qty,
                    'rotation':           rotation,
                }))
            i += 1

        # Vérifier chaque date
        for line_vals in [l[2] for l in lines]:
            date_enl = line_vals.get('date_enlevement')
            if date_enl:
                date_obj = datetime.strptime(date_enl, '%Y-%m-%d').date()
                if date_obj.weekday() in (4, 5):
                    return request.redirect(
                        '/my/gica/planifications/nouveau?bcg_id={}&erreur=date_weekend'.format(bcg_id)
                    )
                periode = request.env['gica.planification.usine'].sudo().search([
                    ('state',      '=',  'confirmee'),
                    ('date_debut', '<=', date_obj),
                    ('date_fin',   '>=', date_obj),
                ], limit=1)
                if periode:
                    return request.redirect(
                        '/my/gica/planifications/nouveau?bcg_id={}&erreur=date_verrouillee'.format(bcg_id)
                    )

        if not lines:
            return request.redirect(
                '/my/gica/planifications/nouveau?bcg_id={}&erreur=lignes_vides'.format(bcg_id)
            )

        observations = kwargs.get('observations', '')
        try:
            planif = request.env['gica.planification.client'].sudo().create({
                'client_id':           gica_client.id,
                'commande_globale_id': bcg.id,
                'source':              'portail',
                'observations':        observations,
                'line_ids':            lines,
            })
            planif.action_soumettre()
        except ValidationError as e:
            err_msg = str(e.args[0]) if e.args else 'validation'
            return request.redirect(
                '/my/gica/planifications/nouveau?bcg_id={}&erreur={}'.format(
                    bcg_id, err_msg[:100]
                )
            )

        return request.redirect(
            '/my/gica/planifications?succes=planif_soumise&ref={}'.format(planif.name)
        )

    # ── Detail d'une planification ────────────────────────────────────────
    @http.route(['/my/gica/planifications/<int:planif_id>'], type='http', auth='user', website=True)
    def portail_planification_detail(self, planif_id, **kwargs):
        partner = request.env.user.partner_id
        gica_client = partner if partner.is_gica_client else False

        if not gica_client:
            return request.render('gestion_commerciale.portail_pas_client_gica')

        planif = request.env['gica.planification.client'].sudo().browse(planif_id)
        if not planif.exists() or planif.client_id.id != gica_client.id:
            return request.redirect('/my/gica/planifications')

        return request.render('gestion_commerciale.portail_gica_planification_detail', {
            'gica_client': gica_client,
            'planif':      planif,
        })