import json
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError, ValidationError,AccessError
#import json
import time
import logging
_logger = logging.getLogger(__name__)
#todos los movimientos despues del primer conteo
#reconteo: se pone estatus de conteo y se eliminan los conteos anteriores
class physicalInventory(models.Model):
    _name = 'physical.inventory'
    _description = 'Inventario fisico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'  # Ordena por ID en orden descendente
 
    
    name = fields.Char(string='Secuencia', readonly=True, copy=False, default='New')
    state_inventory = fields.Selection([ ("draft", "Borrador"),
                                                    ("confirmed", "Confirmado"),
                                                    ("count_started", "Conteo iniciado"),
                                                    ("count_finished", "Conteo Finalizado"),
                                                    ("recount", "Reconteo"),
                                                    ("adjustment_made", "Ajuste realizado"),
                                                    ("canceled", "Cancelado")
                                              ], copy=False, tracking=True,
                                                  ondelete={
                                                                "draft": "set default",
                                                                "confirmed": "set default",
                                                                "count_started": "set default",
                                                                "count_finished": "set default",
                                                                 "recount": "set default",
                                                                "adjustment_made": "set default",
                                                              },default="draft",string= "Estado")
    reference = fields.Char('Referencia' ,required=True)
   
    company_id = fields.Many2one('res.company', string="Empresa", default=lambda self: self.env.user.company_id)
    type = fields.Selection([
                                                    ("cyclic", "Ciclico"),
                                                    ("periodical", "Periodico"),
                                              ], 
                                                    ondelete={
                                                                "cyclic": "set default",
                                                                "periodical": "set default",
                                                              },string="Tipo",required=True,)
    
    date_inventory = fields.Datetime('Fecha', default=lambda self: fields.Datetime.now(),copy=False)
    date_confirm = fields.Datetime('Confirmación', copy=False)
    date_count_started = fields.Datetime('Inicio de conteo',copy=False)
    date_count_finished = fields.Datetime('Fin de conteo',copy=False)
    date_adjusment = fields.Datetime('Ajuste',copy=False)
    cmb_location= fields.Selection([
        ('allLocation', 'Todas las ubicaciones'),
        ('selectedLocation', 'Selección de ubicaciones'),
    ], string='Ubicaciones', default='allLocation')
    
    user_id = fields.Many2one('res.users', string='Responsable', required=False, default=lambda self: self.env.user)
    users_team_ids = fields.Many2many('res.users', string='Equipo de inventarios',required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacen' ,required=True)
    
    
    loc_stock_id = fields.Many2many('stock.location',
        string='Selección',
        store=True,
        domain=lambda self: self._get_lot_stock_domain(),
        check_company=True)
    #Inventario por: = Ubicación/Zona/Familia/Categoría/Línea/Producto
    cmb_products = fields.Selection([
        ('allProduct', 'Todos los productos'),
        ('seletedProduct', 'Selección de productos'),
        ('blind_count', 'Conteo ciego'),
    ], string='Productos', default='allProduct',required=True)
    
    children_location = fields.Boolean("Incluir ubicaciones hijas")
    aprove = fields.Boolean("Aprobado", copy=False,tracking=True,)
    
    inventory_line = fields.One2many('physical.inventory.line', 'inventory_id', string='Lineas de inventario', copy=False, auto_join=True)
    inventory_adjusment = fields.One2many('stock.adjusment', 'inventory_id', string='Ajustes de inventario', copy=False, auto_join=True)
    inventory_produc_count = fields.One2many('phy.inv.prod.count', 'inventory_id', string='Productos de inventario', ondelete='cascade', copy=False, auto_join=True)
    
    
    product_id = fields.Many2many(
        'product.product', string='Selección',
        change_default=True, ondelete='restrict', check_company=True)  # Unrequired company
    presicion = fields.Float("Precisión",compute='_calculate_inventory_data',default=0)
    amount_dif = fields.Monetary(string='Diferencia', compute='_calculate_inventory_data' ,default=0,currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id', string='Company Currency',
        readonly=True, store=True,
        help='Utility field to express amount currency')
    
    @api.depends('state_inventory')
    def _calculate_inventory_data(self):
        for record in self:
          if record.state_inventory == "count_finished":
            # Obtener la suma de product_qty_dif_mon
            filtered_records = record.inventory_adjusment.filtered(lambda r: r.product_uom_qty_dif == 0)
    
            # Verificar que los registros filtrados contengan valores válidos en product_qty_dif_mon
            if filtered_records:
                sum_product_qty_dif_mon = len(filtered_records)
            else:
                sum_product_qty_dif_mon = 0
            
            
            sum_product_uom = sum(record.inventory_adjusment.mapped('product_qty_dif_mon'))


            # Obtener la cantidad de registros en inventory_adjusment
            number_of_records = len(record.inventory_adjusment)

            # Ahora puedes usar `product_qty_dif_mon` y `number_of_records` como quieras
            # Por ejemplo, mostrarlo en el log
            
            if number_of_records:
             self.presicion  = sum_product_qty_dif_mon / number_of_records
             self.amount_dif = sum_product_uom
          else:
             self.presicion  =1
             self.amount_dif = 1
        
    def clean_product(self):
             ctx = self.env.context.copy()
             
          #   print(f"product  {self.product_id}")
             self.product_id= None
             return {
                 'type' : 'ir.actions.act_window',
                
                 'res_model' : self._name,
                 'view_mode' : 'form', 
                 'target' : 'current',
                 'res_id' : self.id,
                 'context' : ctx
             }
    def aprove_inv(self):
        for record in self:
           record.aprove = True
    def set_recount(self):
        for record in self:
           products = self.inventory_adjusment.with_context().filtered(lambda p: p.recount) 
           
         
           if products:
      
            record.write({'state_inventory':'recount','aprove':False}) 
           else:
                raise UserError('No hay productos a recontar, favor de verificar')
           
    def unlink(self):
        for record in self:
            if record.state_inventory != 'draft':
                raise UserError('No se pueden eliminar registros en este estado.')
        return super(physicalInventory, self).unlink()
    def action_view_users(self):
        self.ensure_one()  # Asegúrate de que solo haya un registro en el contexto
        domain = [('id', 'in', self.users_team_ids.ids)]
        return {
            'name': 'Usuarios',
            'view_mode': 'tree',
            'res_model': 'res.users',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': domain,
             'view_id': self.env.ref('mk_physical_inventory.view_users_tree_inventory').id ,
            
        }
        
    def action_view_report_inven(self):
        self.ensure_one()  # Asegúrate de que solo haya un registro en el contexto
        report = self.env['report.transaction'].create({
             "cmb_branchs": "seletedBranch", 
             "warehouse_id": self.warehouse_id.ids, 
             "cmb_location": "seletedLocation",
             "lot_stock_id":  self.loc_stock_id.ids,
             "cmb_products":  "seletedProduct",
             "product_id":  self.inventory_adjusment.product_id.ids,
             "is_cost": True,
             "from_date":  self.date_confirm,
             "to_date":     self.date_adjusment
             
             })
        return report.view_report()
    def action_view_products_inventory(self):
        #Actualiza el dominio del campo lot_stock_id      
        domain = [
            ('inventory_id', '=', self.id),
            ]
        
      
        return {
            'name': ('Productos a contar'),
            'view_mode': 'tree',
            'res_model': 'phy.inv.prod.count',
            'type': 'ir.actions.act_window',
            'target': 'current',
             'context': {
                'show_in_tree_view': True,
               
            },
            'view_id': self.env.ref('mk_physical_inventory.view_phy_inv_prod_count').id ,
              'domain': domain,
        }
    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        #Actualiza el dominio del campo lot_stock_id      
        return {'domain': {'loc_stock_id': self._get_lot_stock_domain()}}
    
   
    def _load_products(self):
        user = self.env.user
        self.inventory_produc_count.sudo().unlink()
        
        
       
        if self.cmb_products == "allProduct":
          self.product_id = False
          products = self.env['product.product'].search([])
          products = products.with_context().filtered(lambda p: p.type  == 'product' and p.active) 
          self.product_id = products
          
        else:
         if self.cmb_products == "blind_count":
             pass
         else:
          if self.product_id:
           products = self.product_id
          else: 
             raise UserError("No se agregó una selección de productos.") 
           
           
         
        if self.cmb_location != 'selectedLocation':
             
              
                 locations = self.env['stock.warehouse'].browse(self.warehouse_id.ids).mapped('view_location_id.id')
                 location_ids = self.env['stock.location'].search([('usage', '=', 'internal'), ('location_id', 'child_of', locations ),('company_id', 'in', user.company_ids.ids)])
               
                 if self.children_location:
                      children_location_ids  = self.env['stock.location'].search([('usage', '=', 'internal'),('location_id', 'child_of', self.loc_stock_id.ids )])
                      if self.children_location:
                            self.loc_stock_id += children_location_ids
                 else:   
                    
                     self.loc_stock_id= location_ids
        else:
         if self.loc_stock_id:
            if self.children_location:
                      children_location_ids  = self.env['stock.location'].search([('usage', '=', 'internal'),('location_id', 'child_of', self.loc_stock_id.ids )])
                      if self.children_location:
                            self.loc_stock_id += children_location_ids
             
        stockQuant = self.env['stock.quant']
       
        products_with_stock = stockQuant.search([('location_id', 'in', self.loc_stock_id.ids),('product_id', 'in',  self.product_id.ids)]).mapped('product_id')
        
      
        if self.cmb_products == "allProduct":
         self.product_id = products_with_stock
        else:
         self.product_id =  self.product_id  

        
      
       
        # Crear los registros en 'phy.inv.prod.count' con base en los productos seleccionados
        for product in self.product_id:
          
           for loc in self.loc_stock_id:
            dic  = product.with_context(location=loc.id)._compute_quantities_dict(None, None, None,None,fields.Datetime.now())
            available_qty = dic[product.id]['qty_available']
            if available_qty != 0 or self.cmb_products != "allProduct":
                self.env['phy.inv.prod.count'].create({
                'inventory_id': self.id,
                'product_id': product.id,
                'loc_id': loc.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': available_qty or 0,  # Puedes ajustar esto según tu lógica
               
            })   
        return {'domain': {'loc_stock_id': self._get_lot_stock_domain()}}
   
   
   
    
    
    
    def _get_lot_stock_domain(self): 
        user = self.env.user
       
        if self.warehouse_id:
           
            
            warehouse_ids = self.env['stock.warehouse'].search([('id', 'in', self.warehouse_id.ids),('company_id', 'in',  user.company_ids.ids)]).ids
            
            locations = self.env['stock.warehouse'].browse(warehouse_ids).mapped('view_location_id.id')
            
          
            children_location_ids  = self.env['stock.location'].search([('usage', '=', 'internal'),('location_id', 'child_of', locations ),('company_id', 'in', user.company_ids.ids)])
            locations += children_location_ids.ids
            return [('location_id', 'in', locations), ('usage', '=', 'internal'), ('company_id', 'in', user.company_ids.ids)]
        else: 
       
            return [('usage', '=', 'internal'), ('company_id', 'in', user.company_ids.ids)]
   
    @api.model
    def create(self, vals):
       
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('inventory.sequence') or 'New'
        return super(physicalInventory, self).create(vals)
    
    def confirm_inventory(self):
        if not self.users_team_ids:
            raise UserError(f"No se asignaron usuarios al equipo de inventario")
            
        self._load_products()
        self.state_inventory= "confirmed"
        self.date_confirm = fields.Datetime.now()
        
    def start_count(self):
        self.state_inventory= "count_started"
        self.date_count_started = fields.Datetime.now()
       
        
    def finish_count(self):
         _logger.info(f"**************************************antes de apagar el cron")
         self.check_cron_status(False)
         product_non_count = []
          # Buscar y eliminar todas las líneas de ajuste relacionadas
         act_next = self.env.context.get('act_next')
         if self.inventory_adjusment:
         
            self.inventory_adjusment.unlink()
           
         msg_error= ""  
         error = self.env['wizard.error.count']
        
         if not act_next:
           for product in self.product_id:
             for loc in self.loc_stock_id:
           
                product_in_loc = self.inventory_produc_count.filtered(lambda r: r.product_id == product and r.loc_id == loc and r.state in ('count'))
                
                if not product_in_loc:
                 
                   product_no_loc = self.inventory_produc_count.filtered(lambda r: r.product_id == product and r.loc_id == loc)
                   if product_no_loc:
                   
                      product_non_count.append(product_no_loc)
           
           
           if product_non_count:
          
               wizard_id = error.with_context(error_count=True, product_non_count=product_non_count).create({
                                                    'inventory_id':self.id,
                                                    'error': "No se encontraron conteos para los siguientes productos, al continuar se registrarán conteos en 0 para el ajuste."
                                                })
              
               ctx = self.env.context.copy()
               ctx['finish_count'] = True
               #   print(f"product  {self.product_id}")
              
               return {
                   'type' : 'ir.actions.act_window',
                   'name' : '¡ADVERTENCIA!',
                   'res_model' : 'wizard.error.count',
                   'view_mode' : 'form', 
                   'target' : 'new',
                   'res_id' : wizard_id.id,
                   'context' : ctx
               }  
            
         stock_quant_id = self.env['stock.quant']
         product_obj = self.env['product.product']
         products = product_obj.search([
                                         ('detailed_type', '=', 'product'),  # Tipo producto
                                                   # Que se puedan vender
                                     ])
         
         
         for p in products:
             for loc in self.loc_stock_id:
            
                 product_in_loc = self.inventory_line.filtered(lambda r: r.product_id == p and r.loc_stock_id == loc and r.state in ('count', 'recount'))
                
                 if product_in_loc:
                    first_line = self.env['physical.inventory.line'].search([
                                                                          ('inventory_id', '=', self.id),
                                                                          ('state', 'in',('count','recount')),
                                                                          ('product_id', '=', p.id)
                                                                      ], order='create_date asc', limit=1)
                    total_qty = sum(r.product_uom_qty for r in product_in_loc)
                    query = f""" SELECT  
                              location_id,
                              location_name,
                              id_product,
                              sum(qty_move) as qty_move
                              FROM view_inventory where id_product = {p.id}
                              and date_move between '{first_line.create_date}' and '{fields.Datetime.now()}'
                              and location_id = {loc.id}
                              group by 
                              location_id,
                              location_name,
                              id_product """
                    self._cr.execute(query)
                  
                    query_result = self._cr.dictfetchall()

# Comprueba si hay resultados
                    if query_result:
                     for result in query_result:
                   
                     
                     
                       total_qty += result['qty_move']  
                     
                     
                    stock_quant_id = self.env['stock.quant'].search([('product_id', '=', p.id),('location_id', '=', loc.id)])
                   
                    
                    if total_qty < 0:
                        total_qty = 0
                        
                        
                    if stock_quant_id:
                        stock_quant_id.write({'inventory_quantity': total_qty})
                    else:
                         stock_quant_id =self.env['stock.quant'].with_context(inventory_mode=True).create({
                                               'product_id': p.id,
                                               'location_id': loc.id,
                                               'inventory_quantity': total_qty,
                                           })
                         
                    stock_adjusment = self.env['stock.adjusment']
                 
                
                    stock_adjusment.create({      'inventory_id': self.id,
                                                   'product_id': p.id,
                                                   'product_uom_qty': abs(total_qty),
                                                   'product_uom_qty_dif': stock_quant_id.inventory_diff_quantity,
                                                   'product_teor': stock_quant_id.quantity,
                                                   'date_checkpoint': fields.Datetime.now(),
                                                   'loc_id': loc.id
                                               }) 
                   
         self.count_product_zero()       
         self.state_inventory= "count_finished"
         self.date_count_finished = fields.Datetime.now()
        
         
         self.__calculate_inventory_data()
         _logger.info(f"**************************************antes de encender el cron")
         self.check_cron_status(True)
           #Actualiza el dominio del campo lot_stock_id      
         domain = [
            ('inventory_id', '=', self.id),
            ]
         return {
                   'name': 'Resumen de diferencias',
                   'type' : 'ir.actions.act_window',
                   'res_model' : 'stock.adjusment',
                   'view_mode' : 'tree', 
                   'target' : 'current',
                   'domain': domain,
                   'context': {
                              'default_active_id': self.id,  # Puedes pasar valores predeterminados
                            
                       }
               }  
    def count_product_zero(self):  
          products_count_ids = self.inventory_produc_count.filtered(lambda r: r.state != 'count')   
          for p in products_count_ids:
           
            stock_quant_id = self.env['stock.quant'].search([('product_id', '=', p.product_id.id),('location_id', '=', p.loc_id.id)])
            if stock_quant_id:
              
                    stock_quant_id.write({'inventory_quantity': 0})
            else:
                    stock_quant_id =self.env['stock.quant'].with_context(inventory_mode=True).create({
                                               'product_id': p.product_id.id,
                                               'location_id': p.loc_id.id,
                                               'inventory_quantity': 0,
                                           })
            
            line_count = self.env['physical.inventory.line']
                 
                  
            line_count.with_context(active_id=self.id).create({      'inventory_id': self.id,
                                                   'product_id': p.product_id.id,
                                                   'product_uom_qty': abs(0),
                                                   'loc_stock_id': p.loc_id.id
                                               }) 
                     
            stock_adjusment = self.env['stock.adjusment']
                 
          
            stock_adjusment.create({      'inventory_id': self.id,
                                                   'product_id': p.product_id.id,
                                                   'product_uom_qty': abs(0),
                                                   'product_uom_qty_dif': stock_quant_id.inventory_diff_quantity,
                                                   'product_teor': stock_quant_id.quantity,
                                                   'loc_id': p.loc_id.id,
                                                    'date_checkpoint': fields.Datetime.now(),
                                               }) 
      
    def aply_adjusment(self):
        
           product_non_count = []
      
           _logger.info(f"**************************************antes de apagar el cron")
           self.check_cron_status(False)
           stock_quant_id = self.env['stock.quant']
           
           act_next = self.env.context.get('act_next')
          
           if not self.aprove:
               raise UserError("Se necesita la aprobación para poder aplica ajustes.")
           error = self.env['wizard.error.count']
           
           #if not act_next:
           #  for product in self.product_id:
           #    for loc in self.loc_stock_id:
           #       product_in_loc = self.inventory_adjusment.filtered(lambda r: r.product_id == product and r.loc_id == loc)
           #      
           #       if not product_in_loc:
           #        
           #          product_no_loc = self.inventory_produc_count.filtered(lambda r: r.product_id == product and r.loc_id == loc)
           #          if product_no_loc:
           #            
           #             product_non_count.append(product_no_loc)
           #  
           #  
           #  if product_non_count:
           #      wizard_id = error.with_context(error_count=True, product_non_count=product_non_count).create({
           #                                           'inventory_id':self.id,
           #                                       
           #                                           'error': "No se encontraron conteos para los siguientes productos, favor de verificar:"
           #                                       })
           #       
           #      ctx = self.env.context.copy()
           #      ctx['aply_adjusment'] = True
           #      #   print(f"product  {self.product_id}")
           #     
           #      return {
           #          'type' : 'ir.actions.act_window',
           #          'name' : '¡ADVERTENCIA!',
           #          'res_model' : 'wizard.error.count',
           #          'view_mode' : 'form', 
           #          'target' : 'new',
           #          'res_id' : wizard_id.id,
           #          'context' : ctx
           #      }
           aux= 0  
           for p in  self.inventory_adjusment:
                   _logger.info(f"Estado actual de inventory: {p.product_id.name} {aux}")
                   aux+=1
                  
                   stock_quant_id = self.env['stock.quant'].search([('product_id', '=', p.product_id.id),('location_id', '=', p.loc_id.id)])  
                   stock_adjusment = self.env['stock.adjusment'].search([('inventory_id','=',self.id,),('product_id', '=', p.product_id.id),('loc_id', '=', p.loc_id.id)])  
                  
             
                                                     
                   total_qty = p.product_uom_qty
                   query = f""" SELECT  
                                location_id,
                                location_name,
                                id_product,
                                sum(qty_move) as qty_move
                                FROM view_inventory where id_product = {p.product_id.id}
                                and date_move between '{stock_adjusment.date_checkpoint}' and '{fields.Datetime.now()}'
                                and location_id = {p.loc_id.id}
                                group by 
                                location_id,
                                location_name,
                                id_product """
                   self._cr.execute(query)
                
                   query_result = self._cr.dictfetchall()
  
# Comprue  ba si hay resultados
                   if query_result:
                       for result in query_result:
                       
                         total_qty += result['qty_move']  
                       
                   if total_qty < 0:
                          total_qty = 0   
                   if stock_quant_id:
                       stock_quant_id.write({'inventory_quantity': total_qty})
                     
                       p.product_uom_qty = total_qty
                   else:
                         stock_quant_id =self.env['stock.quant'].with_context(inventory_mode=True).create({
                                              'product_id': p.product_id.id,
                                              'location_id': p.loc_id.id,
                                              'inventory_quantity': total_qty,
                                          })
                        
                         p.product_uom_qty = total_qty
                         
                   stock_adjusment.date_checkpoint = fields.Datetime.now()
                   stock_adjusment._cr.commit()
           self._cr.commit()
           stock_quant_id = self.env['stock.quant'].search([('product_id', 'in', self.inventory_adjusment.product_id.ids),('location_id', 'in', self.inventory_adjusment.loc_id.ids),('inventory_diff_quantity','!=',0)])
                   
           stock_inventory_adjustment = self.env['stock.inventory.adjustment.name'].with_context(default_quant_ids=stock_quant_id.ids).create({
                                        'inventory_adjustment_name': self.reference, })
                  
           stock_inventory_adjustment.action_apply()
                
           
                
           self.date_adjusment = fields.Datetime.now()     
           self.state_inventory= "adjustment_made"    
           
           self._calculate_inventory_data()
           _logger.info(f"**************************************antes de encender el cron")
           self.check_cron_status(True)
           
          
    def check_cron_status(self,active):
      try:
        # Buscar el cron por nombre
        cron_job = self.env['ir.cron'].browse(42) 
        
        if cron_job:
            _logger.info(f"**************************************Valor actual cron: {self.name}  {cron_job.name} {cron_job.active}")
            # Verificar si el cron está activo
          
            cron_job.write({'active':active})
            cron_job._cr.commit()
           
            _logger.info(f"*************************************Estatus de cron: {cron_job.name} {cron_job.active}")
              
      except UserError as e:
         
            # Capturar el error cuando la tarea programada está corriendo
            if 'El registro no se puede modificar en este momento: se está ejecutando esta tarea programada y no puede ser modificada. Inténtelo de nuevo dentro de unos minutos' in str(e):
              
                time.sleep(60)
                self.check_cron_status()
                
            else:
                raise e  # Levantar otros errores que no sean relacionados con el cron  
    def cancel(self):
        self.state_inventory= "canceled"   
  
    def draft(self):
        self.state_inventory= "draft"    
class StockMove(models.Model):
    _inherit ='stock.move'
    
    inventory_id = fields.Many2one('physical.inventory', string='Inventario', required=True, ondelete='cascade', index=True, copy=False)
    
class ErrorCount(models.TransientModel):
    _name ='wizard.error.count'
    
    
    
    inventory_id = fields.Many2one('physical.inventory', string='inventario', required=True, ondelete='cascade', index=True, copy=False)
     
    error = fields.Char(string='Error',   readonly=True,)
    company_id = fields.Many2one('res.company', 'Empresa', required=True, index=True, default=lambda self: self.env.company)
    product_line = fields.Many2many('phy.inv.prod.count', string='Productos a contar', copy=False, auto_join=True)
    
    @api.model
    def create(self, vals):
     
       
        context = self.env.context
        product_ids = self.env['phy.inv.prod.count']
       
        product_non_count = context.get('product_non_count')   
        count=0
     
        for row in product_non_count:
     
         product_ids += self.env['phy.inv.prod.count'].search([('inventory_id', '=', vals['inventory_id']),('product_id', '=', row[count].product_id.id),('loc_id', '=', row[count].loc_id.id )])
        
        if product_ids:
        # Convertir los productos en una lista de tuplas (0, 0, {'product_id': product_id, 'otros_campos': valores})
        
        
          vals['product_line'] = product_ids.ids
        return super(ErrorCount, self).create(vals)
    def next(self):
     return  self.inventory_id.finish_count()
    def next2(self):
      return self.inventory_id.aply_adjusment()

from odoo import http
from odoo.http import request
class MyAPIController(http.Controller):
    
    @http.route('/getLoc_inv',type='json', auth='user', methods=['POST'],csrf=False )
    def getLocations(self, **kw):
        inventory_id = request.params.get("inventory_id")
        
        inv_id = request.env['physical.inventory'].browse(inventory_id)
        
        
        domain = [('id', 'in', inv_id.loc_stock_id.ids)]

        locations_ids = request.env['stock.location'].search(domain)
        locations = []
        for location in locations_ids:
           location_data = {  # Crear un diccionario para cada ubicación
            'id': location.id,
            'complete_name': location.complete_name,
            }
           locations.append(location_data) 
            
        reception_data = {
           
            'loc_stock_id' : locations
         }
        
      

        response_json = json.dumps(reception_data, default=str) 
        
        return response_json
    @http.route('/getProduct_count',type='json', auth='user', methods=['POST'],csrf=False )
    def getProduct_count(self, **kw):
        inventory_id = request.params.get("inventory_id")
        
        inv_id = request.env['physical.inventory'].browse(inventory_id)
       
        current_user = request.env.user
        
         # Filtrar las líneas de inventario donde el user_id coincida con el usuario actual
        user_inventory_lines = inv_id.inventory_line.filtered(lambda line: line.user_id == current_user and line.state != 'canceled')
    
        products = []
        for pro in user_inventory_lines:
           product_image = pro.product_id.image_128.decode('utf-8') if pro.product_id.image_128 else None  # Imagen más pequeña

           product_data = {  # Crear un diccionario para cada ubicación
            'id': pro.id,
            'barcode': pro.product_id.barcode,
            'complete_name': pro.product_id.name,
            'state': pro.state,
            'product_uom_qty':pro.product_uom_qty,
            'image': product_image,  # Agregar la imagen en base64
            }
           products.append(product_data) 
            
        reception_data = {
           
            'products' : products
         }
        
      

        response_json = json.dumps(reception_data, default=str) 
        
        return response_json
    
    @http.route('/getProduct_for_count',type='json', auth='user', methods=['POST'],csrf=False )
    def getProduct_for_count(self, **kw):
        inventory_id = request.params.get("inventory_id")
        
        inv_id = request.env['physical.inventory'].browse(inventory_id)
       
        current_user = request.env.user
        
         # Filtrar las líneas de inventario donde el user_id coincida con el usuario actual
        user_inventory_produc_counts = inv_id.inventory_produc_count.filtered(lambda line: line.user_id == current_user)
    
        products = []
        for pro in user_inventory_produc_counts:
           product_image = pro.product_id.image_128.decode('utf-8') if pro.product_id.image_128 else None  # Imagen más pequeña

           product_data = {  # Crear un diccionario para cada ubicación
            'id': pro.id,
            'barcode': pro.product_id.barcode,
            'complete_name': pro.product_id.name,
            'state': pro.state,
            'product_uom_qty':pro.product_uom_qty,
            'image': product_image,  # Agregar la imagen en base64
            }
           products.append(product_data) 
            
        reception_data = {
           
            'products' : products
         }
        
      

        response_json = json.dumps(reception_data, default=str) 
        
        return response_json
                                         
    @http.route('/create_inventory_line', type='json', auth='user', methods=['POST'], csrf=False)
    def createInventoryLine(self, **kw):
      try:
        # Obtener los parámetros del request
          # Asegurarse de pasar el contexto correcto
        context = dict(request.env.context or {})
       
        inventory_id = request.params.get('inventory_id')
        product_id = request.params.get('product_id')
        location_id = request.params.get('location_id')
        product_uom_qty = request.params.get('product_uom_qty', 1.0)  # Valor por defecto

        context['active_id'] = inventory_id
        domain = [
           ('default_code', '=', product_id)
           ]
        product = request.env['product.product'].search(domain)

        if not product:
           raise AccessError("No Existe el producto, verifica el código")
        # Crear el registro en el modelo physical.inventory.line
        new_line = request.env['physical.inventory.line'].with_context(context).create({
            'inventory_id': inventory_id,
            'product_id': product.id,
            'loc_stock_id': location_id,
            'product_uom_qty': product_uom_qty,
        })
       
        data = {
            'success': True,
            'message': 'Operación exitosa',
            'error' : "no",
            'id' : new_line.id,
            'product': product.product_tmpl_id.name,
            'product_uom_qty': product_uom_qty,
         }
        
        response_json = json.dumps(data, default=str)

        return response_json

        # Devolver el ID del nuevo registro como confirmación
        return json.dumps({'success': True, 'id': new_line.id})    
      except UserError as error:
         # Hacer rollback de la transacción en caso de error general
         request.env.cr.rollback()
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
           # Hacer rollback de la transacción en caso de error general
         request.env.cr.rollback()
         data = { 
            'success': False,
            'message': 'Ocurrió un error durante el proceso.',
            'error' : str(error),
            'id':  str("no"),
         }
         response_json = json.dumps(data, default=str) 
         return response_json
    @http.route('/validateProduct',type='json', auth='user', methods=['POST'],csrf=False )
    def searchProduct(self, **kw):
      try:
        
        barcode = request.params.get("barcode")
        domain = [('barcode', '=', barcode)]

        products_ids = request.env['product.product'].search(domain)

        if not products_ids:
           raise AccessError("No Existe el producto, verifica el código")
        
        products = []
        for product in products_ids:
           product_image = product.image_128.decode('utf-8') if product.image_128 else None  # Imagen más pequeña
           product_data = {  # Crear un diccionario para cada ubicación
            'um': product.product_tmpl_id.uom_id.name,
            'name': product.product_tmpl_id.name,
            'image':product_image,
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
     
    @http.route('/get_user_profile', type='json', auth='user', methods=['POST'], csrf=False)
    def get_user_profile(self, **kw):
     current_user = request.env.user
     try:
    # Obtener la imagen de perfil del usuario (image_128 es la versión más pequeña)
      user_image = current_user.image_128.decode('utf-8') if current_user.image_128 else None

    # Obtener los grupos a los que pertenece el usuario
      user_groups = current_user.groups_id.mapped('name')

    # Datos del usuario
      user_data = {
        'success': True,
        'name': current_user.name,
        'image': user_image,  # Imagen de perfil del usuario en base64
        'groups': user_groups,  # Lista de nombres de los grupos
     }

      response_json = json.dumps(user_data, default=str)

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