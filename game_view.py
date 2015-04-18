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
    shake_radius = 4
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
    Impassable = set([WALL])

class TileData(object):
    texture_names = {TileTypes.GRASS         : 'grass.png',
                     TileTypes.WALL          : 'wall.png',
                     TileTypes.TILE          : 'tile.png',}

    def __init__(self, type, pos):
        self.pos  = pos
        self.type = type
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

def TileDataFactory(map,type,pos):
    return TileData(type,pos)

class GameMap(object):
    input_mapping = {' ' : TileTypes.GRASS,
                     '.' : TileTypes.TILE,
                     '|' : TileTypes.WALL,
                     '-' : TileTypes.WALL,
                     '+' : TileTypes.WALL,
                     'p' : TileTypes.PLAYER,}
    def __init__(self,name,parent):
        self.size   = Point(89,49)
        self.data   = [[TileTypes.GRASS for i in xrange(self.size.y)] for j in xrange(self.size.x)]
        self.object_cache = {}
        self.object_list = []
        self.actors = []
        self.doors  = []
        self.player = None
        self.parent = parent
        y = self.size.y - 1
        with open(name) as f:
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
                        td = TileDataFactory(self,self.input_mapping[tile],Point(x,y))
                        for tile_x in xrange(td.size.x):
                            for tile_y in xrange(td.size.y):
                                if self.data[x+tile_x][y+tile_y] != TileTypes.GRASS:
                                    self.data[x+tile_x][y+tile_y].Delete()
                                    self.data[x+tile_x][y+tile_y] = TileTypes.GRASS
                                if self.data[x+tile_x][y+tile_y] == TileTypes.GRASS:
                                    self.data[x+tile_x][y+tile_y] = td
                        if self.input_mapping[tile] == TileTypes.PLAYER:
                            self.player = actors.Player(self,Point(x+0.2,y))
                            self.actors.append(self.player)
                    #except KeyError:
                    #    raise globals.types.FatalError('Invalid map data')
                y -= 1
                if y < 0:
                    break

    def AddObject(self,obj):
        self.object_list.append(obj)
        #Now for each tile that the object touches, put it in the cache
        for tile in obj.CoveredTiles():
            self.object_cache[tile] = obj



class GameView(ui.RootElement):
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.map = GameMap('level1.txt',self)
        self.map.world_size = self.map.size * globals.tile_dimensions
        self.viewpos = Viewpos(Point(100,400))
        self.player_direction = Point(0,0)
        self.game_over = False
        self.mouse_pos = Point(0,0)
        #pygame.mixer.music.load('music.ogg')
        #self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        #skip titles for development of the main game
        self.mode = modes.Titles(self)
        #self.mode = modes.LevelOne(self)
        self.StartMusic()

    def StartMusic(self):
        pass
        #pygame.mixer.music.play(-1)
        #self.music_playing = True

    def Draw(self):
        drawing.ResetState()
        drawing.Translate(-self.viewpos.pos.x,-self.viewpos.pos.y,0)
        drawing.DrawAll(globals.quad_buffer,self.atlas.texture.texture)
        #drawing.DrawNoTexture(globals.line_buffer)
        #drawing.DrawNoTexture(globals.colour_tiles)
        drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture.texture)

    def Update(self,t):
        if self.mode:
            self.mode.Update(t)

        if self.game_over:
            return

        self.t = t
        self.viewpos.Update(t)

        if self.viewpos._pos.x < 0:
            self.viewpos._pos.x = 0
        if self.viewpos._pos.y < 0:
            self.viewpos._pos.y = 0
        if self.viewpos._pos.x > (self.map.world_size.x - globals.screen.x):
            self.viewpos._pos.x = (self.map.world_size.x - globals.screen.x)
        if self.viewpos._pos.y > (self.map.world_size.y - globals.screen.y):
            self.viewpos._pos.y = (self.map.world_size.y - globals.screen.y)

        mouse_screen_pos = self.viewpos.pos + self.mouse_pos
        self.map.player.mouse_pos = mouse_screen_pos

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
        #print 'mouse',pos
        #if self.selected_player != None:
        #    self.selected_player.MouseMotion()
        screen_pos = self.viewpos.pos + pos
        self.mouse_pos = pos

        self.mode.MouseMotion(screen_pos,rel)

        return super(GameView,self).MouseMotion(pos,rel,handled)
