{
    'name': 'Gestion commerciale',
    'version': '1.0',
    'summary': 'Gestion des clients GICA',
    'author': 'GICA Project',
    'category': 'Sales',
    'depends': ['base', 'mail','product'],
    'data': [
        'security/ir.model.access.csv',
        'data/products_data.xml',
        'views/gica_client_views.xml',  
        'views/client_contract_views.xml', 
        'views/client_agrement_views.xml',  
        'views/client_document_views.xml',  
        'views/gica_project_views.xml',
        'views/product_views.xml',
        'views/menu.xml',                    
  
    ],
    'installable': True,
    'application': True,
}