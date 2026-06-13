# -*- coding: utf-8 -*-
{
    'name': 'Gestion commerciale',
    'version': '1.0',
    'summary': 'Gestion des clients GICA',
    'author': 'GICA Project',
    'license': 'LGPL-3', 
    'category': 'Sales',
    'depends': ['base', 'mail', 'sale', 'product', 'sale_management', 'portal'],
    'assets': {
    'web.assets_backend': [
        'gestion_commerciale/static/src/js/date_field_verrouillee.js',
        'gestion_commerciale/static/src/css/date_field_verrouillee.css',
    ],
    },

    'data': [
        'security/ir.model.access.csv',

        # Data
        'data/gica_client_nature_data.xml',
        'data/products_data.xml',
        'data/pricelists_data.xml',
        'data/gica_scoring_category_data.xml',
        'data/gica_classification_data.xml',
        'data/gica_commandes_data.xml',
        'data/gica_planification_sequences.xml',
        'data/gica_document_type_data.xml',
        'data/gica_client_category_data.xml',
        'data/gica_circulation_sequences.xml',
        'data/gica_cron.xml',
          # Rapports — AVANT les vues
        'reports/report_ticket_pesee.xml',
        'reports/report_bon_circulation.xml',
        
        'templates/portal_templates.xml',

        # Views — ordre important !
        'views/gica_client_nature_views.xml',       
        'views/gica_client_category_views.xml',
        'views/res_partner_views.xml',             
        'views/client_contract_views.xml',
        'views/client_agrement_views.xml',
        'views/client_document_views.xml',
        'views/gica_document_type_views.xml',
        'views/gica_project_views.xml',
        'views/product_views.xml',
        'views/gica_classification_views.xml',
        'views/gica_scoring_category_views.xml',
        'views/gica_commande_globale_views.xml',
        'views/gica_planification_client_views.xml',
        'views/gica_planification_usine_views.xml',
        'views/gica_planification_config_views.xml',
        'views/gica_planification_calendar_views.xml',
        'views/avenant.xml',  
        'views/sale_order_gica_views.xml',
        'views/gica_bon_circulation_views.xml',
        'data/clinker_sequences.xml',
        'views/gica_bascule_views.xml',

        # Clinker
        'views/clinker_cadence_views.xml',
        'views/clinker_global_order_views.xml',
        'views/clinker_planning_views.xml',
        'views/clinker_approbation_wizard_views.xml',

        'views/menu.xml',
    ],

    'installable': True,
    'application': True,
}