# -*- coding: utf-8 -*-
from odoo import models, fields


class GicaDocumentType(models.Model):
    _name        = 'gica.document.type'
    _description = 'Documents à fournir — Référentiel GICA'
    _order       = 'section, sequence, name'

    name = fields.Char(
        string='Nom du document', required=True,
    )
    
    section = fields.Selection([
        ('admin', 'Administratif'),
        ('tech',  'Technique'),
    ], string='Type de document', required=True)

    sequence = fields.Integer(default=10)
    active   = fields.Boolean(default=True)