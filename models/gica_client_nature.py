from odoo import models, fields, api


class GicaClientNature(models.Model):
    _name = 'gica.client.nature'
    _description = 'Nature des clients GICA'
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(string='Nom', required=True)

    complete_name = fields.Char(
        string='Nom complet',
        compute='_compute_complete_name',
        store=True,
        recursive=True,
    )

    parent_id = fields.Many2one(
        'gica.client.nature',
        string='Nature parente',
        ondelete='cascade',
        index=True
    )

    child_ids = fields.One2many(
        'gica.client.nature',
        'parent_id',
        string='Sous-natures'
    )
    
    nature_id = fields.Many2one(
        'gica.client.nature',
        string='Nature du client',
        domain="[('type_nature', '=', 'utilise')]",
    )

    type_nature = fields.Selection([
        ('vue', 'Vue'),
        ('utilise', 'Utilisé'),
    ], string='Type de Nature', default='utilise', required=True)

    est_filiale_gica = fields.Boolean(string='Est une filiale de GICA', default=False)
    est_don_charite = fields.Boolean(string='Est un don/charité', default=False)

    nis_obligatoire = fields.Boolean(string='NIS Obligatoire', default=False)
    nif_obligatoire = fields.Boolean(string='NIF Obligatoire', default=False)
    ai_obligatoire = fields.Boolean(string='AI Obligatoire', default=False)
    rc_obligatoire = fields.Boolean(string='RC Obligatoire', default=False)
    nin_obligatoire = fields.Boolean(string='NIN Obligatoire', default=False)
    rib_obligatoire = fields.Boolean(string='RIB Obligatoire', default=False)
    swift_obligatoire = fields.Boolean(string='SWIFT Obligatoire', default=False)

    document_ids = fields.Many2many(
        'gica.document.template',
        'nature_document_rel',
        'nature_id',
        'document_id',
        string='Documents à fournir'
    )

    active = fields.Boolean(default=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_name = f"{rec.parent_id.complete_name} / {rec.name}"
            else:
                rec.complete_name = rec.name