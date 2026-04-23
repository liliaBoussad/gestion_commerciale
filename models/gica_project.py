from odoo import models, fields

class GicaProject(models.Model):
    _name = 'gica.project'
    _description = 'Projet client'

    client_id = fields.Many2one(
        'gica.client',
        string="Client",
        ondelete='cascade'
    )

    name = fields.Char(
        string="Nom du projet",
        required=True
    )

    line_ids = fields.One2many(
        'gica.project.line',
        'project_id',
        string="Produits du projet"
    )

    




class GicaProjectLine(models.Model):
    _name = 'gica.project.line'
    _description = 'Produit du projet'

    client_id = fields.Many2one(
    related='project_id.client_id',
    store=True
    )

    project_name = fields.Char(
    related='project_id.name',
    string="Nom du projet",
    store=True
    )

    project_id = fields.Many2one(
        'gica.project',
        string="Projet",
        ondelete="cascade"
    )

    product_id = fields.Many2one(
        'product.product',
        string="Produit",
        required=True
    )

    quantity = fields.Float(
        string="Quantité"
    )

    unite_mesure = fields.Selection([
        ('sac50', 'Sac 50 kg'),
        ('sac25', 'Sac 25 kg'),
        ('vrac', 'Vrac'),
        ('bigbag2t', 'Big Bag 2 tonnes'),
        ('fardeau60', 'Fardeau 60 sacs')
    ], string="Unité")