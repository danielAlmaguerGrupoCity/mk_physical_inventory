odoo.define('cp_window_check.custom_event', function (require) {
    'use strict';
    console.log('Test JavaScript Loaded');
   
    var ListRenderer = require('web.ListRenderer');
    var dom = require('web.dom');
    var rpc = require('web.rpc');

    ListRenderer.include({
        events: _.extend({}, ListRenderer.prototype.events, {
            'click .color_picker': 'redirigir',
            'input input[name="sale_name"]': 'redirigir',
        }),

        start: function () {
            this._super.apply(this, arguments);
            console.log('FormRenderer started');

            // Verificar si los elementos existen en el DOM
            if (this.$('.o_composer_sale_name').length > 0) {
                console.log('Elemento .o_composer_sale_name encontrado en el DOM');
            } else {
                console.log('Elemento .o_composer_sale_name NO encontrado en el DOM');
            }

            if (this.$('input[name="sale_name"]').length > 0) {
                console.log('Elemento input[name="sale_name"] encontrado en el DOM');
            } else {
                console.log('Elemento input[name="sale_name"] NO encontrado en el DOM');
            }
        },
        /**
         * The _renderView function for calling the get_color()
         * @override
         */
            
            redirigir: function(ev) {
                alert("hola");
                // Cambia 'https://www.ejemplo.com' por la URL a la que quieres redirigir
                window.location.href = 'https://www.google.com';
            },
        });

        
  // Log para verificar que ListRenderer.include se ejecuta correctamente
  console.log('ListRenderer.include executed');
});
