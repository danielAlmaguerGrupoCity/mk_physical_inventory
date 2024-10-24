from odoo import models, fields, api
from datetime import datetime
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError, ValidationError,AccessError
import json

class physicalInventoryLine(models.Model):
    _name = 'physical.inventory.line'
    _description = 'Conteos'
    _order = 'inventory_id, id'
   
    inventory_id = fields.Many2one('physical.inventory', string='Inventiario', required=True, ondelete='cascade', index=True, copy=False)
    company_id = fields.Many2one('res.company', 'Empresa', required=True, index=True, default=lambda self: self.env.company)
   
    product_id = fields.Many2one(
        'product.product', string='Producto',
       ondelete='restrict', check_company=True)  # Unrequired company
    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id", domain=[('detailed_type', '=', 'product')])
    
    loc_stock_id = fields.Many2one('stock.location',
        string='Ubicación',check_company=True,
        domain=lambda self: self._get_lot_stock_domain(),
        )
    
    product_uom_qty = fields.Float(string='Cantidad',  digits=(14,2), required=True, default=1.0)
    product_uom = fields.Many2one('uom.uom', string='UdM', domain="[('category_id', '=', product_uom_category_id)]", 
                                   compute='_onchange_product_uom', ondelete="restrict")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    quantity_box = fields.Float('Cajas', digits=(14,2), store=True, default=1.0)
    piezas_caja = fields.Float('Piezas por caja',related='product_template_id.uom_po_id.factor_inv')
    date_inventory_line = fields.Datetime('Fecha',  default=lambda self: fields.Datetime.now())
    user_id = fields.Many2one('res.users', string='Usuario', required=False, default=lambda self: self.env.user)
    product_count = fields.Integer(string='Conteo',  default=1 ,store=True, readonly=True)  
    
    state = fields.Selection([ ("draft", "Borrador"),
                                                    ("count", "Valido"),
                                                    ("canceled", "Cancelado"),
                                                     ("recount", "Recuento")
                                              ],  readonly=True,
                                                  ondelete={
                                                                "draft": "set default",
                                                                "count": "set default",
                                                                 "recount": "set default",
                                                              },default="draft",string= "Estado")
    def unlink(self):
    
        for record in self:
            if record.inventory_id.state_inventory == 'adjustment_made':
                raise UserError('No se pueden eliminar registros en este estado')
        return super(physicalInventoryLine, self).unlink()
    
    def write(self, vals):
     for rec in self:
        context = self.env.context
        active_id = context.get('default_active_id') or rec.inventory_id.id
       
       
       
        inv= rec.env['physical.inventory'].search([('id', '=', active_id)])
        if inv.state_inventory not in ('recount','count_started'):
               raise UserError ("No se pueden ingresar conteos en este estado, favor de verificar")
           
        if "state" in vals: 
           if vals["state"] == "canceled":
           
          # Buscar si ya existe un registro con el mismo producto, ubicación y estado "count" o "recount"
            existing_lines = rec.search([
                    ('inventory_id.id', '=', active_id),
                     ('product_id.id', '=', rec.product_id.id),
                     ('loc_stock_id.id', '=', rec.loc_stock_id.id),
                     ('state', 'in', ['count', 'recount']),
                     ('id', '!=', rec.id)  # Excluir el registro actual
                 ])
           
           # Si existe un registro con el mismo producto y ubicación en estado "count" o "recount", lanzar un error
            if not existing_lines:
               product_count = rec.env['phy.inv.prod.count'].search([    ('inventory_id.id', '=', active_id),
                                                                              ('state', 'in', ['count', 'recount']),
                                                                               ('loc_id.id', '=', rec.loc_stock_id.id),
                                                                               ('product_id.id', '=',  rec.product_id.id )
                                                                           ], order='create_date asc', limit=1)
             
               product_count.state = 'for_count'
        return super(physicalInventoryLine, self).write(vals)
    def setCancel(self):
       context = self.env.context
       active_id = context.get('default_active_id') or context.get('active_ids') or  context.get('active_id') 
      
       for rec in active_id:
          
           p = self.search([('id', '=', rec)])
           p.write({'state':'canceled'})
    @api.model
    def create(self, vals):
        # Obtener el ID del usuario actual
        current_user_id = self.env.user.id
        # Obtener el registro de users_team_ids si existe
       
        context = self.env.context
        active_id = context.get('default_active_id') or  context.get('active_id')
       
        inv= self.env['physical.inventory'].search([('id', '=', active_id)])
        users_team_ids = inv.users_team_ids
        
        
        # Verificar si el usuario actual está en users_team_ids
        #if users_team_ids and current_user_id not in inv.users_team_ids.ids:
          #  raise AccessError('No tienes permisos para generar conteos.')
     
        # Usar el active_id si está disponible
        if active_id:
            vals['inventory_id'] = active_id
        
        if inv.state_inventory not in ('recount','count_started'):
            raise UserError ("No se pueden ingresar conteos en este estado, favor de verificar")
        if inv.state_inventory == 'recount':   
         vals['state'] =  "recount"
        else:
           vals['state'] =  "count"  
           
        res = super(physicalInventoryLine, self).create(vals)
        if res.product_uom_qty > 0:
          res.validate_round()   
       
       
        product_count = self.env['phy.inv.prod.count'].search([    ('inventory_id.id', '=', active_id),
                                                                          ('state', '=','for_count'),
                                                                          ('loc_id.id', '=', res.loc_stock_id.id),
                                                                          ('product_id', '=',  res.product_id.id )
                                                                      ], order='create_date asc', limit=1)
       
        if product_count: 
           res.product_count= product_count.product_count
           first_line = self.search([    ('inventory_id.id', '=', active_id),
                                                                          ('state', 'in',('count','recount','draft')),
                                                                          ('loc_stock_id.id', '=', vals['loc_stock_id']),
                                                                          ('product_id.id', '=',  vals['product_id'] )
                                                                      ], order='create_date asc', limit=1)
          
           if first_line:
                product_count.state = 'count'
        
        
        
        return res
  
    @api.onchange('product_uom_qty')
    def _get_quantities_box(self):
        for rec in self:
            if rec.product_id and rec.product_uom_qty > 0:
               rec.validate_round()   
            product_br = rec.product_id
            piezas_presentacion = product_br.uom_po_id.factor_inv
            qty_available = rec.product_uom_qty
           
           
            quantity_box = 0.0
            if piezas_presentacion > 0:
                if rec.product_uom_qty:
                    quantity_box= qty_available / piezas_presentacion
                
          
            rec.quantity_box = quantity_box
    
    
    @api.depends('product_id')
    def _onchange_product_uom(self):
      for rec in self:
        rec.product_uom = rec.product_id.uom_id.id
   
      
        
    def _get_lot_stock_domain(self):
        user = self.env.user
        context = self.env.context
        active_id = context.get('default_active_id')
        inv= self.env['physical.inventory'].search([('id', '=', active_id)])
        if inv:
           
           
            locations = inv.loc_stock_id.ids
            
            return [('id', 'in', locations), ('usage', '=', 'internal'), ('company_id', 'in', user.company_ids.ids)]
        
        
        return [] 
    
    @api.onchange('product_id')
    def _onchange_warehouse_id(self):
        #Actualiza el dominio del campo lot_stock_id
        return {'domain': {'loc_stock_id': self._get_lot_stock_domain()}}
    
    #@api.depends('product_id')
    #def _get_product_domain(self):
    # for rec in self:
    #    print(f"hola domain product {rec.inventory_id.product_id}")
    #    context = self.env.context
    #    active_id = context.get('default_active_id')
    #    inv= self.env['physical.inventory'].search([('id', '=', active_id)])
    #    if inv:
    #        domain = [('id', 'in',[product.id for product in inv.product_id])]
    #        rec.product_domain = json.dumps((domain) ) 
    #        return [('id', 'in', inv.product_id.ids)]
    #    
    #   
    #    return [] 
    def validate_round(self):
        
            uom_qty = float_round(self.product_uom_qty, precision_rounding=self.product_id.uom_id.rounding, rounding_method='HALF-UP')
            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            qty_done = float_round(self.product_uom_qty, precision_digits=precision_digits, rounding_method='HALF-UP')
            
            if float_compare(uom_qty, qty_done, precision_digits=precision_digits) != 0:
                raise UserError(('La cantidad realizada para el producto "%s" no respeta la precisión de redondeo definida en la unidad de medida "%s".Cambie la cantidad realizada o la precisión de redondeo de su unidad de medida. '
                                ) % (self.product_id.display_name, self.product_id.uom_id.name))

class physicalInventoryAdjusment(models.Model):
     _name = 'stock.adjusment'
     _description = 'Ajustes de inventario'
     _order = 'inventory_id, id'
     
     inventory_id = fields.Many2one('physical.inventory', string='Inventario', required=True, index=True, copy=False)
     product_id = fields.Many2one(
        'product.product', string='Producto',
       ondelete='restrict', check_company=True)  # Unrequired company
     recount = fields.Boolean(string='Por recontar')
     product_name = fields.Char(string='Descripción')
     product_uom_qty = fields.Float(string='Cantidades contadas', required=True, tracking=True)
     product_uom_qty_dif = fields.Float(string='Diferencia',compute='_compute_product_uom_qty' ,store=True, readonly=True)
     product_qty_dif_per = fields.Float(string='Diferencia %', compute='_compute_product_uom_qty' ,store=True, readonly=True)
     product_qty_dif_mon = fields.Float(string='Diferencia $', compute='_compute_monetary' ,store=True, readonly=True)
     product_teor = fields.Float(string='Cantidad teorica',  readonly=True,)
     loc_id = fields.Many2one('stock.location',
        string='Ubicación',
        store=True,  domain=lambda self: self._get_lot_stock_domain(),
        check_company=True)
     company_id = fields.Many2one('res.company', 'Empresa', required=True, index=True, default=lambda self: self.env.company)
     product_uom = fields.Many2one('uom.uom', string='UdM', 
                                  compute='_onchange_product_uom', ondelete="restrict")
     date_checkpoint = fields.Datetime('Checkpoint',copy=False)
    
     def unlink(self):
        for record in self:
            if record.inventory_id.state_inventory == 'adjustment_made':
                raise UserError('No se pueden eliminar registros en este estado')
        return super(physicalInventoryAdjusment, self).unlink()
    
     def _get_lot_stock_domain(self):
        user = self.env.user
        context = self.env.context
        active_id = context.get('default_active_id')
        inv= self.env['physical.inventory'].search([('id', '=', active_id)])
        if inv:
           
           
            locations = inv.loc_stock_id.ids
            
            return [('id', 'in', locations), ('usage', '=', 'internal'), ('company_id', 'in', user.company_ids.ids)]
        
        
        return [] 
     @api.depends('product_uom_qty')
     def _compute_monetary(self): 
          for rec in self:
             if rec.inventory_id.state_inventory != 'adjustment_made':
                rec.product_qty_dif_mon =  rec.product_uom_qty_dif * rec.product_id.standard_price
     @api.depends('product_uom_qty')
     def _compute_product_uom_qty(self): 
        for rec in self:
         
        #Actualiza el dominio del campo lot_stock_id
          
          
       
          if rec.product_id and rec.loc_id and rec.inventory_id.state_inventory != 'adjustment_made':
            dic  = rec.product_id.with_context(location=rec.loc_id.id)._compute_quantities_dict(None, None, None,None,fields.Datetime.now())
            available_qty = dic[rec.product_id.id]['qty_available']
          
            rec.product_teor=available_qty
          rec.product_uom_qty_dif =  rec.product_uom_qty - rec.product_teor
          if rec.product_teor == 0:
                rec.product_qty_dif_per = 0
          else:  
              rec.product_qty_dif_per =  (rec.product_uom_qty / (rec.product_teor or 1) - 1)*100
          rec.write({'product_uom_qty_dif': (rec.product_uom_qty - rec.product_teor) })
        
        
     def action_set_inventory_recount(self):
      for rec in self:  
         inventory_id = rec.inventory_id
         if inventory_id.state_inventory not in ('recount','count_started','count_finished'):
            raise UserError ("No se puede realizar un reconteo en este estado. ")
      #   
      #  rec.recount = True
      #  inventory_id.write({'state_inventory':'recount','aprove':False}) 
      #  lines = rec.env['physical.inventory.line'].search([   ('loc_stock_id', '=', rec.loc_id.id),
      #                                                ('inventory_id', '=', inventory_id.id),
      #                                                ('product_id', '=', rec.product_id.id)
      #                                                                ])
      #  lines.write({'state':'canceled'})
      #  
         lines_for_count = rec.env['phy.inv.prod.count'].search([   ('loc_id', '=', rec.loc_id.id),
                                                       ('inventory_id', '=', inventory_id.id),
                                                       ('product_id', '=', rec.product_id.id)
                                                                      ],limit =1)
        
         inventory_id.write({'state_inventory':'recount','aprove':False}) 
         if not lines_for_count:
           
            dic  =  rec.product_id.with_context(location= rec.loc_id.id)._compute_quantities_dict(None, None, None,None,fields.Datetime.now())
            available_qty = dic[ rec.product_id.id]['qty_available']
            self.env['phy.inv.prod.count'].create({
                 'inventory_id': inventory_id.id,
                 'product_id': rec.product_id.id,
                 'loc_id': rec.loc.id,
                 'product_uom': rec.product_id.uom_id.id,
                 'product_uom_qty': available_qty,  # Puedes ajustar esto según tu lógica
                 'product_count':1
             })  
         inventory_id.write({'state_inventory':'count_finished','aprove':False}) 
        # else:
        #     lines_for_count.write({'state':'for_count','product_count': (lines_for_count.product_count +1)})
        
         
      selected_ids = self.env.context.get('active_ids', [])
    
      active_ids = self.env['stock.adjusment'].browse(selected_ids)
      product_count = self.env['phy.inv.prod.count'].search([('inventory_id', '=',self.inventory_id.id ),('product_id', '=', active_ids.product_id.ids),('loc_id', '=',  active_ids.loc_id.ids)])
      
      wizard = self.env['wizard.recount'].create({
                                      'inventory_id': self.inventory_id.id,
                                      'product_line':product_count.ids,
                                      'users_team_ids':self.inventory_id.users_team_ids.ids
                                      # 'product_id': products.ids,  # Si son varios productos, descomentar esta línea
                                  }) 
      return {
                   'type' : 'ir.actions.act_window',
                   'res_model' : 'wizard.recount',
                   'view_mode' : 'form', 
                   'target' : 'new',
                   'res_id' : wizard.id,
                  
               }  
     @api.depends('product_id')
     def _onchange_product_uom(self):
       for rec in self:
          rec.product_uom = rec.product_id.uom_id.id 
        
     @api.model
     def create(self, vals):
        # Obtener el ID del usuario actual
        current_user_id = self.env.user.id
        # Obtener el registro de users_team_ids si existe
        users_team_ids = self.inventory_id.users_team_ids
        context = self.env.context
        active_id = context.get('default_active_id') or  context.get('active_id') or vals['inventory_id']
        if active_id:
            vals['inventory_id'] = active_id
           
        inv= self.env['physical.inventory'].search([('id', '=', active_id)])
        adj = self.env['stock.adjusment'].search([('inventory_id', '=',active_id ),('product_id', '=', vals['product_id']),('loc_id', '=', vals['loc_id'])])    
      
        if inv:
         if inv.state_inventory not in ('recount','count_started','count_finished'):
            raise UserError ("No se pueden ingresar conteos en este estado, favor de verificar")
        if adj:
           raise UserError(f"El producto ya está registrado en la ubicación seleccionada.")
        
        res= super(physicalInventoryAdjusment, self).create(vals)
        res.product_name = res.product_id.name
      
        product_count = self.env['phy.inv.prod.count'].search([('inventory_id', '=',active_id ),('product_id', '=', res.product_id.id),('loc_id', '=', res.loc_id.id)])
        if not product_count:  
         available_qty = self.env['stock.quant']._get_available_quantity(res.product_id, res.loc_id,None, strict=True)
         self.env['phy.inv.prod.count'].with_context(active_id=active_id).create({
                'inventory_id': active_id,
                'product_id': res.product_id.id,
                'loc_id': res.loc_id.id,
                'product_uom': res.product_id.uom_id.id,
                'product_uom_qty': available_qty,  # Puedes ajustar esto según tu lógica
                'state':'count'
            })  
        product_count_line = self.env['physical.inventory.line'].search([('inventory_id', '=',active_id ),('product_id', '=', res.product_id.id),('loc_stock_id', '=', res.loc_id.id)])
        if not product_count_line:
        
          self.env['physical.inventory.line'].with_context(active_id=active_id).create({
                'inventory_id':active_id,
                'product_id': res.product_id.id,
                'loc_stock_id': res.loc_id.id,
                'product_uom': res.product_id.uom_id.id,
                'product_uom_qty': res.product_uom_qty,  # Puedes ajustar esto según tu lógica
               
            })  
      
        return res  
     def write(self, vals):
      context = self.env.context
      active_id = context.get('default_active_id') or context.get('active_id') or self.inventory_id.id
    
   
      inv= self.env['physical.inventory'].search([('id', '=', active_id)])
      if not 'product_uom_qty_dif' in vals:
       if inv.state_inventory not in ('recount','count_started','count_finished'):
             raise UserError (f"No se pueden modificar registros en este estado, favor de verificar")
      if 'product_uom_qty' in vals:
          adj= self.env['physical.inventory'].search([('id', '=', active_id)])
          
          if adj and self.product_uom_qty != vals['product_uom_qty']:
            msg = f"* Cantidad de {self.product_id.name}  modificada de {self.product_uom_qty} a { vals['product_uom_qty']} "
            inv.message_post(body=msg)
      return super(physicalInventoryAdjusment, self).write(vals)



class physicalInventoryRecount(models.Model):
    _name = 'phy.inv.prod.count'
    _description = 'Productos a contar'
    _order = 'inventory_id, id'
   
    inventory_id = fields.Many2one('physical.inventory', string='Inventario', required=True, ondelete='cascade', index=True, copy=False)
    company_id = fields.Many2one('res.company', 'Empresa', required=True, index=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Usuario reconteo')
    product_id = fields.Many2one(
        'product.product', string='Producto',
       
       ondelete='restrict', check_company=True)  # Unrequired company
    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id", domain=[('detailed_type', '=', 'product')])
    loc_id = fields.Many2one('stock.location',
        string='Ubicación',
        store=True,
        check_company=True)
    company_id = fields.Many2one('res.company', 'Empresa', required=True, index=True, default=lambda self: self.env.company)
    product_uom = fields.Many2one('uom.uom', string='UdM', 
                                  default =lambda self: self.product_id.uom_id.id, ondelete="restrict")
    product_count = fields.Integer(string='Conteo',  default=1 ,store=True, readonly=True)  
    product_uom_qty = fields.Float(string='Cantidad a la mano', digits='Product Unit of Measure',required=True, tracking=True)
    state = fields.Selection([ ("draft", "Borrador"),
                                                    ("for_count", "Por contar"),
                                                    ("count", "Contado"),
                                                   
                                              ],  readonly=True,
                                                  ondelete={
                                                                "for_count": "set default",
                                                                "count": "set default",
                                                               
                                                              },default="for_count",string= "Estado")
    @api.onchange('product_id')
    def _onchange_warehouse_id(self):
        #Actualiza el dominio del campo lot_stock_id
        return {'domain': {'product_id': self._get_product_domain()}}
   
    
    @api.model
    def create(self, vals):
        # Obtener el ID del usuario actual 
        context = self.env.context
        active_id = context.get('default_active_id') or  context.get('active_id') 
        
       
        # Usar el active_id si está disponible
        if active_id:
            vals['inventory_id'] = active_id
            
       
       
       
        return super(physicalInventoryRecount, self).create(vals)
    
class ReCount(models.TransientModel):
    _name ='wizard.recount'
    
    
    
    inventory_id = fields.Many2one('physical.inventory', string='inventario', required=True, ondelete='cascade', index=True, copy=False)
    
    product_line = fields.Many2many('phy.inv.prod.count', string='Productos a contar', copy=False, auto_join=True)
   
    users_team_ids = fields.Many2many('res.users', string='Equipo de inventarios',required=True)
    
    team_id = fields.Many2one('res.users', string='Equipo de inventarios',  domain="[('id', 'in', users_team_ids)]")
    
    def set_recount(self):
      self.inventory_id.write({'state_inventory':'recount','aprove':False}) 
      for rec in self.product_line:
          
        if self.inventory_id.state_inventory not in ('recount','count_started','count_finished'):
             raise UserError ("No se puede realizar un reconteo en este estado. ")
        
        line_stock_adj = rec.env['stock.adjusment'].search([   ('loc_id', '=', rec.loc_id.id),
                                                      ('inventory_id', '=', self.inventory_id.id),
                                                      ('product_id', '=', rec.product_id.id)
                                                                      ])
        
        
        line_stock_adj.recount = True
        
        
        lines = rec.env['physical.inventory.line'].search([   ('loc_stock_id', '=', rec.loc_id.id),
                                                      ('inventory_id', '=', self.inventory_id.id),
                                                      ('product_id', '=', rec.product_id.id)
                                                                     ])
        lines.write({'state':'canceled'})  
        rec.user_id = self.team_id
        rec.state = 'for_count'
      self.inventory_id.write({'state_inventory':'count_finished','aprove':False})   