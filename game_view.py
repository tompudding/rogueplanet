from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random
import actors

class Viewpos(object):
    follow_threshold = 0
    max_away = Point(100,20)
    shake_radius = 10
    def __init__(self,point):
        self._pos = point
        self.NoTarget()
        self.follow = None
        self.follow_locked = False
        self.t = 0
        self.shake_end = None
        self.shake_duration = 1
        self.shake = Point(0,0)
        self.last_update   = globals.time

    def NoTarget(self):
        self.target        = None
        self.target_change = None
        self.start_point   = None
        self.target_time   = None
        self.start_time    = None

    @property
    def pos(self):
        return self._pos + self.shake

    def Set(self,point):
        self._pos = point.to_int()
        self.NoTarget()

    def ScreenShake(self,duration):
        self.shake_end = globals.time + duration
        self.shake_duration = float(duration)

    def SetTarget(self,point,t,rate=2,callback = None):
        #Don't fuck with the view if the player is trying to control it
        rate /= 4.0
        self.follow        = None
        self.follow_start  = 0
        self.follow_locked = False
        self.target        = point.to_int()
        self.target_change = self.target - self._pos
        self.start_point   = self._pos
        self.start_time    = t
        self.duration      = self.target_change.length()/rate
        self.callback      = callback
        if self.duration < 200:
            self.duration  = 200
        self.target_time   = self.start_time + self.duration

    def Follow(self,t,actor):
        """
        Follow the given actor around.
        """
        self.follow        = actor
        self.follow_start  = t
        self.follow_locked = False

    def HasTarget(self):
        return self.target != None

    def Skip(self):
        self._pos = self.target
        self.NoTarget()
        if self.callback:
            self.callback(self.t)
            self.callback = None

    def Update(self,t):
        try:
            return self.update(t)
        finally:
            self._pos = self._pos.to_int()

    def update(self,t):
        self.t = t
        elapsed = t - self.last_update
        self.last_update = t

        if self.shake_end:
            if t >= self.shake_end:
                self.shake_end = None
                self.shake = Point(0,0)
            else:
                left = (self.shake_end - t)/self.shake_duration
                radius = left*self.shake_radius
                self.shake = Point(random.random()*radius,random.random()*radius)

        if self.follow:
            #We haven't locked onto it yet, so move closer, and lock on if it's below the threshold
            fpos = (self.follow.GetPosCentre()*globals.tile_dimensions).to_int() + globals.screen*Point(0,0.03)
            if not fpos:
                return
            target = fpos - (globals.screen*0.5).to_int()
            diff = target - self._pos
            #print diff.SquareLength(),self.follow_threshold
            direction = diff.direction()

            if abs(diff.x) < self.max_away.x and abs(diff.y) < self.max_away.y:
                adjust = diff*0.02*elapsed*0.06
            else:
                adjust = diff*0.03*elapsed*0.06
            #adjust = adjust.to_int()
            if adjust.x == 0 and adjust.y == 0:
                adjust = direction
            self._pos += adjust
            return

        elif self.target:
            if t >= self.target_time:
                self._pos = self.target
                self.NoTarget()
                if self.callback:
                    self.callback(t)
                    self.callback = None
            elif t < self.start_time: #I don't think we should get this
                return
            else:
                partial = float(t-self.start_time)/self.duration
                partial = partial*partial*(3 - 2*partial) #smoothstep
                self._pos = (self.start_point + (self.target_change*partial)).to_int()


class TileTypes:
    GRASS               = 1
    WALL                = 2
    TILE                = 3
    PLAYER              = 4
    LIGHT               = 5
    PANELS              = 6,
    CHAIR               = 7,
    DOOR_CLOSED         = 8,
    DOOR_OPEN           = 9,
    SENTRY_LIGHT        = 10,
    CRATE               = 11,
    HEALTH_STATION      = 12,
    ENEMY               = 13,
    RECHARGE_STATION    = 14,
    REDALERT_STATION    = 15

    Impassable = set([WALL, PANELS, CHAIR, DOOR_CLOSED, CRATE, HEALTH_STATION, REDALERT_STATION, RECHARGE_STATION])
    Doors = set([DOOR_CLOSED, DOOR_OPEN])

class TileData(object):
    texture_names = {TileTypes.GRASS         : 'grass.png',
                     TileTypes.WALL          : 'wall.png',
                     TileTypes.TILE          : 'tile.png',
                     TileTypes.PANELS        : 'tile.png',
                     TileTypes.CHAIR         : 'tile.png',
                     TileTypes.PLAYER        : 'tile.png',
                     TileTypes.CRATE         : 'crate.png',
                     TileTypes.HEALTH_STATION : 'health_station.png',
                     TileTypes.RECHARGE_STATION : 'recharge_station.png',
                     TileTypes.REDALERT_STATION : 'redalert_station.png',
                     TileTypes.DOOR_CLOSED   : 'door_closed.png',
                     TileTypes.DOOR_OPEN     : 'door_open.png'}

    def __init__(self, type, pos, last_type, parent):
        self.pos  = pos
        self.type = type
        self.actors = {}
        try:
            self.name = self.texture_names[type]
        except KeyError:
            self.name = self.texture_names[TileTypes.GRASS]
        #How big are we?
        self.size = ((globals.atlas.TextureSubimage(self.name).size)/globals.tile_dimensions).to_int()
        self.quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords(self.name))
        bl        = pos * globals.tile_dimensions
        tr        = bl + self.size*globals.tile_dimensions
        self.quad.SetVertices(bl,tr,0)
    def Delete(self):
        self.quad.Delete()
    def Interact(self,player):
        pass
    def deactivate(self):
        pass
    def Update(self,t):
        pass
    def AddActor(self,actor):
        self.actors[actor] = True
    def Interacted(self):
        pass

    def RemoveActor(self,actor):
        try:
            del self.actors[actor]
        except KeyError:
            pass


class LightTile(TileData):
    def __init__(self, type, pos, last_type, parent):
        #Firstly decide what kind of tile we want
        super(LightTile,self).__init__(last_type,pos,last_type,parent)
        self.light = actors.Light(pos)

class SentryLightTile(TileData):
    count = 0
    angles = [math.pi/2,math.pi/2,0,math.pi,3*math.pi/2,3*math.pi/2]
    def __init__(self, type, pos, last_type, parent):
        #Firstly decide what kind of tile we want
        super(SentryLightTile,self).__init__(TileTypes.GRASS,pos,last_type,parent)
        #which direction are we pointing? It goes up, up, left, right, down, down
        self.light = actors.SentryLight(pos,self.angles[SentryLightTile.count],0.9,parent)
        print SentryLightTile.count
        SentryLightTile.count += 1

class Door(TileData):
    locked = False
    def __init__(self, type, pos, last_type, parent):
        super(Door, self).__init__(type, pos, last_type, parent)
    def Toggle(self):
        if self.type == TileTypes.DOOR_CLOSED:
            self.type = TileTypes.DOOR_OPEN
            #globals.sounds.dooropen.play()
        else:
            self.type = TileTypes.DOOR_CLOSED
            #globals.sounds.doorclosed.play()
        self.quad.SetTextureCoordinates(globals.atlas.TextureSpriteCoords(self.texture_names[self.type]))

    def Interact(self,player):
        if not self.locked:
            self.Toggle()
        else:
            print 'it\'s locked',player.has_key
            if player.has_key:
                #play an unlocking sound
                self.Toggle()
            else:
                #play a locked sound
                pass
        return True

class LockedDoor(Door):
    locked = True

class HealthStation(TileData):
    def Interact(self,player):
        if player.health == player.initial_health:
            #tell the player that something would have happened
            pass
        else:
            extra = player.initial_health - player.health
            player.AdjustHealth(extra)
        return True

class RechargeStation(TileData):
    def Interact(self,player):
        if not player.info_box.torch_data.enabled:
            #play sound
            return
        if player.torch.level == player.torch.max_level:
            #tell the player that something would have happened
            pass
        else:
            extra = player.torch.max_level - player.torch.level
            player.torch.adjust_level(extra)
        return True

class RedAlertStation(TileData):
    def __init__(self, type, pos, last_type, parent):
        self.red_alert = False
        super(RedAlertStation, self).__init__(type, pos, last_type, parent)
    def Toggle(self):
        if self.red_alert:
            self.red_alert = False
            for light in globals.game_view.sentry_lights + globals.lights:
                light.colour = (1,1,1)
            #globals.sounds.dooropen.play()
        else:
            self.red_alert = True
            for light in globals.game_view.sentry_lights + globals.lights:
                light.colour = (1,0,0)


    def Interact(self,player):
        self.Toggle()
        return True


class Crate(TileData):
    duration = 2000
    def __init__(self, type, pos, last_type, parent):
        super(Crate, self).__init__(type, pos, last_type, parent)
        self.player = None
        self.interact_count = 0

    def Interact(self,player):
        self.start = globals.time
        self.player = player
        self.end = self.start + self.duration
        globals.game_view.interact_box.Enable()
        return False

    def Update(self,t):
        if globals.time > self.end:
            self.Interacted()
            self.deactivate()
            return True
        progress = float(globals.time - self.start)/self.duration
        globals.game_view.interact_box.progress.SetBarLevel(progress)

    def deactivate(self):
        globals.game_view.interact_box.Disable()
        self.player = None

    def Interacted(self):
        self.interact_count += 1

class TorchCrate(Crate):
    def __init__(self, type, pos, last_type, parent):
        super(TorchCrate,self).__init__(type, pos, last_type, parent)
        self.light = actors.FixedLight( self.pos, self.size )
    def Interacted(self):
        super(TorchCrate, self).Interacted()
        if self.interact_count == 1 and self.player:
            self.player.AddItem(actors.TorchItem(self.player))

class FlareCrate(Crate):
    duration = 1000
    def Interacted(self):
        super(FlareCrate, self).Interacted()
        if self.interact_count == 1 and self.player:
            self.player.AddItem(actors.FlareItem(self.player))

class CommsCrate(Crate):
    duration = 10000
    def Interacted(self):
        super(CommsCrate, self).Interacted()
        if self.interact_count == 1 and self.player:
            self.player.AddItem(actors.CommsItem(self.player))
            #play has key sound
            self.player.has_key = True

class BatteriesCrate(Crate):
    duration = 2000
    def Interacted(self):
        super(BatteriesCrate, self).Interacted()
        if self.interact_count == 1 and self.player:
            self.player.torch.burn_rate = 0
            self.player.torch.on_penalty = 0


class TiliumCrate(Crate):
    duration = 10000
    def Interacted(self):
        super(TiliumCrate, self).Interacted()
        if self.interact_count == 1 and self.player:
            self.player.tilium = True


crate_types = [BatteriesCrate, TorchCrate, CommsCrate, FlareCrate, TiliumCrate]
door_types = [Door,Door,LockedDoor]

def TileDataFactory(map,type,pos,last_type,parent):
    #Why don't I just use a dictionary for this?

    if type in TileTypes.Doors:
        door_type = door_types.pop(0)
        return door_type(type, pos, last_type,parent)
    elif type == TileTypes.LIGHT:
        return LightTile(type,pos,last_type,parent)
    elif type == TileTypes.SENTRY_LIGHT:
        return SentryLightTile(type,pos,last_type,parent)
    elif type == TileTypes.CRATE:
        crate_type = crate_types.pop(0)
        return crate_type(type, pos, last_type, parent)
    elif type == TileTypes.HEALTH_STATION:
        return HealthStation(type, pos, last_type, parent)
    elif type == TileTypes.REDALERT_STATION:
        return RedAlertStation(type, pos, last_type, parent)
    elif type == TileTypes.RECHARGE_STATION:
        return RechargeStation(type, pos, last_type, parent)
    return TileData(type,pos,last_type,parent)

class GameMap(object):
    input_mapping = {' ' : TileTypes.GRASS,
                     '.' : TileTypes.TILE,
                     '|' : TileTypes.WALL,
                     '-' : TileTypes.WALL,
                     '+' : TileTypes.WALL,
                     'X' : TileTypes.PLAYER,
                     'p' : TileTypes.PANELS,
                     'c' : TileTypes.CHAIR,
                     's' : TileTypes.SENTRY_LIGHT,
                     'd' : TileTypes.DOOR_CLOSED,
                     'h' : TileTypes.HEALTH_STATION,
                     'r' : TileTypes.RECHARGE_STATION,
                     'R' : TileTypes.REDALERT_STATION,
                     'l' : TileTypes.LIGHT,
                     'e' : TileTypes.ENEMY,
                     'C' : TileTypes.CRATE}

    def __init__(self,name,parent):
        self.size   = Point(120,50)
        self.data   = [[TileTypes.GRASS for i in xrange(self.size.y)] for j in xrange(self.size.x)]
        self.object_cache = {}
        self.object_list = []
        self.actors = []
        self.doors  = []
        self.player = None
        self.parent = parent
        y = self.size.y - 1
        player_pos = None
        with open(name) as f:
            last = None
            for line in f:
                line = line.strip('\n')
                if len(line) < self.size.x:
                    line += ' '*(self.size.x - len(line))
                if len(line) > self.size.x:
                    line = line[:self.size.x]
                for inv_x,tile in enumerate(line[::-1]):
                    x = self.size.x-1-inv_x

                    #try:
                    if 1:
                        #hack, also give the adjacent tile so we know what kind of background to put it on...
                        td = TileDataFactory(self,self.input_mapping[tile],Point(x,y),last,parent)
                        last = self.input_mapping[tile]
                        for tile_x in xrange(td.size.x):
                            for tile_y in xrange(td.size.y):
                                if self.data[x+tile_x][y+tile_y] != TileTypes.GRASS:
                                    self.data[x+tile_x][y+tile_y].Delete()
                                    self.data[x+tile_x][y+tile_y] = TileTypes.GRASS
                                if self.data[x+tile_x][y+tile_y] == TileTypes.GRASS:
                                    self.data[x+tile_x][y+tile_y] = td
                        if self.input_mapping[tile] == TileTypes.PLAYER:
                            player_pos = Point(x+0.2,y)
                        if self.input_mapping[tile] == TileTypes.ENEMY:
                            self.parent.enemy_positions.append(Point(x+0.2,y))
                    #except KeyError:
                    #    raise globals.types.FatalError('Invalid map data')
                y -= 1
                if y < 0:
                    break
        if not player_pos:
            raise Exception('No player defined')
        self.player = actors.Player(self,player_pos)
        self.actors.append(self.player)

    def AddObject(self,obj):
        self.object_list.append(obj)
        #Now for each tile that the object touches, put it in the cache
        for tile in obj.CoveredTiles():
            self.object_cache[tile] = obj

    def AddActor(self,pos,actor):
        try:
            self.data[pos.x][pos.y].AddActor(actor)
        except IndexError:
            pass

    def RemoveActor(self,pos,actor):
        try:
            self.data[pos.x][pos.y].RemoveActor(actor)
        except IndexError:
            pass

    def get_tile_from_world(self,pos):
        pos = (pos/globals.tile_dimensions).to_int()
        print pos
        try:
            return self.data[pos.x][pos.y]
        except IndexError:
            return None

class TimeOfDay(object):
    def __init__(self,t):
        self.Set(t)

    def Set(self,t):
        self.t = t

    def Daylight(self):
        #Direction will be
        a_k = 0.2
        d_k = 0.4
        r = 1000
        b = -1.5
        t = (self.t+0.75)%1.0
        a = t*math.pi*2
        z = math.sin(a)*r
        p = math.cos(a)*r
        x = math.cos(b)*p
        y = math.sin(b)*p
        if t < 0.125:
            #dawn
            colour  = [d_k*math.sin(40*t/math.pi) for i in (0,1,2)]
            ambient = [a_k*math.sin(40*t/math.pi) for i in (0,1,2)]
        elif t < 0.375:
            #daylight
            colour = (d_k,d_k,d_k)
            ambient = (a_k,a_k,a_k)
        elif t < 0.5:
            #dusk
            colour = (d_k*math.sin(40*(t+0.25)/math.pi) for i in (0,1,2))
            ambient = [a_k*math.sin(40*(t+0.25)/math.pi) for i in (0,1,2)]
        else:
            x,y,z = (1,1,1)
            colour = (0,0,0)
            ambient = (0,0,0)

        return (-x,-y,-z),colour,ambient,ambient[0]/a_k

    def Ambient(self):
        t = (self.t+0.75)%1.0
        return (0.5,0.5,0.5)

    def Nightlight(self):
        #Direction will be

        return (1,3,-5),(0.25,0.25,0.4)

class GameView(ui.RootElement):
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.sentry_lights = []
        self.enemies = []
        globals.ui_atlas = drawing.texture.TextureAtlas('ui_atlas_0.png','ui_atlas.txt',extra_names=False)
        self.enemy_positions = []
        self.map = GameMap('level1.txt',self)
        self.map.world_size = self.map.size * globals.tile_dimensions
        self.viewpos = Viewpos(Point(100,400))
        self.player_direction = Point(0,0)
        self.game_over = False
        self.mouse_world = Point(0,0)
        self.mouse_pos = Point(0,0)
        #pygame.mixer.music.load('music.ogg')
        #self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        #skip titles for development of the main game
        self.mode = modes.Titles(self)
        self.light      = drawing.Quad(globals.light_quads)
        self.light.SetVertices(Point(0,0),
                               globals.screen_abs - Point(0,0),
                               0)
        self.nightlight      = drawing.Quad(globals.nightlight_quads)
        self.nightlight.SetVertices(Point(0,0),
                               globals.screen_abs - Point(0,0),
                               0.01)
        self.timeofday = TimeOfDay(0.1)
        #self.mode = modes.LevelOne(self)
        self.StartMusic()
        self.fixed_light = actors.FixedLight( Point(11,38),Point(26,9) )
        self.interact_box = ui.Box(parent = globals.screen_root,
                                   pos = Point(0.3,0.0),
                                   tr = Point(0.5,0.08),
                                   colour = (0.5,0.5,0.5,0.7))
        self.interact_box.title = ui.TextBox(self.interact_box,
                                             bl = Point(0,0),
                                             tr = Point(1,1),
                                             text = 'Opening...',
                                             textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                             colour = (0,0,0,1),
                                             scale = 9,
                                             alignment = drawing.texture.TextAlignments.CENTRE)
        self.interact_box.progress = ui.PowerBar(self.interact_box,
                                                 pos = Point(0.1,0.3),
                                                 tr = Point(0.9,0.6),
                                                 level = 0.6,
                                                 bar_colours = (drawing.constants.colours.red,
                                                                drawing.constants.colours.yellow,
                                                                drawing.constants.colours.green),
                                                 border_colour = drawing.constants.colours.white)
        self.interact_box.Disable()

        for pos in self.enemy_positions:
            self.enemies.append( actors.Enemy( self.map, pos ) )

    def StartMusic(self):
        pass
        #pygame.mixer.music.play(-1)
        #self.music_playing = True

    def remove_enemy(self,to_remove):
        self.enemies = [enemy for enemy in self.enemies if enemy is not to_remove]

    def Draw(self):
        drawing.ResetState()
        drawing.Translate(-self.viewpos.pos.x,-self.viewpos.pos.y,0)
        drawing.DrawAll(globals.quad_buffer,self.atlas.texture)
        #drawing.DrawNoTexture(globals.line_buffer)
        #drawing.DrawNoTexture(globals.colour_tiles)
        drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture)

    def Update(self,t):
        if self.mode:
            self.mode.Update(t)

        if self.game_over:
            return

        self.t = t
        self.viewpos.Update(t)
        #self.timeofday.t = float(t)/10000

        if self.viewpos._pos.x < 0:
            self.viewpos._pos.x = 0
        if self.viewpos._pos.y < 0:
            self.viewpos._pos.y = 0
        if self.viewpos._pos.x > (self.map.world_size.x - globals.screen.x):
            self.viewpos._pos.x = (self.map.world_size.x - globals.screen.x)
        if self.viewpos._pos.y > (self.map.world_size.y - globals.screen.y):
            self.viewpos._pos.y = (self.map.world_size.y - globals.screen.y)

        self.mouse_world = self.viewpos.pos + self.mouse_pos
        self.map.player.mouse_pos = self.mouse_world


        for enemy in self.enemies:
            enemy.Update(t)
        for light in self.sentry_lights:
            light.Update(t)
        self.map.player.Update(t)

    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)

    def KeyDown(self,key):
        self.mode.KeyDown(key)

    def KeyUp(self,key):
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(1)
        self.mode.KeyUp(key)

    def MouseMotion(self,pos,rel,handled):
        #temp hack trying to read the brightness at the coord

        #p = pos*globals.scale
        #x = glReadPixels(p.x,p.y,1,1,GL_RGBA,GL_FLOAT)

        #print 'mouse',pos
        #if self.selected_player != None:
        #    self.selected_player.MouseMotion()
        world_pos = self.viewpos.pos + pos
        self.mouse_pos = pos

        self.mode.MouseMotion(world_pos,rel)

        return super(GameView,self).MouseMotion(pos,rel,handled)

    def MouseButtonDown(self,pos,button):
        if self.mode:
            pos = self.viewpos.pos + pos
            return self.mode.MouseButtonDown(pos,button)
        else:
            return False,False

    def MouseButtonUp(self,pos,button):
        if self.mode:
            pos = self.viewpos.pos + pos
            return self.mode.MouseButtonUp(pos,button)
        else:
            return False,False
