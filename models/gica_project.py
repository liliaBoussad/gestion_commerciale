# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GicaProject(models.Model):
    _name        = 'gica.project'
    _description = 'Projet client'

    client_id = fields.Many2one(
        'gica.client',
        string="Client",
        ondelete='cascade',
        required=True,
    )
    name = fields.Char(
        string="Nom du projet",
        required=True,
    )
    line_ids = fields.One2many(
        'gica.project.line',
        'project_id',
        string="Produits du projet",
    )
    nb_produits = fields.Integer(
        string="Nb produits",
        compute='_compute_totaux',
        store=True,
    )
    quantity_total = fields.Float(
        string="Quantite totale (T)",
        compute='_compute_totaux',
        store=True,
    )

    @api.depends('line_ids.quantity')
    def _compute_totaux(self):
        for rec in self:
            rec.nb_produits     = len(rec.line_ids)
            rec.quantity_total  = sum(rec.line_ids.mapped('quantity'))


class GicaProjectLine(models.Model):
    _name        = 'gica.project.line'
    _description = 'Produit du projet'
    _order       = 'sequence, id'

    sequence = fields.Integer(default=10)

    client_id = fields.Many2one(
        related='project_id.client_id',
        store=True,
    )
    project_name = fields.Char(
        related='project_id.name',
        string="Nom du projet",
        store=True,
    )
    project_id = fields.Many2one(
        'gica.project',
        string="Projet",
        ondelete="cascade",
        required=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string="Produit",
        required=True,
        domain="[('is_gica_product', '=', True)]",
    )
    product_id = fields.Many2one(
        'product.product',
        string="Variante",
        compute='_compute_product_id',
        store=True,
    )
    conditionnement_id = fields.Many2one(
        'product.attribute.value',
        string="Conditionnement",
        domain="[('attribute_id', '=', 4)]",
        required=True,
    )
    quantity = fields.Float(
        string="Quantite (T)",
        required=True,
    )

    @api.depends('product_tmpl_id', 'conditionnement_id')
    def _compute_product_id(self):
        for rec in self:
            if rec.product_tmpl_id and rec.conditionnement_id:
                variant = rec.product_tmpl_id.product_variant_ids.filtered(
                    lambda v: any(
                        a.attribute_id.id == 4 and
                        a.product_attribute_value_id == rec.conditionnement_id
                        for a in v.product_template_attribute_value_ids
                    )
                )
                rec.product_id = variant[0] if variant else False
            else:
                rec.product_id = False