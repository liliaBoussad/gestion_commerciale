# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GicaPlanificationConfig(models.Model):
    _name        = 'gica.planification.config'
    _description = 'Configuration Planification GICA'

    name = fields.Char(
        string='Nom',
        default='Configuration Planification',
        readonly=True,
    )
    heure_cron = fields.Integer(
        string='Heure de récupération automatique',
        default=3,
        help='Heure (0-23) à laquelle le système récupère automatiquement les planifications soumises.',
    )
    actif = fields.Boolean(
        string='Récupération automatique activée',
        default=True,
    )
    nb_jours_periode = fields.Integer(
        string='Durée de la période (jours)',
        default=14,
        help='Nombre de jours couverts par chaque planification usine.',
    )

    @api.model
    def get_config(self):
        """Retourne la configuration active ou en crée une par défaut."""
        config = self.search([], limit=1)
        if not config:
            config = self.create({})
        return config