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
    initial_health = 100
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
        self.last_damage = 0
        self.health = self.initial_health
        self.interacting = None
        self.SetPos(pos)
        self.set_angle(3*math.pi/2)

    def RemoveFromMap(self):
        if self.pos != None:
            bl = self.pos.to_int()
            tr = (self.pos+self.size).to_int()
            for x in xrange(bl.x,tr.x+1):
                for y in xrange(bl.y,tr.y+1):
                    self.map.RemoveActor(Point(x,y),self)

    def AdjustHealth(self,amount):
        self.health += amount
        if self.health > self.initial_health:
            self.health = self.initial_health
        if self.health < 0:
            #if self.dead_sound:
            #    self.dead_sound.play()
            self.health = 0

    def damage(self, amount):
        if globals.time < self.last_damage + self.immune_duration:
            #woop we get to skip
            return
        self.last_damage = globals.time
        self.AdjustHealth(-amount)

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

        if self.interacting:
            self.move_speed = Point(0,0)

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
                            self.TriggerCollide(actor)
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

        if self.interacting:
            diff = self.interacting.pos + (self.interacting.size*0.5) - self.pos
            distance = diff.length()
            print 'turnip',distance
            if distance > 2.5:
                self.deactivate()

    def GetPos(self):
        return self.pos

    def GetPosCentre(self):
        return self.pos

    def click(self, pos, button):
        pass

    def unclick(self, pos, button):
        pass

    @property
    def screen_pos(self):
        p = (self.pos*globals.tile_dimensions - globals.game_view.viewpos._pos)*globals.scale
        return p


class Light(object):
    z = 60
    def __init__(self,pos,radius = 400):
        self.radius = radius
        self.width = self.height = radius
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.set_pos(pos)
        self.on = True
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
        self.on = True
        globals.non_shadow_lights.append(self)

    def Update(self,t):
        self.vertices = [((self.parent.pos + corner*2)*globals.tile_dimensions).to_int() for corner in self.parent.corners_euclid]
        self.quad.SetAllVertices(self.vertices, 0)

    @property
    def pos(self):
        return (self.parent.pos.x*globals.tile_dimensions.x,self.parent.pos.y*globals.tile_dimensions.y,self.z)

class FixedLight(object):
    z = 6
    def __init__(self,pos,size):
        #self.world_pos = pos
        self.pos = pos*globals.tile_dimensions
        self.size = size
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (0.2,0.2,0.2)
        self.on = True
        globals.uniform_lights.append(self)
        self.pos = (self.pos.x,self.pos.y,self.z)
        box = (self.size*globals.tile_dimensions)
        bl = Point(*self.pos[:2])
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)


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
        self.initial_angle = angle
        self.angle = angle
        self.angle_width = width
        self.on = True
        pos = pos*globals.tile_dimensions
        self.world_pos = pos
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        globals.cone_lights.append(self)

    @property
    def screen_pos(self):
        p = self.pos
        out =  ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)
        return out


class SentryLight(ConeLight):
    max_disturb = 0.4
    duration = 600
    def __init__(self,pos,angle,width,parent):
        self.duration = SentryLight.duration + (random.random()*100-50)
        self.offset = random.random()*self.duration
        super(SentryLight,self).__init__(pos,angle,width)
        parent.sentry_lights.append(self)

    def Update(self,t):
        self.angle = self.initial_angle + math.sin(float(t+self.offset)/self.duration)*self.max_disturb

class Torch(ConeLight):
    max_level = 100
    burn_rate = 0.005
    restore_rate = 0.003
    on_penalty = 2
    def __init__(self,parent,offset):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.parent = parent
        self.last_update    = None
        self.colour = (1,1,1)
        self.angle = 0.0
        self.offset = cmath.polar(offset.x + offset.y*1j)
        self.angle_width = 0.5
        self.on = False
        self.level = self.max_level
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

    def turn_on(self):
        self.on = True
        self.adjust_level(-self.on_penalty)

    def turn_off(self):
        self.on = False

    def adjust_level(self, amount):
        self.level += amount
        if self.level > self.max_level:
            self.level = self.max_level
        if self.level < 0:
            self.level = 0
            self.on = False
        self.parent.info_box.torch_data.power.SetBarLevel(float(self.level)/self.max_level)

    def Update(self,t):
        if self.last_update == None:
            self.last_update = globals.time
            return
        elapsed = globals.time - self.last_update
        self.last_update = globals.time
        if self.on:
            burned = elapsed * self.burn_rate
            self.adjust_level(-burned)
        else:
            restored = elapsed * self.restore_rate
            self.adjust_level(restored)

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
    seek_distance = 16
    brightness_threshold = 0.1
    flee_threshold = 0.03
    base_attack_damage = 5

    def __init__(self,map,pos):
        self.last_random = 0
        self.fleeing = False
        super(Enemy,self).__init__(map,pos)

    def get_brightness(self):
        sp = self.screen_pos
        self.pixel_data = glReadPixels(sp.x-self.width/2,sp.y-self.width/2,self.width,self.height,GL_RGB,GL_FLOAT)[:,:,1:3]

        return numpy.average(self.pixel_data)

    def TriggerCollide(self,other):
        if isinstance(other,Player):
            self.attack(other)

    def attack_damage(self):
        return self.base_attack_damage + random.randint(0,6)-3

    def attack(self, player):
        #print self,'attacking!',player
        player.damage(self.attack_damage())
        globals.current_view.viewpos.ScreenShake(500)

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
    initial_health = 100
    immune_duration = 200
    def __init__(self,map,pos):
        self.mouse_pos = Point(0,0)
        super(Player,self).__init__(map,pos)
        self.light = ActorLight(self)
        self.tilium = False
        self.flare = None
        self.torch = Torch(self,Point(-(self.width/globals.tile_dimensions.x)*0.6,0))
        self.info_box = ui.Box(parent = globals.screen_root,
                               pos = Point(0,0),
                               tr = Point(1,0.08),
                               colour = (0,0,0,0.7))
        self.info_box.health_text = ui.TextBox(self.info_box,
                                               bl = Point(0.8,0),
                                               tr = Point(1,0.7),
                                               text = '\x81:%d' % self.initial_health,
                                               textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                               colour = (1,0,0,1),
                                               scale = 10,
                                               alignment = drawing.texture.TextAlignments.CENTRE)
        self.info_box.torch_data = ui.UIElement(self.info_box,
                                                pos = Point(0.5,0),
                                                tr = Point(0.85,1))
        self.info_box.torch_data.text = ui.TextBox(self.info_box.torch_data,
                                                    bl = Point(0,0),
                                                    tr = Point(0.57,0.7),
                                                    text = 'Torch power:',
                                                    textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                                    colour = (1,0,0,1),
                                                    scale = 8,
                                                    alignment = drawing.texture.TextAlignments.CENTRE)
        self.info_box.torch_data.power = ui.PowerBar(self.info_box.torch_data,
                                                     pos = Point(0.5,0.36),
                                                     tr = Point(1,0.66),
                                                     level = 0.6,
                                                     bar_colours = (drawing.constants.colours.red,
                                                                    drawing.constants.colours.yellow,
                                                                    drawing.constants.colours.green),
                                                     border_colour = drawing.constants.colours.white)
        self.info_box.torch_data.Disable()
        self.inv_quads = [drawing.Quad(globals.screen_texture_buffer,tc = globals.ui_atlas.TextureUiCoords('empty.png')) for i in xrange(4)]
        self.sel_quads = [drawing.Quad(globals.screen_texture_buffer,tc = globals.ui_atlas.TextureUiCoords('selected.png')) for i in xrange(4)]
        box_size = 48
        sep_x = int((self.info_box.absolute.size.x*0.2 - box_size*3)/4)
        sep_y = int((self.info_box.absolute.size.y - box_size)/2)
        for i in xrange(4):
            bl = self.info_box.absolute.bottom_left + Point(self.info_box.absolute.size.x*0.03,0) + Point(((i+1)*sep_x)+(i*box_size),sep_y)
            tr = bl + Point(box_size,box_size)
            self.inv_quads[i].SetVertices(bl,tr,9000)
            self.sel_quads[i].SetVertices(bl,tr,9001)
            self.inv_quads[i].Enable()
            self.sel_quads[i].Disable()

        self.inventory = [None,None,None,None]
        self.num_items = 0
        self.current_item = 0
        self.attacking = False
        self.AddItem(Hand(self))
        self.Select(self.num_items-1)
        self.weapon = self.inventory[self.current_item]
        self.interacting = None

    def AddItem(self,item):
        #haxor
        if isinstance(item,TorchItem):
            self.info_box.torch_data.Enable()
        elif isinstance(item,FlareItem):
            self.flare = item
        self.inventory[self.num_items] = item
        item.SetIconQuad(self.inv_quads[self.num_items])
        self.num_items += 1
        #auto select the new item
        #self.Select(self.num_items-1)

    def SelectNext(self):
        self.Select((self.current_item + 1)%self.num_items)

    def SelectPrev(self):
        self.Select((self.current_item + self.num_items - 1 )%self.num_items)


    def Select(self,index):
        if not self.attacking and self.inventory[index]:
            self.sel_quads[self.current_item].Disable()
            self.weapon = self.inventory[index]
            self.current_item = index
            self.sel_quads[self.current_item].Enable()

    def Update(self,t):
        if self.dead:
            globals.current_view.mode = modes.GameOver(globals.current_view)
            globals.current_view.game_over = True
        if self.interacting:
            done = self.interacting.Update(t)
            if done:
                self.deactivate()
        self.UpdateMouse(self.mouse_pos,None)
        super(Player,self).Update(t)
        self.light.Update(t)
        self.torch.Update(t)
        if self.flare:
            self.flare.Update(t)

    def deactivate(self):
        if self.interacting:
            self.interacting.deactivate()
            self.interacting = None
        print 'done'

    def UpdateMouse(self,pos,rel):
        diff = pos - (self.pos*globals.tile_dimensions)
        distance,angle = cmath.polar(complex(diff.x,diff.y))
        self.set_angle(angle+math.pi)
        self.torch.angle = angle

    def TriggerCollide(self,other):
        if isinstance(other,Enemy):
            other.attack(self)


    def click(self, pos, button):
        if button == 1:
            self.weapon.Activate(pos)

        elif button == 4:
            self.SelectNext()
        elif button == 5:
            self.SelectPrev()
        print 'click',pos,button
        #self.torch.on = True

    def unclick(self, pos, button):
        print 'unclick',pos,button
        self.weapon.deactivate()
        #self.torch.on = False

    def AdjustHealth(self,amount):
        super(Player,self).AdjustHealth(amount)
        self.info_box.health_text.SetText('\x81:%d' % self.health,colour = (1,1,0,1))

    def damage(self, amount):
        if globals.time < self.last_damage + self.immune_duration:
            #woop we get to skip
            return
        self.last_damage = globals.time
        self.AdjustHealth(-amount)

class Item(object):
    sounds = None
    def __init__(self,player):
        self.player = player
        self.icon_tc = globals.ui_atlas.TextureUiCoords(self.icon)

    def SetIconQuad(self,quad):
        quad.SetTextureCoordinates(self.icon_tc)

    def Disturbance(self):
        return Point(0,0)

    def Activate(self,pos):
        pass

    def deactivate(self):
        pass

    def Update(self,t):
        return True if t > self.end else False

class Hand(Item):
    icon = 'hand.png'
    def Activate(self,pos):
        #print 'handing!',pos
        td = globals.game_view.map.get_tile_from_world(pos)
        diff = td.pos + (td.size*0.5) - self.player.pos
        distance = diff.length()
        if 1.0 < distance < 2.5:
            done = td.Interact(self.player)
            if not done:
                self.player.interacting = td

    def deactivate(self):
        self.player.deactivate()

class TorchItem(Item):
    icon = 'torch.png'

    def Activate(self,pos):
        self.player.torch.turn_on()

    def deactivate(self):
        self.player.torch.turn_off()

class FlareItem(Item):
    icon = 'flare.png'
    speed = 0.05
    def __init__(self,player):
        super(FlareItem,self).__init__(player)
        self.end = None

    def Activate(self,pos):
        if self.end:
            print 'flares exhausted'
            return
        self.start_pos = self.player.pos
        self.end_pos = globals.game_view.mouse_world.to_float()/globals.tile_dimensions

        self.diff = self.end_pos - self.start_pos
        self.duration = self.diff.length()/self.speed
        self.start = globals.time
        self.end = globals.time + self.duration

        self.light = Light(self.start_pos, radius=200)

    def Update(self,t):
        if not self.end:
            return
        if globals.time > self.end:
            #hack so we don't get updated anymore
            #self.player.flare = None
            return
        progress = float(globals.time - self.start)/self.duration
        partial = self.start_pos + (self.diff*progress)
        self.light.set_pos( partial )
        print 'x',progress,partial


class CommsItem(Item):
    icon = 'comms.png'
