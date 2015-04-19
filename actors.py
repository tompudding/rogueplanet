from globals.types import Point
import globals
import ui
import drawing
import os
import game_view
import random
import pygame
import cmath
import math

class Directions:
    UP    = 0
    DOWN  = 1
    RIGHT = 2
    LEFT  = 3

class Actor(object):
    texture = None
    width   = None
    height  = None
    def __init__(self,map,pos):
        self.map            = map
        self.tc             = globals.atlas.TextureSpriteCoords('%s.png' % self.texture)
        self.quad           = drawing.Quad(globals.quad_buffer,tc = self.tc)
        self.size           = Point(float(self.width)/16,float(self.height)/16)
        self.corners = self.size, Point(-self.size.x,self.size.y), Point(-self.size.x,-self.size.y), Point(self.size.x,-self.size.y)
        self.corners        = [p*0.5 for p in self.corners]
        self.corners_polar  = [(p.length(),((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        self.corners_euclid = [p for p in self.corners]
        self.current_sound  = None
        self.last_update    = None
        self.dead           = False
        self.move_speed     = Point(0,0)
        self.move_direction = Point(0,0)
        self.SetPos(pos)
        self.set_angle(3*math.pi/2)

    def SetPos(self,pos):
        self.pos = pos

        self.vertices = [((pos + corner)*globals.tile_dimensions).to_int() for corner in self.corners_euclid]

        #bl = pos * globals.tile_dimensions
        #tr = bl + (globals.tile_scale*Point(self.width,self.height))
        #bl = bl.to_int()
        #tr = tr.to_int()
        #self.quad.SetVertices(bl,tr,4)
        self.quad.SetAllVertices(self.vertices, 4)


    def set_angle(self, angle):
        self.angle = angle
        self.corners_polar  = [(p.length(),self.angle + ((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        cnums = [cmath.rect(r,a) for (r,a) in self.corners_polar]
        self.corners_euclid = [Point(c.real,c.imag) for c in cnums]

    def Update(self,t):
        self.Move(t)

    def Move(self,t):
        if self.last_update == None:
            self.last_update = globals.time
            return
        elapsed = globals.time - self.last_update
        self.last_update = globals.time

        self.move_speed += self.move_direction*elapsed*globals.time_step
        self.move_speed *= 0.7*(1-(elapsed/1000.0))

        amount = Point(self.move_speed.x*elapsed*globals.time_step,self.move_speed.y*elapsed*globals.time_step)

        #check each of our four corners
        for corner in self.corners:
            pos = self.pos + corner
            target_x = pos.x + amount.x
            if target_x >= self.map.size.x:
                amount.x = 0
                target_x = pos.x
            elif target_x < 0:
                amount.x = -pos.x
                target_x = 0
            target_tile_x = self.map.data[int(target_x)][int(pos.y)]
            if target_tile_x.type in game_view.TileTypes.Impassable:
                amount.x = 0

            elif (int(target_x),int(pos.y)) in self.map.object_cache:
                obj = self.map.object_cache[int(target_x),int(pos.y)]
                if obj.Contains(Point(target_x,pos.y)):
                    amount.x = 0

            target_y = pos.y + amount.y
            if target_y >= self.map.size.y:
                amount.y = 0
                target_y = pos.y
            elif target_y < 0:
                amount.y = -pos.y
                target_y = 0
            target_tile_y = self.map.data[int(pos.x)][int(target_y)]
            if target_tile_y.type in game_view.TileTypes.Impassable:
                amount.y = 0
            elif (int(pos.x),int(target_y)) in self.map.object_cache:
                obj = self.map.object_cache[int(pos.x),int(target_y)]
                if obj.Contains(Point(pos.x,target_y)):
                    amount.y = 0


        self.SetPos(self.pos + amount)

    def GetPos(self):
        return self.pos

    def GetPosCentre(self):
        return self.pos

class BaseLight(object):
    def __init__(self,parent):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_buffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.parent = parent
        self.colour = (1,1,1)

    @property
    def pos(self):
        return (self.parent.pos.x*globals.tile_dimensions.x,self.parent.pos.y*globals.tile_dimensions.y,10)

    def Update(self,t):
        self.quad.SetAllVertices(self.parent.vertices, 0)

class Light(BaseLight):
    def __init__(self,parent):
        super(Light,self).__init__(parent)
        globals.lights.append(self)

class ConeLight(object):
    width = 400
    height = 400
    z = 60
    def __init__(self,pos,angle,width):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.angle = angle
        self.angle_width = width
        pos = pos*globals.tile_dimensions
        self.pos = (pos.x,pos.y,self.z)
        globals.cone_lights.append(self)

    @property
    def screen_pos(self):
        p = self.pos
        return ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)

class Torch(ConeLight):
    def __init__(self,parent,offset):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.parent = parent
        self.colour = (1,1,1)
        self.angle = 0.0
        self.offset = cmath.polar(offset.x + offset.y*1j)
        self.angle_width = 0.5
        globals.cone_lights.append(self)

    @property
    def pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))*globals.tile_dimensions
        return (pos.x,pos.y,self.z)

    def Update(self,t):
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        #self.quad.SetAllVertices(self.parent.vertices, 0)


class Player(Actor):
    texture = 'player'
    width = 16
    height = 16

    def __init__(self,map,pos):
        self.mouse_pos = Point(0,0)
        #self.light = Light(self)
        self.torch = Torch(self,Point(-(self.width/globals.tile_dimensions.x)*0.6,0))
        super(Player,self).__init__(map,pos)

    def Update(self,t):
        if self.dead:
            globals.current_view.mode = modes.GameOver(globals.current_view)
            globals.current_view.game_over = True
        self.UpdateMouse(self.mouse_pos,None)
        super(Player,self).Update(t)
        #self.light.Update(t)
        self.torch.Update(t)

    def UpdateMouse(self,pos,rel):
        diff = pos - (self.pos*globals.tile_dimensions)
        distance,angle = cmath.polar(complex(diff.x,diff.y))
        self.set_angle(angle+math.pi)
        self.torch.angle = angle

