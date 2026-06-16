# -*- coding: utf-8 -*-
{
    'name': 'Gestion commerciale',
    'version': '1.0',
    'summary': 'Gestion des clients GICA',
    'author': 'GICA Project',
    'category': 'Sales',
    'depends': ['base', 'mail', 'sale', 'product', 'sale_management', 'portal'],
    'data': [
        'security/ir.model.access.csv',

        # Data
        'data/gica_client_nature_data.xml',
        
        'data/gica_scoring_category_data.xml',
        'data/gica_classification_data.xml',
        'data/gica_commandes_data.xml',
        'data/gica_planification_sequences.xml',
       
        'data/gica_document_type_data.xml',
        'data/gica_client_category_data.xml',
        'data/gica_pricelists_data.xml',

        # Views — ordre important !
        'views/gica_client_nature_views.xml',       
        'views/gica_client_category_views.xml',
        'views/gica_client_views.xml',
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
        'views/sale_order_gica_views.xml',
        'views/gica_avenant_views.xml',
        'views/gica_pricelist_config_views.xml',
       
       

        'views/menu.xml',
         # Portail
        'templates/portail_gica.xml',
         'templates/portal_quotations_inherit.xml',
        'templates/portal_sale_hide_actions.xml',
        'templates/portal_my_home_sale_remove_alert.xml',
        'templates/portail_bcg_templates.xml',
        'templates/portail_planification_templates.xml',
        'templates/portail_devis_demande_template.xml',
        
        'wizard/gica_refus_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
}