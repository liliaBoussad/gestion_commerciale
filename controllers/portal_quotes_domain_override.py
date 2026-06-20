# -*- coding: utf-8 -*-
from odoo.addons.sale.controllers.portal import CustomerPortal as SaleCustomerPortal


class GicaSaleCustomerPortal(SaleCustomerPortal):

    def _prepare_quotations_domain(self, partner):
        """Etend le domaine natif pour inclure tous les devis GICA
        du client, quel que soit leur etat (draft, sent), au lieu
        de se limiter aux devis envoyes avec follower."""
        domain = super()._prepare_quotations_domain(partner)
        # Domaine natif : message_partner_ids + state = 'sent'
        # On le remplace par : partner_id direct + state in draft/sent
        return [
            '|',
            ('partner_id', '=', partner.id),
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ['draft', 'sent']),
        ]