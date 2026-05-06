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
        'data/products_data.xml',
        'data/gica_scoring_category_data.xml',
        'data/gica_classification_data.xml',
        'data/gica_commandes_data.xml',
        'data/gica_planification_sequences.xml',   # ← nouveau Phase 1
        'data/gica_document_type_data.xml',
        'data/gica_client_category_data.xml',

        # Views
        'views/res_partner_views.xml',
        'views/gica_client_views.xml',
        'views/client_contract_views.xml',
        'views/client_agrement_views.xml',
        'views/client_document_views.xml',
        'views/gica_document_type_views.xml',
        'views/gica_client_category_views.xml',
        'views/gica_project_views.xml',
        'views/product_views.xml',
        'views/gica_classification_views.xml',
        'views/gica_scoring_category_views.xml',
        'views/gica_commande_globale_views.xml',
        'views/gica_planification_client_views.xml',  # ← nouveau Phase 1
        'views/gica_planification_usine_views.xml',   # ← nouveau Phase 1
        'views/sale_order_gica_views.xml',
        'views/gica_client_nature_views.xml',

        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}