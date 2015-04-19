from globals.types import Point
from OpenGL.GL import *
import globals
import ui
import drawing
import os
import game_view
import random
import pygame
import cmath
import math
import numpy

class Directions:
    UP    = 0
    DOWN  = 1
    RIGHT = 2
    LEFT  = 3

class Actor(object):
    texture = None
    width   = None
    height  = None
    threshold = 0.01
    def __init__(self,map,pos):
        self.map            = map
        self.tc             = globals.atlas.TextureSpriteCoords('%s.png' % self.texture)
        self.quad           = drawing.Quad(globals.quad_buffer,tc = self.tc)
        self.size           = Point(float(self.width)/16,float(self.height)/16)
        self.corners = self.size, Point(-self.size.x,self.size.y), Point(-self.size.x,-self.size.y), Point(self.size.x,-self.size.y)
        self.corners        = [p*0.5 for p in self.corners]
        self.corners_polar  = [(p.length(),((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        self.radius_square  = (self.size.x/2)**2 + (self.size.y/2)**2
        self.radius         = math.sqrt(self.radius_square)
        self.corners_euclid = [p for p in self.corners]
        self.current_sound  = None
        self.last_update    = None
        self.dead           = False
        self.move_speed     = Point(0,0)
        self.move_direction = Point(0,0)
        self.pos = None
        self.SetPos(pos)
        self.set_angle(3*math.pi/2)

    def RemoveFromMap(self):
        if self.pos != None:
            bl = self.pos.to_int()
            tr = (self.pos+self.size).to_int()
            for x in xrange(bl.x,tr.x+1):
                for y in xrange(bl.y,tr.y+1):
                    self.map.RemoveActor(Point(x,y),self)

    def SetPos(self,pos):
        self.RemoveFromMap()
        self.pos = pos

        self.vertices = [((pos + corner)*globals.tile_dimensions).to_int() for corner in self.corners_euclid]

        bl = pos
        tr = bl + self.size
        bl = bl.to_int()
        tr = tr.to_int()
        #self.quad.SetVertices(bl,tr,4)
        self.quad.SetAllVertices(self.vertices, 4)
        for x in xrange(bl.x,tr.x+1):
            for y in xrange(bl.y,tr.y+1):
                self.map.AddActor(Point(x,y),self)

    def TriggerCollide(self,other):
        pass


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

        bl = self.pos.to_int()
        tr = (self.pos+self.size).to_int()
        for x in xrange(bl.x,tr.x+1):
            for y in xrange(bl.y,tr.y+1):
                try:
                    for actor in self.map.data[x][y].actors:
                        if actor is self:
                            continue
                        distance = actor.pos - self.pos
                        if distance.SquareLength() < self.radius_square + actor.radius_square:
                            overlap = self.radius + actor.radius - distance.length()
                            adjust = distance.unit_vector()*-overlap
                            #print type(self),self.radius,actor.radius,distance.length(),overlap,adjust
                            amount += adjust*0.1
                            #We've hit, so move us away from it's centre by the overlap
                except IndexError:
                    pass

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

    @property
    def screen_pos(self):
        p = (self.pos*globals.tile_dimensions - globals.game_view.viewpos._pos)*globals.scale
        return p


class Light(object):
    z = 60
    width = 400
    height = 400
    def __init__(self,pos):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.set_pos(pos)
        globals.lights.append(self)

    def set_pos(self,pos):
        self.world_pos = pos
        pos = pos*globals.tile_dimensions
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)

    def Update(self,t):
        pass

    @property
    def screen_pos(self):
        p = self.pos
        return ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)

class ActorLight(object):
    z = 6
    def __init__(self,parent):
        self.parent = parent
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (1,1,1)
        globals.non_shadow_lights.append(self)

    def Update(self,t):
        self.vertices = [((self.parent.pos + corner*2)*globals.tile_dimensions).to_int() for corner in self.parent.corners_euclid]
        self.quad.SetAllVertices(self.vertices, 0)

    @property
    def pos(self):
        return (self.parent.pos.x*globals.tile_dimensions.x,self.parent.pos.y*globals.tile_dimensions.y,self.z)


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
    def world_pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))
        return (pos.x,pos.y,self.z)

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

class Enemy(Actor):
    texture = 'enemy'
    width   = 16
    height  = 16
    speed = 0.04
    random_segments = 200
    seek_distance = 8
    brightness_threshold = 0.1
    flee_threshold = 0.03

    def __init__(self,map,pos):
        self.last_random = 0
        self.fleeing = False
        super(Enemy,self).__init__(map,pos)

    def get_brightness(self):
        sp = self.screen_pos
        self.pixel_data = glReadPixels(sp.x-self.width/2,sp.y-self.width/2,self.width,self.height,GL_RGB,GL_FLOAT)[:,:,1:3]

        return numpy.average(self.pixel_data)

    def Update(self,t):
        brightness = self.get_brightness()
        player_diff = globals.game_view.map.player.pos - self.pos
        player_distance = player_diff.length()
        if self.fleeing:
            if brightness > self.flee_threshold:
                self.avoid_light(player_diff, player_distance)
            else:
                self.fleeing = False
        else:
            if brightness > self.brightness_threshold:
                self.avoid_light(player_diff, player_distance)
            elif player_distance < self.seek_distance:
                self.seek_player(player_diff,player_distance)
            else:
                self.random_walk()
        d,angle = cmath.polar(self.move_direction.x + self.move_direction.y*1j)
        self.set_angle(angle + math.pi)
        super(Enemy,self).Update(t)

    def seek_player(self, player_diff, player_distance):
        distance,angle = cmath.polar(player_diff.x + player_diff.y*1j)
        self.seek_distance = 30 #We go up after seeing him
        self.move_direction = player_diff.unit_vector()*self.speed

    def random_walk(self):
        elapsed = globals.time - self.last_random
        if elapsed < self.random_segments:
            return
        self.last_random = globals.time
        a = random.random()*2*math.pi
        d = cmath.rect(self.speed,a)
        self.set_angle(a+math.pi)
        self.move_direction = Point(d.real,d.imag)

    def avoid_light(self, player_diff, player_distance):
        lights = [(light,(self.pos-Point(*light.world_pos[:2]))) for light in globals.lights + globals.cone_lights]
        lights.sort(lambda x,y : cmp(x[1].SquareLength(),y[1].SquareLength()))
        diff = lights[0][1]
        self.move_direction = diff.unit_vector()*self.speed
        self.fleeing = True

    def avoid_light_old(self, player_diff, player_distance):
        #Get the brightness at a few points and go in the direction that it's
        #Use green light for some reason
        elapsed = globals.time - self.last_random
        if elapsed < self.random_segments:
            return
        self.last_random = globals.time
        self.fleeing = True
        sp = self.screen_pos
        self.pixel_data = glReadPixels(sp.x-self.width*2,sp.y-self.width*2,self.width*4,self.height*4,GL_RGB,GL_FLOAT)[:,:,1:3]
        max_index = numpy.argmax(self.pixel_data[:,:,1:2])
        min_index = numpy.argmin(self.pixel_data[:,:,1:2])
        indices = numpy.unravel_index((max_index,min_index),self.pixel_data.shape)
        max_index = indices[0][0],indices[1][0],indices[2][0]
        min_index = indices[0][1],indices[1][1],indices[2][1]
        #print 'max=',max_index,self.pixel_data[max_index]
        #print 'test',self.pixel_data[indices]
        d = Point(indices[0][0]-indices[0][1],indices[1][0]-indices[1][1]).unit_vector()
        if d.length() == 0:
            self.seek_player(player_diff, player_distance)
            self.move_direction *= -1

        self.move_direction = d.unit_vector()*self.speed




class Player(Actor):
    texture = 'player'
    width = 16
    height = 16

    def __init__(self,map,pos):
        self.mouse_pos = Point(0,0)
        super(Player,self).__init__(map,pos)
        self.light = ActorLight(self)
        self.torch = Torch(self,Point(-(self.width/globals.tile_dimensions.x)*0.6,0))

    def Update(self,t):
        if self.dead:
            globals.current_view.mode = modes.GameOver(globals.current_view)
            globals.current_view.game_over = True
        self.UpdateMouse(self.mouse_pos,None)
        super(Player,self).Update(t)
        self.light.Update(t)
        self.torch.Update(t)

    def UpdateMouse(self,pos,rel):
        diff = pos - (self.pos*globals.tile_dimensions)
        distance,angle = cmath.polar(complex(diff.x,diff.y))
        self.set_angle(angle+math.pi)
        self.torch.angle = angle

