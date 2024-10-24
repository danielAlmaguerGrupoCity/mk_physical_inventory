import base64
from contextlib import nullcontext
import json
from os import environ

import requests
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from odoo.exceptions import AccessError
from odoo.exceptions import except_orm
from odoo import http


class MyAPIController(http.Controller):
    
    @http.route('/setQuantity',type='json', auth='user', methods=['POST'],csrf=False )
    def setQuantity(self, **kw):
        # Obtener el ID del registro del modelo stock.inventory.adjustment.name
     try:
        ref = request.params.get("id")  # Obtener el valor del parámetro "name"
        product_id = request.params.get("product_id")
        location_id = request.params.get("location_id")
        quantity = request.params.get("quantity")


        domain = [
           ('default_code', '=', product_id)
           ]
        product = request.env['product.product'].search(domain)

        if not product:
           raise AccessError("No Existe el producto, verifica el código")
        
        print(f"regas: {product_id} {product.id} {location_id}")
        # Buscar el registro o crear uno nuevo si no existe
        domain = [
           ('product_id', '=', int(product.id)),
           ('location_id', '=', int(location_id))
           ]
        inventory_adjustment = request.env['stock.quant'].search(domain)

        print(f"regas: {inventory_adjustment} {quantity}")
        if inventory_adjustment:
            inventory_adjustment.write({'inventory_quantity': quantity})
      
    
      
       
        # Llamar al método action_apply
        print(f"Re2: {inventory_adjustment}")
        

        data = {
            'success': True,
            'message': (
                        "Inventario teórico: " + str(inventory_adjustment.quantity) + 
                        "\nCantidad Contada: " + str(quantity) + 
                        "\nDiferencia: " + str(inventory_adjustment.inventory_diff_quantity)
                        ),
            'id':  str(inventory_adjustment.id),
            'error': 'no',
          }
        response_json = json.dumps(data, default=str) 
        
        return response_json
     except UserError as error:
        # Manejar excepciones UserError y retornar una respuesta de error con código de estado 400
         data = {
            'success': False,
            'message': 'Ocurrió un error en la operación.',
            'error' : str(error),
            'id':  str("no"),
         }
         response_json = json.dumps(data, default=str) 
         return response_json
     
     except Exception as error:
         data = { 
            'success': False,
            'message': 'Ocurrió un error durante el proceso.',
            'error' : str(error),
            'id':  str("no"),
         }
         response_json = json.dumps(data, default=str) 
         return response_json
     
    @http.route('/applyAdjustment',type='json', auth='user', methods=['POST'],csrf=False )
    def applyAdjustment(self, **kw):
        # Obtener el ID del registro del modelo stock.inventory.adjustment.name
     try:
        id = request.params.get("id")  # Obtener el valor del parámetro "name"
        ref = request.params.get("ref")
        # Buscar el registro o crear uno nuevo si no existe
        domain = [
           ('id', '=', int(id))
           ]
        inventory_adjustment = request.env['stock.quant'].search(domain)

        inventory_diff_quantity = inventory_adjustment.inventory_diff_quantity
        inventory_quantity = inventory_adjustment.inventory_quantity
        quantity = inventory_adjustment.quantity

        if inventory_adjustment:
           inventory_adjustment.with_context(inventory_name=ref).action_apply_inventory()
       
        # Llamar al método action_apply
        print(f"applyAdjusment: {inventory_adjustment.product_id.product_tmpl_id.name }")
        

        data = {
            'success': True,
            'product': inventory_adjustment.product_id.product_tmpl_id.name,
            'qty_inv': quantity,
            'qty_cont':inventory_quantity ,
            'qty_dif': inventory_diff_quantity ,
            'message': 'Ajuste aplicado: ' + inventory_adjustment.product_id.product_tmpl_id.name + ": " + str(inventory_adjustment.quantity),
            'error': 'no',
          }
        response_json = json.dumps(data, default=str) 
        
        return response_json
     except UserError as error:
        # Manejar excepciones UserError y retornar una respuesta de error con código de estado 400
         data = {
            'success': False,
            'message': 'Ocurrió un error en la operación.',
            'error' : str(error)
         }
         response_json = json.dumps(data, default=str) 
         return response_json
     
     except Exception as error:
         data = { 
            'success': False,
            'message': 'Ocurrió un error durante el proceso.',
            'error' : str(error)
         }
         response_json = json.dumps(data, default=str) 
         return response_json



    @http.route('/getLocations',type='json', auth='user', methods=['POST'],csrf=False )
    def getLocations(self, **kw):
        
        domain = [('usage', '=', "internal")]

        locations_ids = request.env['stock.location'].search(domain)
        locations = []
        for location in locations_ids:
           location_data = {  # Crear un diccionario para cada ubicación
            'id': location.id,
            'complete_name': location.complete_name,
            }
           locations.append(location_data) 
            
        reception_data = {
            'success': True,
            'message': 'Operación exitosa',
            'error' : "no",
            'data' : locations
         }
        
        response_json = json.dumps(reception_data, default=str)

        return response_json
     
    @http.route('/getAllInventory',type='json', auth='user', methods=['POST'],csrf=False )
    def getLocations(self, **kw):
        
        domain = [('id', '=', 16)]

        inventory_ids = request.env['physical.inventory'].search(domain)
        invt = []
        for inv in inventory_ids:
           data = {  # Crear un diccionario para cada ubicación
            'id': inv.id,
            'complete_name': inv.name,
            }
           invt.append(data) 
            
        reception_data = {
            'success': True,
            'message': 'Operación exitosa',
            'error' : "no",
            'data' : invt
         }
        
        response_json = json.dumps(reception_data, default=str)

        return response_json
    
    @http.route('/searchProduct',type='json', auth='user', methods=['POST'],csrf=False )
    def searchProduct(self, **kw):
      try:
        
        barcode = request.params.get("barcode")
        domain = [('barcode', '=', barcode)]

        products_ids = request.env['product.product'].search(domain)

        if not products_ids:
           raise AccessError("No Existe el producto, verifica el código")
        
        products = []
        for product in products_ids:
           product_data = {  # Crear un diccionario para cada ubicación
            'um': product.product_tmpl_id.uom_id.name,
            
            }
           products.append(product_data) 
            
        data = {
            'success': True,
            'message': 'Operación exitosa',
            'error' : "no",
            'data' : products
         }
        
        response_json = json.dumps(data, default=str)

        return response_json
        
        
      except UserError as error:
        # Manejar excepciones UserError y retornar una respuesta de error con código de estado 400
         data = {
            'success': False,
            'message': 'Ocurrió un error en la operación.',
            'error' : str(error),
            'id':  str("no"),
         }
         response_json = json.dumps(data, default=str) 
         return response_json
     
      except Exception as error:
         data = { 
            'success': False,
            'message': 'Ocurrió un error durante el proceso.',
            'error' : str(error),
            'id':  str("no"),
         }
         response_json = json.dumps(data, default=str) 
         return response_json


   
