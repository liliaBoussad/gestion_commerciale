# -*- coding: utf-8 -*-
from odoo import models, fields


class PricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    a_la_charge_de = fields.Selection([
        ('client', 'A la charge du client'),
        ('scaek',  'A la charge de SCAEK'),
    ], string='A la charge de')