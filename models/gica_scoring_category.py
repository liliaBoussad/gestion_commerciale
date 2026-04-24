# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GicaScoringCategory(models.Model):
    """
    Catégorie de scoring GICA — définit les avantages accordés
    à chaque niveau de classification (Section 4.04 du document GICA).

    Niveaux : PLATINUM / GOLD / SILVER / BRONZE

    Avantages applicables :
      - Délai de paiement
      - Modes de paiement autorisés
      - Remise sur volume (Oui/Non)
    """
    _name = 'gica.scoring.category'
    _description = 'Catégorie de Scoring GICA'
    _order = 'score_minimum desc'
    _rec_name = 'name'

    name = fields.Char(string='Nom', required=True)

    niveau = fields.Selection([
        ('platinum', 'PLATINUM'),
        ('gold',     'GOLD'),
        ('silver',   'SILVER'),
        ('bronze',   'BRONZE'),
    ], string='Niveau', required=True)

    score_minimum = fields.Float(
        string='Score Minimum',
        required=True,
        help='Score minimum pour accéder à cette catégorie.',
    )

    # ── 1. Délai de paiement ──────────────────────────────────────────────
    delai_paiement = fields.Integer(
        string='Délai de paiement (jours)',
        default=0,
        help='0 = paiement immédiat/anticipé | 15 = Gold | 30 = Platinum',
    )

    paiement_anticipe = fields.Boolean(
        string='Paiement anticipé requis',
        default=False,
        help='Silver et Bronze : le client doit payer avant l\'enlèvement.',
    )

    # ── 2. Modes de paiement autorisés ────────────────────────────────────
    mode_cheque_certifie  = fields.Boolean(string='Chèque certifié',   default=True)
    mode_cheque_ordinaire = fields.Boolean(string='Chèque ordinaire',  default=False)
    mode_virement         = fields.Boolean(string='Virement bancaire', default=True)
    mode_lettre_change    = fields.Boolean(string='Lettre de change',  default=False)
    mode_versement        = fields.Boolean(string='Versement bancaire',default=True)
    mode_cib              = fields.Boolean(string='Paiement CIB',      default=True)

    modes_paiement_display = fields.Char(
        string='Modes de règlement autorisés',
        compute='_compute_modes_paiement_display',
        store=True,
    )

    # ── 3. Remise sur volume ──────────────────────────────────────────────
    remise_volume = fields.Boolean(
        string='Remise sur volume',
        default=True,
        help='Selon objectifs de volume trimestriels.',
    )

    description = fields.Text(string='Description')

    # ── Computed ───────────────────────────────────────────────────────────

    @api.depends(
        'mode_cheque_certifie', 'mode_cheque_ordinaire', 'mode_virement',
        'mode_lettre_change', 'mode_versement', 'mode_cib',
    )
    def _compute_modes_paiement_display(self):
        for rec in self:
            modes = []
            if rec.mode_cheque_certifie:  modes.append('Chèque certifié')
            if rec.mode_cheque_ordinaire: modes.append('Chèque ordinaire')
            if rec.mode_virement:         modes.append('Virement')
            if rec.mode_lettre_change:    modes.append('Lettre de change')
            if rec.mode_versement:        modes.append('Versement')
            if rec.mode_cib:              modes.append('CIB')
            rec.modes_paiement_display = ', '.join(modes) if modes else 'Aucun'

    # ── Contraintes ────────────────────────────────────────────────────────

    @api.constrains('niveau')
    def _check_unique_niveau(self):
        for rec in self:
            others = self.search([('niveau', '=', rec.niveau), ('id', '!=', rec.id)])
            if others:
                raise ValidationError(
                    f'Une catégorie pour le niveau {rec.niveau.upper()} existe déjà.'
                )

    @api.constrains('score_minimum')
    def _check_score_minimum(self):
        for rec in self:
            if rec.score_minimum < 0:
                raise ValidationError('Le score minimum ne peut pas être négatif.')

    # ── Helper ─────────────────────────────────────────────────────────────

    @api.model
    def get_category_for_niveau(self, niveau):
        """Retourne la catégorie correspondant à un niveau de classification."""
        return self.search([('niveau', '=', niveau)], limit=1)