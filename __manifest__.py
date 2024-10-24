# -*- coding: utf-8 -*-

{
    
    'name': 'Inventarios Físicos',
    'version': '0.1',
    'author': 'Daniel Almaguer',
    'website': 'https://mx.linkedin.com/in/daniel-almaguer-valdez-b0768b215?original_referer=https%3A%2F%2Fwww.google.com%2F',
    'category': 'Labels',
    'summary': 'Modulo para toma de inventarios fisicos',
    'description': """\n
           
    """,
    'depends': ['base',
                    'product',
                    'mk_report_transactions',
                    'sale',
                    'stock',
                    'sale_stock','point_of_sale',],

    'data': [
               
             
                # Permisos de Acceso #
                 'security/group_access.xml',
                'security/ir.model.access.csv',
               
                # Reportes #
                'data/sequences.xml',
                'views/view_physical_inventory.xml',
               

            ],

    'demo': [

    ],
    'installable': True,
    'auto_install': False,
    'assets': {
       'web.assets_backend': [
        'cp_window_check/static/src/js/custom_event.js',
    ],
},

    'license': 'LGPL-3',
}
