# -*- coding: utf-8 -*-
"""
ALMATY CITY - GTA-подобная игра с открытым миром (вид сверху), горизонтальная ориентация.
Pydroid 3: меню Pip -> установить "pygame" (нужен pygame 2.x), затем запусти этот файл.
В настройках Pydroid включи горизонтальную ориентацию. Сохранение: рядом с файлом (almaty_city_save.json).

ALMATY CITY  -  top-down open-world crime game (GTA-style) for Pydroid 3.
Landscape. Touch controls. One file, no external assets.
Install:  Pydroid 3 -> Pip -> install "pygame", then run this file.

On foot : left screen = floating joystick, FIRE = shoot (auto-aim), ACT = enter/exit car / use,
          WPN = next weapon, SPR = sprint.
In car  : <  > steer, GAS / BRAKE, HB = handbrake, HORN, ACT = exit car.
Keyboard (PC): WASD/arrows, SPACE fire/handbrake, E/F act, Q weapon, SHIFT sprint, H horn,
               M map, P/ESC pause.
"""
import os, sys, math, random, json, time, array
import pygame

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()
SAVE_PATH = os.path.join(HERE, "almaty_city_save.json")

LW, LH = 960, 540          # logical resolution (scaled to the phone screen)
TILE = 48
G = None                   # the Game instance
CV = None                  # logical canvas
SFX = None
LANG = 'en'
RU = {}

WHITE = (255, 255, 255); BLACK = (0, 0, 0); RED = (220, 50, 50); GREEN = (60, 200, 90)
BLUE = (70, 120, 230); YELLOW = (250, 210, 60); ORANGE = (250, 140, 40); GRAY = (120, 120, 125)
DARK = (24, 26, 34)


def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def ang_to(ax, ay, bx, by):
    return math.atan2(by - ay, bx - ax)


def rnd(a, b):
    return random.uniform(a, b)


def chance(p):
    return random.random() < p


def shade(c, k):
    return (int(clamp(c[0] * k, 0, 255)), int(clamp(c[1] * k, 0, 255)), int(clamp(c[2] * k, 0, 255)))


def T(s):
    if LANG == 'ru':
        return RU.get(s, s)
    return s


# ---------------------------------------------------------------- text
FONTS = {}
TEXT_CACHE = {}
FONT_PATH = None


def get_font(size):
    f = FONTS.get(size)
    if f is None:
        f = pygame.font.Font(FONT_PATH, int(size * 0.8)) if FONT_PATH else pygame.font.Font(None, size)
        FONTS[size] = f
    return f


def font_has_cyrillic():
    try:
        f = get_font(24)
        a = pygame.image.tostring(f.render(u"Жы", True, (255, 255, 255)), "RGBA")
        b = pygame.image.tostring(f.render(u"", True, (255, 255, 255)), "RGBA")
        return a != b
    except Exception:
        return False


def text_img(s, size, color):
    key = (s, size, color)
    img = TEXT_CACHE.get(key)
    if img is None:
        if len(TEXT_CACHE) > 700:
            TEXT_CACHE.clear()
        img = get_font(size).render(s, True, color)
        TEXT_CACHE[key] = img
    return img


def draw_text(s, x, y, size=22, color=WHITE, anchor='tl', shadow=True, surf=None):
    surf = surf or CV
    img = text_img(s, size, color)
    w, h = img.get_width(), img.get_height()
    if anchor[1] == 'c':
        x -= w // 2
    elif anchor[1] == 'r':
        x -= w
    if anchor[0] == 'm':
        y -= h // 2
    elif anchor[0] == 'b':
        y -= h
    if shadow:
        surf.blit(text_img(s, size, (0, 0, 0)), (x + 1, y + 1))
    surf.blit(img, (x, y))
    return w


# ---------------------------------------------------------------- sound
class Sfx:
    RATE = 22050

    def __init__(self):
        self.ok = False
        self.snd = {}
        self.volume = 0.8
        self.ch = 1
        try:
            pygame.mixer.init(self.RATE, -16, 1, 512)
            init = pygame.mixer.get_init()
            self.ch = init[2] if init else 1
            self.ok = True
            self.build()
        except Exception:
            self.ok = False

    def tone(self, f0, f1, dur, noise=0.0, vol=0.5, wave='sq', decay=2.0):
        n = int(self.RATE * dur)
        buf = array.array('h')
        ph = 0.0
        for i in range(n):
            t = i / float(n)
            ph += (f0 + (f1 - f0) * t) / self.RATE
            if wave == 'sq':
                s = 1.0 if (ph % 1.0) < 0.5 else -1.0
            elif wave == 'saw':
                s = (ph % 1.0) * 2 - 1
            else:
                s = math.sin(ph * 6.2832)
            s = s * (1 - noise) + (random.random() * 2 - 1) * noise
            v = int(s * ((1 - t) ** decay) * vol * 30000)
            for _ in range(self.ch):
                buf.append(v)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def build(self):
        t = self.tone
        self.snd = {
            'pistol': t(900, 200, 0.12, 0.8, 0.6), 'smg': t(1100, 300, 0.07, 0.8, 0.5),
            'shotgun': t(500, 80, 0.25, 0.9, 0.8), 'rifle': t(800, 150, 0.1, 0.85, 0.6),
            'rocket': t(220, 60, 0.5, 0.7, 0.6), 'boom': t(120, 30, 0.8, 1.0, 0.9, 'sq', 1.5),
            'punch': t(200, 90, 0.08, 0.5, 0.6), 'hit': t(300, 100, 0.1, 0.9, 0.4),
            'pickup': t(600, 1300, 0.16, 0.0, 0.4, 'sin'), 'cash': t(1000, 1700, 0.12, 0.0, 0.4, 'sin'),
            'horn': t(330, 330, 0.4, 0.05, 0.35, 'sq', 0.4), 'crash': t(160, 40, 0.3, 0.95, 0.7),
            'win': t(500, 1000, 0.5, 0.0, 0.5, 'sin', 0.8), 'fail': t(400, 100, 0.6, 0.1, 0.5, 'saw', 0.8),
            'siren': t(650, 1000, 0.5, 0.0, 0.25, 'sq', 0.2), 'click': t(800, 800, 0.03, 0.2, 0.3),
        }

    def play(self, name, vol=1.0, x=None, y=None):
        if not self.ok:
            return
        s = self.snd.get(name)
        if s is None:
            return
        if x is not None:
            d = dist(x, y, CAM[0] + LW / 2, CAM[1] + LH / 2)
            vol *= clamp(1.0 - d / 900.0, 0.0, 1.0)
            if vol < 0.06:
                return
        s.set_volume(clamp(vol * self.volume, 0, 1))
        s.play()


CAM = [0.0, 0.0]


def play(name, vol=1.0, x=None, y=None):
    if SFX is not None:
        SFX.play(name, vol, x, y)


# ---------------------------------------------------------------- controls
FOOT_LAYOUT = {'fire': (880, 430, 52), 'act': (775, 478, 36), 'wpn': (905, 318, 30),
               'sprint': (782, 380, 30), 'pause': (925, 32, 24), 'map': (865, 32, 24), 'phone': (805, 32, 24)}
CAR_LAYOUT = {'left': (95, 450, 50), 'right': (225, 450, 50), 'gas': (880, 440, 54), 'brake': (765, 478, 40),
              'act': (775, 372, 32), 'horn': (690, 410, 26), 'hb': (665, 485, 28), 'fire': (905, 322, 30),
              'pause': (925, 32, 24), 'map': (865, 32, 24), 'phone': (805, 32, 24), 'radio': (745, 32, 24)}


class Controls:
    STICK_R = 70.0

    def __init__(self):
        self.sw, self.sh = LW, LH
        self.scale, self.ox, self.oy = 1.0, 0.0, 0.0
        self.fingers = {}
        self.finger_mode = False
        self.menu_mode = False
        self.keys = set()
        self.downs = []
        self.pressed = set()
        self.held = set()
        self.mode = 'foot'
        self.layout = FOOT_LAYOUT
        self.mx = self.my = 0.0
        self.steer = self.gas = self.brake = 0.0
        self.fire = self.sprint = self.horn = self.hb = False

    def set_screen(self, sw, sh):
        self.sw, self.sh = sw, sh
        self.scale = min(sw / float(LW), sh / float(LH))
        self.ox = (sw - LW * self.scale) / 2.0
        self.oy = (sh - LH * self.scale) / 2.0

    def to_logical(self, px, py):
        return (px - self.ox) / self.scale, (py - self.oy) / self.scale

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        self.layout = CAR_LAYOUT if mode == 'car' else FOOT_LAYOUT
        for f in self.fingers.values():
            if f['role'] == 'btn' and f['btn'] not in self.layout:
                f['role'] = 'ui'
            elif f['role'] == 'stick' and mode == 'car':
                f['role'] = 'ui'

    def _down(self, fid, x, y):
        self.downs.append((x, y))
        f = {'x': x, 'y': y, 'sx': x, 'sy': y, 'role': 'ui', 'btn': None, 't0': time.time()}
        if not self.menu_mode:
            for name, (cx, cy, r) in self.layout.items():
                if dist(x, y, cx, cy) <= r * 1.2:
                    f['role'] = 'btn'
                    f['btn'] = name
                    self.pressed.add(name)
                    break
            else:
                if self.mode == 'foot' and x < LW * 0.5 and y > 90:
                    if not any(o['role'] == 'stick' for o in self.fingers.values()):
                        f['role'] = 'stick'
                        f['sx'] = clamp(x, 100, 380)
                        f['sy'] = clamp(y, 170, LH - 90)
        self.fingers[fid] = f

    def _move(self, fid, x, y):
        f = self.fingers.get(fid)
        if f:
            f['x'], f['y'] = x, y

    def _up(self, fid):
        self.fingers.pop(fid, None)

    def handle(self, e):
        t = e.type
        if t == pygame.FINGERDOWN:
            self.finger_mode = True
            x, y = self.to_logical(e.x * self.sw, e.y * self.sh)
            self._down(e.finger_id, x, y)
        elif t == pygame.FINGERMOTION:
            x, y = self.to_logical(e.x * self.sw, e.y * self.sh)
            self._move(e.finger_id, x, y)
        elif t == pygame.FINGERUP:
            self._up(e.finger_id)
        elif t == pygame.MOUSEBUTTONDOWN and not self.finger_mode and not getattr(e, 'touch', False):
            x, y = self.to_logical(*e.pos)
            self._down(-1, x, y)
        elif t == pygame.MOUSEMOTION and not self.finger_mode and not getattr(e, 'touch', False):
            x, y = self.to_logical(*e.pos)
            self._move(-1, x, y)
        elif t == pygame.MOUSEBUTTONUP and not self.finger_mode and not getattr(e, 'touch', False):
            self._up(-1)
        elif t == pygame.KEYDOWN:
            self.keys.add(e.key)
            k = e.key
            if k in (pygame.K_e, pygame.K_f):
                self.pressed.add('act')
            elif k == pygame.K_q:
                self.pressed.add('wpn')
            elif k == pygame.K_m:
                self.pressed.add('map')
            elif k in (pygame.K_p, pygame.K_ESCAPE):
                self.pressed.add('pause')
            elif k == pygame.K_TAB:
                self.pressed.add('phone')
            elif k == pygame.K_r:
                self.pressed.add('radio')
        elif t == pygame.KEYUP:
            self.keys.discard(e.key)

    def poll(self):
        held = set()
        mx = my = 0.0
        for f in self.fingers.values():
            if f['role'] == 'btn':
                held.add(f['btn'])
            elif f['role'] == 'stick':
                dx, dy = f['x'] - f['sx'], f['y'] - f['sy']
                d = math.hypot(dx, dy)
                if d > 1:
                    k = min(d, self.STICK_R) / self.STICK_R
                    if k > 0.18:
                        mx, my = dx / d * k, dy / d * k
        K = self.keys
        kl = pygame.K_LEFT in K or pygame.K_a in K
        kr = pygame.K_RIGHT in K or pygame.K_d in K
        ku = pygame.K_UP in K or pygame.K_w in K
        kd = pygame.K_DOWN in K or pygame.K_s in K
        if kl or kr or ku or kd:
            mx = float(kr) - float(kl)
            my = float(kd) - float(ku)
            d = math.hypot(mx, my)
            if d > 1:
                mx, my = mx / d, my / d
        self.mx, self.my = mx, my
        self.steer = (1.0 if ('right' in held or kr) else 0.0) - (1.0 if ('left' in held or kl) else 0.0)
        self.gas = 1.0 if ('gas' in held or ku) else 0.0
        self.brake = 1.0 if ('brake' in held or kd) else 0.0
        space = pygame.K_SPACE in K
        self.fire = 'fire' in held or space
        self.hb = 'hb' in held or space
        self.sprint = 'sprint' in held or pygame.K_LSHIFT in K or pygame.K_RSHIFT in K
        self.horn = 'horn' in held or pygame.K_h in K
        self.held = held

    def end_frame(self):
        self.downs = []
        self.pressed = set()

    def stick_state(self):
        for f in self.fingers.values():
            if f['role'] == 'stick':
                return f
        return None


# ================================================================ WORLD
GRASS, ROAD, SIDE, BLDG, WATER, SAND, PARK, DOCK, LOT, PLAZA = range(10)
TILE_COL = {GRASS: (74, 132, 72), ROAD: (58, 60, 66), SIDE: (152, 152, 158), BLDG: (90, 90, 90),
            WATER: (38, 98, 168), SAND: (216, 198, 142), PARK: (62, 150, 82), DOCK: (140, 100, 62),
            LOT: (84, 86, 92), PLAZA: (176, 170, 158)}
CELL = 12
COLS, ROWS = 9, 7
WT = COLS * CELL + 2 + 14        # world width in tiles (14 = harbour)
HT = ROWS * CELL + 2
WPX, HPX = WT * TILE, HT * TILE
DIST_NAMES = {'down': 'Downtown', 'sub': 'Green Hills', 'ind': 'Industrial Zone', 'com': 'Market District',
              'park': 'Central Park', 'port': 'Harbour', 'res': 'Old Town'}


def district_of(i, j):
    if i >= COLS:
        return 'port'
    if 3 <= i <= 5 and 2 <= j <= 4:
        return 'down'
    if i <= 2 and j >= 4:
        return 'ind'
    if i >= 6 and j >= 4:
        return 'ind' if j == 6 else 'com'
    if i <= 2 and j <= 3:
        return 'sub'
    if i >= 6 and j <= 3:
        return 'sub' if j <= 1 else 'res'
    return 'com'


class Prop:
    __slots__ = ('kind', 'x', 'y', 'r', 'hp', 'ang', 'vx', 'vy', 'alive', 'col')

    def __init__(self, kind, x, y, r, hp=1, col=(0, 0, 0)):
        self.kind, self.x, self.y, self.r, self.hp = kind, x, y, r, hp
        self.ang = 0.0
        self.vx = self.vy = 0.0
        self.alive = True
        self.col = col


class World:
    def __init__(self, seed=7):
        self.rng = random.Random(seed)
        self.t = bytearray(WT * HT)
        self.var = bytearray(WT * HT)
        self.buildings = []
        self.props = []
        self.pois = []              # points of interest (shops etc.)
        self.parks = []
        self.sidewalk_spawns = []
        self.garages = []
        self.hosp = (0, 0)
        self.police_hq = (0, 0)
        self.houses = []
        self.chunks = {}
        self.bspr = {}
        self.build()
        self.hash = {}
        for p in self.props:
            self.hash.setdefault((int(p.x // 96), int(p.y // 96)), []).append(p)
        self.mini = self.make_mini()

    # ------------------------------------------------------------ helpers
    def tile(self, tx, ty):
        if tx < 0 or ty < 0 or tx >= WT or ty >= HT:
            return BLDG
        return self.t[ty * WT + tx]

    def setr(self, x, y, w, h, v):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if 0 <= xx < WT and 0 <= yy < HT:
                    self.t[yy * WT + xx] = v

    def solid_px(self, x, y):
        return self.tile(int(x // TILE), int(y // TILE)) == BLDG

    def add_prop(self, kind, tx, ty, r, hp=1, col=(0, 0, 0), jitter=True):
        x = (tx + 0.5) * TILE + (self.rng.uniform(-8, 8) if jitter else 0)
        y = (ty + 0.5) * TILE + (self.rng.uniform(-8, 8) if jitter else 0)
        p = Prop(kind, x, y, r, hp, col)
        self.props.append(p)
        return p

    def add_building(self, x, y, w, h, kind='shop', name=None, col=None, floors=None):
        R = self.rng
        self.setr(x, y, w, h, BLDG)
        if col is None:
            col = R.choice([(170, 90, 80), (190, 170, 120), (120, 130, 150), (160, 160, 165), (140, 110, 90),
                            (110, 140, 120), (180, 140, 100), (150, 120, 140)])
        b = {'x': x, 'y': y, 'w': w, 'h': h, 'kind': kind, 'name': name, 'col': col,
             'fl': floors or R.randint(2, 5), 'seed': R.randint(0, 9999)}
        self.buildings.append(b)
        return b

    def poi(self, kind, tx, ty, name):
        self.pois.append({'kind': kind, 'x': (tx + 0.5) * TILE, 'y': (ty + 0.5) * TILE, 'name': name, 'cool': 0.0})

    # ------------------------------------------------------------ generation
    def build(self):
        R = self.rng
        # base: grass everywhere, roads, harbour
        self.setr(0, 0, WT, HT, GRASS)
        for k in range(WT * HT):
            self.var[k] = R.randint(0, 7)
        for r in range(ROWS + 1):
            self.setr(0, r * CELL, COLS * CELL + 2, 2, ROAD)
        for c in range(COLS + 1):
            self.setr(c * CELL, 0, 2, HT, ROAD)
        # harbour: sand strip then water, docks
        hx = COLS * CELL + 2
        self.setr(hx, 0, 14, HT, WATER)
        self.setr(hx, 0, 3, HT, SAND)
        for r in range(ROWS):
            y0 = r * CELL + 3
            self.setr(hx + 2, y0 + 1, 8, 2, DOCK)
            self.setr(hx + 9, y0 + 1, 2, 5, DOCK)
        self.setr(hx, 0, 3, 2, ROAD)
        # blocks
        for j in range(ROWS):
            for i in range(COLS):
                self.make_block(i, j)
        # harbour warehouses on the sand
        for j in range(0, ROWS, 2):
            self.add_building(hx - 0, j * CELL + 4, 2, 4, 'industrial', None, (130, 130, 140), 1)
        self.setr(hx, 0, 3, HT, SAND)
        for b in [b for b in self.buildings if b['x'] >= hx]:
            self.setr(b['x'], b['y'], b['w'], b['h'], BLDG)
        # crates and lamps around roads
        for c in range(COLS + 1):
            for r in range(ROWS + 1):
                x0, y0 = c * CELL, r * CELL
                if c < COLS and r < ROWS:
                    self.add_prop('lamp', x0 + 2, y0 + 2, 5, 1, jitter=False)
                    self.add_prop('hydrant', x0 + 11, y0 + 11, 5, 1)

    def make_block(self, i, j):
        R = self.rng
        x0, y0 = i * CELL + 2, j * CELL + 2
        d = district_of(i, j)
        # sidewalk ring
        self.setr(x0, y0, 10, 10, SIDE)
        ix, iy = x0 + 1, y0 + 1                  # interior 8x8
        special = {(4, 3): 'plaza', (1, 1): 'hospital', (7, 2): 'police', (4, 1): 'park', (1, 5): 'ammu',
                   (7, 5): 'spray', (5, 5): 'stadium', (7, 1): 'safe', (2, 3): 'dealer', (0, 6): 'safe2',
                   (3, 6): 'junk', (6, 3): 'mall'}
        sp = special.get((i, j))
        if d == 'port':
            return
        if sp == 'park' or (d == 'sub' and (i + j) % 4 == 0 and not sp):
            self.make_park(ix, iy)
        elif sp == 'plaza':
            self.setr(ix, iy, 8, 8, PLAZA)
            self.setr(ix + 2, iy + 2, 4, 4, WATER)
            self.setr(ix + 3, iy + 3, 2, 2, PLAZA)
            for k in range(8):
                self.add_prop('tree', ix + (k % 2) * 7, iy + k, 8, 3)
        elif sp == 'hospital':
            self.setr(ix, iy, 8, 8, PLAZA)
            self.add_building(ix, iy, 8, 5, 'hospital', 'HOSPITAL', (235, 235, 240), 4)
            self.hosp = ((ix + 4) * TILE, (iy + 6) * TILE)
            self.poi('hospital', ix + 4, iy + 6, 'Hospital')
        elif sp == 'police':
            self.setr(ix, iy, 8, 8, LOT)
            self.add_building(ix, iy, 6, 4, 'police', 'POLICE HQ', (60, 80, 130), 3)
            self.police_hq = ((ix + 3) * TILE, (iy + 5) * TILE)
            self.poi('police', ix + 3, iy + 5, 'Police HQ')
            self.garages.append(('police', (ix + 6.5) * TILE, (iy + 6) * TILE))
        elif sp == 'ammu':
            self.setr(ix, iy, 8, 8, LOT)
            self.add_building(ix, iy, 8, 3, 'shop', 'AMMU-NATION', (170, 70, 60), 2)
            self.poi('ammu', ix + 4, iy + 3, 'Ammu-Nation')
            self.add_building(ix, iy + 5, 8, 3, 'shop', 'GUN RANGE', (110, 110, 120), 2)
            self.poi('range', ix + 4, iy + 4, 'Shooting Range')
        elif sp == 'spray':
            self.setr(ix, iy, 8, 8, LOT)
            self.add_building(ix, iy, 8, 3, 'shop', "PAY'N'SPRAY", (230, 190, 60), 2)
            self.poi('spray', ix + 4, iy + 3, "Pay'n'Spray")
            self.add_building(ix, iy + 5, 4, 3, 'shop', 'GARAGE', (130, 90, 70), 2)
            self.poi('garage', ix + 6, iy + 5, 'Car Dealer')
            self.garages.append(('dealer', (ix + 6) * TILE, (iy + 6.5) * TILE))
        elif sp == 'dealer':
            self.setr(ix, iy, 8, 8, LOT)
            self.add_building(ix, iy, 8, 3, 'shop', 'AUTO SALON', (70, 140, 180), 2)
            self.poi('garage', ix + 4, iy + 3, 'Car Dealer')
            self.garages.append(('dealer', (ix + 4) * TILE, (iy + 5.5) * TILE))
            self.add_building(ix + 5, iy + 5, 3, 3, 'house', None, (160, 100, 80), 1)
        elif sp in ('safe', 'safe2'):
            self.setr(ix, iy, 8, 8, GRASS)
            self.add_building(ix + 1, iy + 1, 4, 3, 'house', 'SAFEHOUSE', (200, 190, 120), 2)
            self.poi('safehouse', ix + 3, iy + 4, 'Safehouse')
            self.garages.append(('home', (ix + 6) * TILE, (iy + 5) * TILE))
            for k in range(3):
                self.add_prop('tree', ix + 6 + k % 2, iy + k, 8, 3)
        elif sp == 'stadium':
            self.setr(ix, iy, 8, 8, LOT)
            self.add_building(ix, iy, 8, 1, 'industrial', 'STADIUM', (180, 180, 190), 1)
            self.add_building(ix, iy + 7, 8, 1, 'industrial', None, (180, 180, 190), 1)
            self.setr(ix + 1, iy + 1, 6, 6, PARK)
            self.poi('stunt', ix + 4, iy + 4, 'Stunt Arena')
        elif sp == 'junk':
            self.setr(ix, iy, 8, 8, LOT)
            for k in range(6):
                self.add_prop('crate', ix + R.randint(0, 7), iy + R.randint(0, 7), 12, 2, (150, 110, 60))
            self.add_building(ix, iy, 4, 3, 'industrial', 'SCRAPYARD', (110, 100, 90), 1)
            self.poi('scrap', ix + 5, iy + 3, 'Scrapyard (sell cars)')
        elif sp == 'mall':
            self.setr(ix, iy, 8, 8, LOT)
            self.add_building(ix, iy, 8, 5, 'shop', 'MALL', (210, 120, 150), 3)
            self.poi('clothes', ix + 4, iy + 5, 'Mall (armor & food)')
        elif d == 'down':
            self.setr(ix, iy, 8, 8, PLAZA)
            for (bx, by, bw, bh) in R.choice([[(0, 0, 8, 8)], [(0, 0, 4, 8), (5, 0, 3, 8)],
                                              [(0, 0, 8, 3), (0, 4, 4, 4), (5, 4, 3, 4)]]):
                col = R.choice([(110, 140, 170), (90, 120, 150), (130, 150, 160), (100, 100, 120), (150, 160, 175)])
                self.add_building(ix + bx, iy + by, bw, bh, 'tower', None, col, R.randint(6, 16))
        elif d == 'ind':
            self.setr(ix, iy, 8, 8, LOT)
            for (bx, by, bw, bh) in R.choice([[(0, 0, 8, 4), (0, 5, 5, 3)], [(0, 0, 4, 8), (5, 0, 3, 5)],
                                              [(0, 0, 8, 3), (0, 4, 8, 4)]]):
                self.add_building(ix + bx, iy + by, bw, bh, 'industrial', None,
                                  R.choice([(120, 125, 135), (140, 120, 100), (110, 130, 120)]), 1)
            for k in range(4):
                self.add_prop('crate', ix + R.randint(0, 7), iy + R.randint(0, 7), 12, 2, (150, 110, 60))
        elif d == 'sub':
            self.setr(ix, iy, 8, 8, GRASS)
            for (hx_, hy_) in [(0, 0), (4, 0), (0, 4), (4, 4)]:
                if chance(0.85):
                    b = self.add_building(ix + hx_, iy + hy_, 3, 3, 'house', None, None, 1)
                    self.houses.append(b)
                    self.add_prop('tree', ix + hx_ + 3, iy + hy_ + 3, 8, 3)
        else:
            self.setr(ix, iy, 8, 8, LOT if d == 'com' else GRASS)
            for (bx, by, bw, bh) in R.choice([[(0, 0, 4, 4), (5, 0, 3, 4), (0, 5, 8, 3)],
                                              [(0, 0, 8, 3), (0, 4, 3, 4), (4, 4, 4, 4)],
                                              [(0, 0, 3, 8), (4, 0, 4, 3), (4, 4, 4, 4)]]):
                self.add_building(ix + bx, iy + by, bw, bh, 'shop', None, None, R.randint(2, 4))
        # street furniture on sidewalks
        for k in range(R.randint(1, 3)):
            side = R.randint(0, 3)
            o = R.randint(1, 8)
            tx, ty = [(x0 + o, y0), (x0 + o, y0 + 9), (x0, y0 + o), (x0 + 9, y0 + o)][side]
            if self.tile(tx, ty) == SIDE:
                self.add_prop(R.choice(['bin', 'bench', 'box']), tx, ty, 8, 1)
        for k in range(10):
            self.sidewalk_spawns.append((x0 + R.randint(0, 9), y0 + (0 if chance(0.5) else 9)))
            self.sidewalk_spawns.append((x0 + (0 if chance(0.5) else 9), y0 + R.randint(0, 9)))

    def make_park(self, ix, iy):
        R = self.rng
        self.setr(ix, iy, 8, 8, PARK)
        self.setr(ix + 3, iy, 2, 8, SIDE)
        self.setr(ix, iy + 3, 8, 2, SIDE)
        if chance(0.6):
            self.setr(ix + 5, iy + 5, 3, 3, WATER)
        for k in range(14):
            tx, ty = ix + R.randint(0, 7), iy + R.randint(0, 7)
            if self.tile(tx, ty) == PARK:
                self.add_prop('tree', tx, ty, 9, 3)
        self.parks.append((ix, iy))

    # ------------------------------------------------------------ collisions
    def props_near(self, x, y):
        cx, cy = int(x // 96), int(y // 96)
        out = []
        for a in (cx - 1, cx, cx + 1):
            for b in (cy - 1, cy, cy + 1):
                l = self.hash.get((a, b))
                if l:
                    out.extend(l)
        return out

    def push_circle(self, x, y, r, use_props=True):
        """Resolve circle against solid tiles (and props). Returns x,y,hit_strength."""
        hit = 0.0
        tx0, ty0 = int((x - r) // TILE), int((y - r) // TILE)
        tx1, ty1 = int((x + r) // TILE), int((y + r) // TILE)
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                if self.tile(tx, ty) != BLDG:
                    continue
                rx0, ry0 = tx * TILE, ty * TILE
                cx = clamp(x, rx0, rx0 + TILE)
                cy = clamp(y, ry0, ry0 + TILE)
                dx, dy = x - cx, y - cy
                d2 = dx * dx + dy * dy
                if d2 < r * r:
                    if d2 < 1e-6:
                        mx, my = x - (rx0 + TILE / 2), y - (ry0 + TILE / 2)
                        m = math.hypot(mx, my) or 1
                        x += mx / m * r
                        y += my / m * r
                        hit = max(hit, r)
                    else:
                        d = math.sqrt(d2)
                        x += dx / d * (r - d)
                        y += dy / d * (r - d)
                        hit = max(hit, r - d)
        if use_props:
            for p in self.props_near(x, y):
                if not p.alive or p.kind in ('hydrant_down',):
                    continue
                dx, dy = x - p.x, y - p.y
                rr = r + p.r
                d2 = dx * dx + dy * dy
                if d2 < rr * rr and d2 > 1e-6:
                    d = math.sqrt(d2)
                    x += dx / d * (rr - d)
                    y += dy / d * (rr - d)
                    hit = max(hit, (rr - d) + 0.5)
        return x, y, hit

    def line_clear(self, x0, y0, x1, y1, step=16):
        d = dist(x0, y0, x1, y1)
        n = int(d // step) + 1
        for k in range(1, n):
            t = k / float(n)
            if self.solid_px(lerp(x0, x1, t), lerp(y0, y1, t)):
                return False
        return True

    def ray_hit(self, x0, y0, ang, maxd, step=12):
        """first solid point along ray, returns distance"""
        c, s = math.cos(ang), math.sin(ang)
        d = 0.0
        while d < maxd:
            d += step
            if self.solid_px(x0 + c * d, y0 + s * d):
                return d
        return maxd

    # ------------------------------------------------------------ roads / spawns
    def band_c(self, tx):
        """vertical road band index if tile x is in one, else -1"""
        if tx < 0 or tx > COLS * CELL + 1:
            return -1
        c, o = divmod(tx, CELL)
        return c if o < 2 and c <= COLS else -1

    def band_r(self, ty):
        if ty < 0 or ty >= HT:
            return -1
        r, o = divmod(ty, CELL)
        return r if o < 2 and r <= ROWS else -1

    def is_road(self, x, y):
        return self.tile(int(x // TILE), int(y // TILE)) == ROAD

    def terrain_at(self, x, y):
        return self.tile(int(x // TILE), int(y // TILE))

    def random_road_point(self, near=None, rmin=0, rmax=0):
        for _ in range(60):
            if near:
                a = rnd(0, 6.283)
                d = rnd(rmin, rmax)
                x, y = near[0] + math.cos(a) * d, near[1] + math.sin(a) * d
            else:
                x, y = rnd(60, WPX - 14 * TILE), rnd(60, HPX - 60)
            if self.is_road(x, y):
                return x, y
        return None

    def random_walk_point(self, near=None, rmin=0, rmax=0):
        for _ in range(60):
            if near:
                a = rnd(0, 6.283)
                d = rnd(rmin, rmax)
                x, y = near[0] + math.cos(a) * d, near[1] + math.sin(a) * d
            else:
                x, y = rnd(60, WPX - 60), rnd(60, HPX - 60)
            t = self.terrain_at(x, y)
            if t in (SIDE, GRASS, PARK, PLAZA, LOT, SAND):
                return x, y
        return None

    def lane_pos(self, d, x, y):
        """center of lane for direction d (0 E,1 S,2 W,3 N) closest to x,y"""
        if d in (0, 2):
            r = clamp(int(round((y / TILE - 1) / CELL)), 0, ROWS)
            ty = r * CELL + (1 if d == 0 else 0)
            return (ty + 0.5) * TILE
        c = clamp(int(round((x / TILE - 1) / CELL)), 0, COLS)
        tx = c * CELL + (0 if d == 1 else 1)
        return (tx + 0.5) * TILE

    # ------------------------------------------------------------ minimap
    def make_mini(self):
        s = pygame.Surface((WT, HT))
        for y in range(HT):
            for x in range(WT):
                t = self.t[y * WT + x]
                c = TILE_COL[t]
                if t == BLDG:
                    c = (95, 95, 105)
                elif t in (SIDE, PLAZA):
                    c = (110, 110, 115)
                elif t == ROAD:
                    c = (200, 200, 205)
                elif t == LOT:
                    c = (90, 90, 95)
                s.set_at((x, y), c)
        return s

    # ------------------------------------------------------------ drawing
    def chunk(self, cx, cy):
        key = (cx, cy)
        s = self.chunks.get(key)
        if s is not None:
            return s
        if len(self.chunks) > 48:
            self.chunks.clear()
        CS = 8
        s = pygame.Surface((CS * TILE, CS * TILE))
        for ty in range(cy * CS, min(HT, cy * CS + CS)):
            for tx in range(cx * CS, min(WT, cx * CS + CS)):
                t = self.t[ty * WT + tx]
                px, py = (tx - cx * CS) * TILE, (ty - cy * CS) * TILE
                if t == BLDG:
                    s.fill((60, 62, 66), (px, py, TILE, TILE))
                    continue
                v = self.var[ty * WT + tx]
                col = TILE_COL[t]
                if t in (GRASS, PARK, SAND, LOT):
                    col = shade(col, 0.94 + v * 0.012)
                elif t == WATER:
                    col = shade(col, 0.94 + 0.012 * ((tx * 7 + ty * 13) % 9))
                elif t == SIDE and (tx + ty) % 2 == 0:
                    col = shade(col, 0.95)
                s.fill(col, (px, py, TILE, TILE))
                if t == ROAD:
                    self.road_marks(s, tx, ty, px, py)
                elif t == DOCK:
                    s.fill(shade(col, 0.8), (px, py + 15, TILE, 2))
                    s.fill(shade(col, 0.8), (px, py + 33, TILE, 2))
        self.chunks[key] = s
        return s

    def draw(self, cam, t_night):
        cx, cy = int(cam[0]), int(cam[1])
        CS = 8 * TILE
        for gy in range(max(0, cy // CS), min((HT - 1) // 8, (cy + LH) // CS) + 1):
            for gx in range(max(0, cx // CS), min((WT - 1) // 8, (cx + LW) // CS) + 1):
                CV.blit(self.chunk(gx, gy), (gx * CS - cx, gy * CS - cy))
        for b in self.buildings:
            px, py = b['x'] * TILE - cx, b['y'] * TILE - cy
            w, h = b['w'] * TILE, b['h'] * TILE
            if px > LW or py > LH or px + w < -20 or py + h < -20:
                continue
            CV.fill((70, 72, 70), (px + 8, py + h, w, 8))
            CV.fill((70, 72, 70), (px + w, py + 8, 8, h))
            spr = self.bspr.get(id(b))
            if spr is None:
                if len(self.bspr) > 70:
                    self.bspr.clear()
                spr = pygame.Surface((w, h))
                self.draw_building(b, spr, w, h)
                self.bspr[id(b)] = spr
            CV.blit(spr, (px, py))

    def road_marks(self, s, tx, ty, px, py):
        c, r = self.band_c(tx), self.band_r(ty)
        if c >= 0 and r >= 0:
            return
        if r >= 0 and 1 < tx < COLS * CELL:
            if (ty - r * CELL) == 0 and (tx % 4) < 2:
                s.fill((200, 200, 120), (px + 4, py + TILE - 2, TILE - 8, 3))
            m = tx % CELL
            if m == 2 or m == CELL - 1:
                for k in range(0, TILE, 8):
                    s.fill((210, 210, 210), (px + 8, py + k, TILE - 16, 4))
        elif c >= 0 and 1 < ty < HT - 2:
            if (tx - c * CELL) == 0 and (ty % 4) < 2:
                s.fill((200, 200, 120), (px + TILE - 2, py + 4, 3, TILE - 8))
            m = ty % CELL
            if m == 2 or m == CELL - 1:
                for k in range(0, TILE, 8):
                    s.fill((210, 210, 210), (px + k, py + 8, 4, TILE - 16))

    def draw_building(self, b, surf, w, h):
        col = b['col']
        k = b['kind']
        px = py = 0
        surf.fill(shade(col, 0.62))
        surf.fill(shade(col, 1.0), (3, 3, w - 9, h - 9))
        surf.fill(shade(col, 1.12), (3, 3, w - 9, 3))
        rs = b['seed']
        if k == 'tower':
            pygame.draw.rect(surf, shade(col, 0.8), (10, 10, w - 29, h - 29), 2)
            for gx in range(18, w - 24, 20):
                for gy in range(18, h - 24, 20):
                    surf.fill(shade(col, 1.25 if (gx + gy + rs) % 3 else 0.75), (gx, gy, 12, 12))
            if rs % 3 == 0 and w >= 150:
                pygame.draw.circle(surf, (230, 230, 80), (w // 2, h // 2), 26, 3)
                draw_text('H', w // 2, h // 2, 30, (230, 230, 80), 'mc', False, surf)
        elif k in ('shop', 'house'):
            for gx in range(10, w - 18, 18):
                surf.fill(shade(col, 0.82), (gx, 8, 10, 6))
            if k == 'house':
                pygame.draw.polygon(surf, shade(col, 0.88), [(3, h - 6), (w // 2, 3), (w - 6, h - 6)], 2)
            elif (rs % 4) == 0:
                surf.fill((90, 90, 100), (w - 40, 12, 20, 14))
        elif k == 'industrial':
            for gx in range(12, w - 16, 24):
                surf.fill(shade(col, 0.85), (gx, 6, 6, h - 18))
            if rs % 2:
                pygame.draw.circle(surf, shade(col, 0.7), (w - 24, 20), 10)
        if b['name']:
            kind_col = {'hospital': (220, 40, 40), 'police': (240, 240, 255)}.get(k, WHITE)
            if k == 'hospital':
                surf.fill((220, 40, 40), (w // 2 - 6, 20, 12, 36))
                surf.fill((220, 40, 40), (w // 2 - 18, 32, 36, 12))
            draw_text(T(b['name']) if b['name'] in RU else b['name'], w // 2, h - 16, 22, kind_col, 'mc', True, surf)


# ================================================================ DATA
WEAPONS = {
    'fist': dict(n='Fists', dmg=9, rate=0.36, melee=True, rng=32, price=0, ammo=0, col=(230, 190, 150)),
    'bat': dict(n='Baseball Bat', dmg=26, rate=0.5, melee=True, rng=48, price=150, ammo=0, col=(170, 120, 60)),
    'pistol': dict(n='Pistol', dmg=22, rate=0.30, spd=950, rng=560, spread=0.03, pel=1, price=250, ammo=120, ap=40, col=(60, 60, 70), snd='pistol'),
    'smg': dict(n='Micro SMG', dmg=11, rate=0.075, spd=1000, rng=520, spread=0.10, pel=1, price=900, ammo=300, ap=100, col=(70, 70, 80), snd='smg'),
    'shotgun': dict(n='Shotgun', dmg=10, rate=0.8, spd=900, rng=330, spread=0.26, pel=7, price=1200, ammo=60, ap=30, col=(110, 80, 50), snd='shotgun'),
    'rifle': dict(n='Assault Rifle', dmg=19, rate=0.105, spd=1200, rng=760, spread=0.05, pel=1, price=2500, ammo=400, ap=150, col=(50, 70, 50), snd='rifle'),
    'rpg': dict(n='Rocket Launcher', dmg=170, rate=1.4, spd=520, rng=900, spread=0.0, pel=1, price=6000, ammo=20, ap=5, col=(80, 90, 60), snd='rocket', rocket=True),
    'grenade': dict(n='Grenade', dmg=150, rate=0.8, spd=420, rng=380, spread=0.0, pel=1, price=500, ammo=20, ap=5, col=(60, 100, 60), snd='click', gren=True),
}
WORDER = ['fist', 'bat', 'pistol', 'smg', 'shotgun', 'rifle', 'rpg', 'grenade']

VTYPES = {
    'compact': dict(n='Compact', L=40, W=21, vmax=400, acc=330, hp=90, grip=7.0, turn=2.7, price=1500, cols=[(200, 60, 60), (70, 130, 200), (230, 230, 230), (90, 170, 90), (230, 180, 60)]),
    'sedan': dict(n='Sedan', L=48, W=24, vmax=450, acc=340, hp=110, grip=6.5, turn=2.5, price=3500, cols=[(60, 60, 70), (180, 180, 190), (140, 40, 40), (40, 70, 130), (200, 200, 210)]),
    'sport': dict(n='Sport Coupe', L=48, W=23, vmax=600, acc=470, hp=100, grip=5.5, turn=2.7, price=18000, cols=[(220, 30, 30), (250, 200, 0), (30, 30, 30), (20, 90, 200), (240, 120, 20)]),
    'muscle': dict(n='Muscle Car', L=52, W=25, vmax=560, acc=440, hp=130, grip=4.8, turn=2.4, price=12000, cols=[(30, 100, 60), (200, 80, 20), (30, 30, 40), (150, 20, 20)]),
    'suv': dict(n='SUV', L=54, W=26, vmax=430, acc=300, hp=160, grip=6.2, turn=2.2, price=7000, cols=[(40, 40, 45), (200, 200, 205), (100, 70, 40), (60, 90, 70)]),
    'van': dict(n='Van', L=56, W=26, vmax=360, acc=250, hp=150, grip=6.0, turn=2.0, price=2500, cols=[(230, 230, 230), (80, 100, 140), (200, 190, 120)]),
    'truck': dict(n='Truck', L=74, W=30, vmax=320, acc=200, hp=240, grip=6.0, turn=1.6, price=6000, cols=[(210, 120, 40), (60, 100, 150), (170, 170, 175)]),
    'bus': dict(n='City Bus', L=92, W=30, vmax=280, acc=170, hp=300, grip=6.0, turn=1.3, price=0, cols=[(40, 110, 200), (220, 90, 40)]),
    'taxi': dict(n='Taxi', L=48, W=24, vmax=470, acc=350, hp=110, grip=6.5, turn=2.5, price=0, cols=[(250, 210, 30)]),
    'police': dict(n='Police Cruiser', L=50, W=24, vmax=540, acc=420, hp=130, grip=6.0, turn=2.7, price=0, cols=[(40, 60, 120)]),
    'ambulance': dict(n='Ambulance', L=58, W=27, vmax=420, acc=300, hp=150, grip=6.0, turn=2.0, price=0, cols=[(240, 240, 240)]),
    'bike': dict(n='Motorbike', L=30, W=12, vmax=620, acc=520, hp=45, grip=8.0, turn=3.4, price=4000, cols=[(220, 40, 40), (30, 30, 30), (40, 100, 220), (240, 200, 0)]),
    'tank': dict(n='Army Tank', L=66, W=38, vmax=250, acc=180, hp=900, grip=9.0, turn=1.5, price=0, cols=[(80, 100, 60)]),
}
TRAFFIC_TYPES = ['compact', 'compact', 'sedan', 'sedan', 'sedan', 'suv', 'van', 'sport', 'muscle', 'truck', 'bus', 'taxi', 'bike']
RADIO = ['Almaty FM', 'Silk Road Beats', 'Tengri Rock', 'Steppe Talk', 'Radio Off']
CIV_COLS = [(200, 80, 80), (80, 120, 200), (90, 180, 100), (230, 200, 90), (180, 120, 200), (230, 140, 70),
            (120, 120, 130), (60, 60, 70), (240, 240, 240), (150, 100, 70)]
SKIN = [(240, 200, 160), (210, 160, 120), (170, 120, 80), (120, 80, 55)]

# ================================================================ PARTICLES
class Part:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max', 'size', 'col', 'kind', 'grow')

    def __init__(self, kind, x, y, vx, vy, life, size, col, grow=0.0):
        self.kind, self.x, self.y, self.vx, self.vy = kind, x, y, vx, vy
        self.life = self.max = life
        self.size, self.col, self.grow = size, col, grow


def spawn_part(kind, x, y, vx, vy, life, size, col, grow=0.0):
    if len(G.parts) < 450:
        G.parts.append(Part(kind, x, y, vx, vy, life, size, col, grow))


def blood(x, y, n=6):
    for _ in range(n):
        a = rnd(0, 6.283)
        s = rnd(30, 140)
        spawn_part('blood', x, y, math.cos(a) * s, math.sin(a) * s, rnd(0.3, 0.7), rnd(2, 4), (170, 20, 20))
    if len(G.decals) < 160:
        G.decals.append([x + rnd(-6, 6), y + rnd(-6, 6), rnd(3, 7), (120, 15, 15), 40.0])


def sparks(x, y, n=5, col=(255, 220, 120)):
    for _ in range(n):
        a = rnd(0, 6.283)
        s = rnd(60, 220)
        spawn_part('spark', x, y, math.cos(a) * s, math.sin(a) * s, rnd(0.15, 0.4), 2, col)


def smoke(x, y, size=6, col=(70, 70, 75), life=1.0, vy=-30):
    spawn_part('smoke', x + rnd(-3, 3), y + rnd(-3, 3), rnd(-15, 15), vy, life, size, col, 10)


def explosion(x, y, radius=110, dmg=160, owner=None):
    play('boom', 1.0, x, y)
    for _ in range(26):
        a = rnd(0, 6.283)
        s = rnd(40, 300)
        spawn_part('fire', x, y, math.cos(a) * s, math.sin(a) * s, rnd(0.3, 0.8), rnd(8, 18),
                   random.choice([(255, 200, 60), (255, 120, 30), (240, 60, 20)]), -6)
    for _ in range(14):
        smoke(x + rnd(-30, 30), y + rnd(-30, 30), rnd(12, 22), (50, 50, 55), rnd(1.0, 2.2))
    G.shake = max(G.shake, 14 * clamp(1 - dist(x, y, G.cam_c[0], G.cam_c[1]) / 900.0, 0.1, 1))
    G.decals.append([x, y, radius * 0.45, (30, 30, 30), 90.0])
    for p in [G.player] + G.peds:
        if p.hp > 0 and not p.in_car:
            d = dist(x, y, p.x, p.y)
            if d < radius:
                p.hurt(dmg * (1 - d / radius), owner, 'explosion')
                a = ang_to(x, y, p.x, p.y)
                p.kx += math.cos(a) * 300 * (1 - d / radius)
                p.ky += math.sin(a) * 300 * (1 - d / radius)
    for v in G.cars:
        if v.alive:
            d = dist(x, y, v.x, v.y)
            if d < radius + 30:
                v.damage(dmg * 1.6 * (1 - d / (radius + 30)), owner)
                a = ang_to(x, y, v.x, v.y)
                v.vx += math.cos(a) * 260 * (1 - d / (radius + 30))
                v.vy += math.sin(a) * 260 * (1 - d / (radius + 30))
    for pr in G.world.props_near(x, y):
        if pr.alive and dist(x, y, pr.x, pr.y) < radius:
            G.hit_prop(pr, 99)
    G.noise(x, y, 700)
    G.add_wanted_event(x, y, 0.6, owner)


# ================================================================ SPRITES
SPR_CACHE = {}
ROT_CACHE = {}


def car_sprite(vt, col):
    key = (vt, col)
    s = SPR_CACHE.get(key)
    if s:
        return s
    sp = VTYPES[vt]
    L, W = sp['L'], sp['W']
    s = pygame.Surface((L + 8, W + 8), pygame.SRCALPHA)
    ox, oy = 4, 4
    body = pygame.Rect(ox, oy, L, W)
    if vt == 'bike':
        pygame.draw.ellipse(s, (20, 20, 20), (ox, oy + 3, L, W - 6))
        pygame.draw.rect(s, col, (ox + 6, oy + 2, L - 14, W - 4), border_radius=4)
        pygame.draw.rect(s, (30, 30, 35), (ox + L - 8, oy - 1, 3, W + 2))
        pygame.draw.circle(s, (240, 200, 150), (ox + L // 2 - 2, oy + W // 2), 5)
        pygame.draw.circle(s, (60, 60, 200), (ox + L // 2 - 2, oy + W // 2), 4)
        SPR_CACHE[key] = s
        return s
    pygame.draw.rect(s, (20, 20, 22), (ox + 2, oy - 2, L - 4, W + 4), border_radius=5)
    if vt == 'tank':
        pygame.draw.rect(s, (30, 30, 30), (ox, oy, L, 8))
        pygame.draw.rect(s, (30, 30, 30), (ox, oy + W - 8, L, 8))
        pygame.draw.rect(s, col, (ox + 4, oy + 4, L - 10, W - 8), border_radius=6)
        pygame.draw.circle(s, shade(col, 0.8), (ox + L // 2 - 4, oy + W // 2), 11)
        pygame.draw.rect(s, shade(col, 0.6), (ox + L // 2, oy + W // 2 - 2, L // 2 + 4, 4))
        SPR_CACHE[key] = s
        return s
    pygame.draw.rect(s, col, body, border_radius=7)
    pygame.draw.rect(s, shade(col, 0.72), body, 2, border_radius=7)
    cab_x = ox + int(L * 0.28)
    cab_w = int(L * 0.40)
    if vt in ('bus', 'truck', 'van', 'ambulance'):
        if vt == 'truck':
            pygame.draw.rect(s, shade(col, 0.8), (ox + 2, oy + 2, int(L * 0.65), W - 4), border_radius=3)
            cab_x, cab_w = ox + int(L * 0.70), int(L * 0.24)
        elif vt == 'bus':
            for k in range(6):
                pygame.draw.rect(s, (150, 200, 230), (ox + 8 + k * 13, oy + 3, 9, W - 6))
            cab_x, cab_w = ox + L - 14, 8
        else:
            cab_x, cab_w = ox + int(L * 0.60), int(L * 0.28)
    pygame.draw.rect(s, (40, 60, 80), (cab_x, oy + 3, cab_w, W - 6), border_radius=4)
    pygame.draw.rect(s, shade(col, 1.15), (cab_x + 4, oy + 5, max(4, cab_w - 9), W - 10), border_radius=3)
    pygame.draw.rect(s, (255, 250, 200), (ox + L - 3, oy + 2, 3, 5))
    pygame.draw.rect(s, (255, 250, 200), (ox + L - 3, oy + W - 7, 3, 5))
    pygame.draw.rect(s, (200, 20, 20), (ox, oy + 2, 3, 5))
    pygame.draw.rect(s, (200, 20, 20), (ox, oy + W - 7, 3, 5))
    if vt == 'police':
        pygame.draw.rect(s, (240, 240, 240), (ox + 8, oy + 2, int(L * 0.2), W - 4))
        pygame.draw.rect(s, (230, 30, 30), (cab_x + 8, oy + 5, 5, W - 10))
    elif vt == 'taxi':
        pygame.draw.rect(s, (255, 255, 255), (cab_x + 6, oy + W // 2 - 3, 8, 6))
    elif vt == 'ambulance':
        pygame.draw.rect(s, (220, 30, 30), (ox + 10, oy + W // 2 - 2, 14, 4))
        pygame.draw.rect(s, (220, 30, 30), (ox + 15, oy + W // 2 - 7, 4, 14))
    elif vt in ('sport', 'muscle'):
        pygame.draw.rect(s, (245, 245, 245), (ox + 4, oy + W // 2 - 2, L - 8, 4))
    SPR_CACHE[key] = s
    return s


def rotated(img, key, ang):
    deg = int(round(-math.degrees(ang) / 6.0)) % 60
    k = (key, deg)
    r = ROT_CACHE.get(k)
    if r is None:
        if len(ROT_CACHE) > 1500:
            ROT_CACHE.clear()
        r = pygame.transform.rotate(img, deg * 6.0)
        ROT_CACHE[k] = r
    return r


# ================================================================ VEHICLE
class Vehicle:
    def __init__(self, vt, x, y, ang=0.0, color=None, ai='traffic'):
        sp = VTYPES[vt]
        self.vt, self.sp = vt, sp
        self.x, self.y, self.ang = x, y, ang
        self.vx = self.vy = 0.0
        self.color = color or random.choice(sp['cols'])
        self.hp = self.maxhp = float(sp['hp'])
        self.ai = ai
        self.driver = None            # None / 'player' / 'npc'
        self.alive = True
        self.wreck = False
        self.fire = 0.0
        self.gas = self.brake = self.steer = 0.0
        self.hb = False
        self.dir = int(((ang / (math.pi / 2)) % 4) + 0.5) % 4
        self.in_int = False
        self.cruise = rnd(0.5, 0.75) * sp['vmax']
        self.stuck = 0.0
        self.siren = False
        self.t = rnd(0, 10)
        self.owned = False
        self.target = None
        self.hornt = 0.0
        self.last_hit = None
        self.cool = 0.0
        self.age = 0.0
        self.flip = 0.0
        self.sink = 0.0
        self.mission = None
        self.hostile = False
        self.R = max(sp['W'] * 0.55, 9)
        self.yaw_rate = 0.0
        self.wait_t = 0.0
        self.tur = ang

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    def fwd(self):
        return math.cos(self.ang), math.sin(self.ang)

    def circles(self):
        L = self.sp['L']
        c, s = math.cos(self.ang), math.sin(self.ang)
        o = L * 0.26
        if self.vt == 'bike':
            o = 5
        return [(self.x + c * o, self.y + s * o), (self.x - c * o, self.y - s * o)]

    def damage(self, d, owner=None):
        if not self.alive or self.wreck and d < 0:
            return
        if self.vt == 'tank' and owner != 'rocket':
            d *= 0.25
        if owner is not None:
            self.last_hit = owner
        self.hp -= d
        if self.hp < self.maxhp * 0.4 and self.hp > 0:
            if random.random() < d * 0.02:
                smoke(self.x, self.y, 6)
        if self.hp <= 0 and not self.wreck:
            self.wreck = True
            self.fire = rnd(2.2, 3.5)
            G.on_vehicle_wrecked(self)

    def update(self, dt):
        self.age += dt
        self.t += dt
        if self.hornt > 0:
            self.hornt -= dt
        if self.cool > 0:
            self.cool -= dt
        if self.wreck:
            self.gas = self.brake = self.steer = 0.0
            self.hb = False
            if self.fire > 0:
                self.fire -= dt
                smoke(self.x, self.y, rnd(6, 10), (40, 40, 40), 1.2)
                if random.random() < 0.3:
                    spawn_part('fire', self.x + rnd(-8, 8), self.y + rnd(-8, 8), 0, -20, 0.4, 6, (255, 150, 40), -8)
                if self.fire <= 0:
                    self.fire = 0
                    explosion(self.x, self.y, 100, 120, self.last_hit)
                    self.alive = False if self.driver is None else self.alive
                    self.vx += rnd(-80, 80)
                    self.vy += rnd(-80, 80)
        elif self.hp < self.maxhp * 0.25 and chance(dt * 6):
            smoke(self.x, self.y, 5)
        if self.driver is None and self.ai != 'none':
            self.run_ai(dt)
        self.physics(dt)

    def physics(self, dt):
        sp = self.sp
        c, s = math.cos(self.ang), math.sin(self.ang)
        vf = self.vx * c + self.vy * s
        vl = -self.vx * s + self.vy * c
        W = G.world
        terr = W.terrain_at(self.x, self.y)
        mult = 1.0
        if terr in (GRASS, PARK):
            mult = 0.62
        elif terr == SAND:
            mult = 0.5
        elif terr == WATER:
            mult = 0.25
            self.sink += dt
            if self.sink > 2.2 and not self.wreck:
                self.hp = 0
                self.wreck = True
                self.fire = 0.01
                G.on_vehicle_wrecked(self)
        if self.wreck:
            mult = 0.0
        vmax = sp['vmax'] * mult
        acc = sp['acc']
        if self.gas > 0 and vf < vmax:
            vf += acc * self.gas * dt * (1.0 if vf >= 0 else 2.5)
        if self.gas < 0 and vf > -vmax * 0.35:
            vf -= acc * 0.6 * dt
        if self.brake > 0:
            if vf > 4:
                vf -= acc * 1.6 * dt
            elif vf > -vmax * 0.3:
                vf -= acc * 0.5 * dt
        if self.brake > 0 and vf < 0:
            vf = min(vf, 0)
            vf -= acc * 0.5 * dt * self.brake
        vf *= (1.0 - (0.55 if self.gas == 0 and self.brake == 0 else 0.15) * dt)
        if terr in (GRASS, PARK, SAND) and vf > vmax:
            vf *= (1 - 2.0 * dt)
        grip = sp['grip'] * (0.25 if self.hb else 1.0)
        if self.wreck:
            grip = 1.0
        vl *= max(0.0, 1.0 - grip * dt)
        if self.hb and abs(vf) > 20:
            vf *= (1 - 0.9 * dt)
        # steering
        sf = clamp(vf / 140.0, -1.0, 1.0)
        if abs(vf) > 340 and not self.hb:
            sf *= 340.0 / abs(vf) * 1.15
        turn = self.steer * sp['turn'] * sf * (1.4 if self.hb and abs(vf) > 80 else 1.0)
        self.ang += turn * dt
        c, s = math.cos(self.ang), math.sin(self.ang)
        self.vx = c * vf - s * vl
        self.vy = s * vf + c * vl
        self.x += self.vx * dt
        self.y += self.vy * dt
        # collisions with world
        hit = 0.0
        for k, (cx, cy) in enumerate(self.circles()):
            nx, ny, h = W.push_circle(cx, cy, self.R)
            if h > 0:
                self.x += nx - cx
                self.y += ny - cy
                hit = max(hit, h)
        if hit > 0:
            sp_ = self.speed
            if sp_ > 60:
                n = math.hypot(self.vx, self.vy) or 1
                self.vx *= 0.35
                self.vy *= 0.35
                if sp_ > 120:
                    self.damage(sp_ * 0.06, None)
                    sparks(self.x, self.y, 4)
                    if sp_ > 170:
                        play('crash', clamp(sp_ / 400.0, 0.3, 1.0), self.x, self.y)
                        if self.driver == 'player':
                            G.shake = max(G.shake, sp_ / 60.0)
                    for pr in W.props_near(self.x, self.y):
                        if pr.alive and dist(self.x, self.y, pr.x, pr.y) < self.R + pr.r + 6:
                            G.hit_prop(pr, sp_ * 0.2, self.vx * 0.5, self.vy * 0.5)
            self.stuck += dt
        else:
            self.stuck = max(0.0, self.stuck - dt)
        self.x = clamp(self.x, 20, WPX - 20)
        self.y = clamp(self.y, 20, HPX - 20)
        # skid marks and smoke
        if abs(vl) > 90 or (self.hb and abs(vf) > 160):
            if chance(dt * 40) and len(G.skids) < 300:
                G.skids.append([self.x - c * 12 - s * 7, self.y - s * 12 + c * 7, 35.0])
                G.skids.append([self.x - c * 12 + s * 7, self.y - s * 12 - c * 7, 35.0])
            if chance(dt * 10):
                smoke(self.x - c * 14, self.y - s * 14, 5, (180, 180, 180), 0.5, -5)

    # ------------------------------------------------------------ AI
    def sense_ahead(self):
        c, s = math.cos(self.ang), math.sin(self.ang)
        L, Wd = self.sp['L'], self.sp['W']
        look = 34 + self.speed * 0.30
        for v in G.cars:
            if v is self or not v.alive:
                continue
            dx, dy = v.x - self.x, v.y - self.y
            if abs(dx) > 240 or abs(dy) > 240:
                continue
            f = dx * c + dy * s
            l = -dx * s + dy * c
            if 0 < f < (L + v.sp['L']) * 0.5 + look and abs(l) < (Wd + v.sp['W']) * 0.5 + 3:
                return True
        P = G.player
        if not P.in_car:
            dx, dy = P.x - self.x, P.y - self.y
            f, l = dx * c + dy * s, -dx * s + dy * c
            if 0 < f < L * 0.5 + look + 12 and abs(l) < Wd * 0.5 + 12:
                return True
        for p in G.peds:
            if p.dead or p.in_car or abs(p.x - self.x) > 160 or abs(p.y - self.y) > 160:
                continue
            dx, dy = p.x - self.x, p.y - self.y
            f, l = dx * c + dy * s, -dx * s + dy * c
            if 0 < f < L * 0.5 + look + 12 and abs(l) < Wd * 0.5 + 10:
                return True
        return False

    def drive_to(self, tx, ty, speed, dt, careful=False):
        a = ang_to(self.x, self.y, tx, ty)
        W = G.world
        c, s = math.cos(self.ang), math.sin(self.ang)
        pl = 50 + self.speed * 0.25
        left = W.solid_px(self.x + math.cos(self.ang - 0.6) * pl, self.y + math.sin(self.ang - 0.6) * pl)
        right = W.solid_px(self.x + math.cos(self.ang + 0.6) * pl, self.y + math.sin(self.ang + 0.6) * pl)
        ahead = W.solid_px(self.x + c * pl * 1.3, self.y + s * pl * 1.3)
        d = wrap(a - self.ang)
        if ahead or left or right:
            if left and not right:
                d = 0.9
            elif right and not left:
                d = -0.9
            elif ahead:
                d = 1.0 if self.stuck % 2 < 1 else -1.0
        self.steer = clamp(d * 2.2, -1, 1)
        vf = self.vx * c + self.vy * s
        want = speed * (0.45 if abs(d) > 0.9 else (0.75 if abs(d) > 0.45 else 1.0))
        if ahead:
            want *= 0.5
        if self.stuck > 0.8:
            self.gas = -1.0
            self.steer = -self.steer
            self.brake = 0.0
            if self.stuck > 2.0:
                self.stuck = 0.0
            return
        if vf < want:
            self.gas, self.brake = 1.0, 0.0
        elif vf > want + 40:
            self.gas, self.brake = 0.0, 0.7
        else:
            self.gas = self.brake = 0.0

    def run_ai(self, dt):
        ai = self.ai
        W = G.world
        if ai == 'parked':
            self.gas = 0.0
            self.brake = 1.0
            self.hb = True
            return
        if ai == 'traffic':
            self.traffic_ai(dt)
        elif ai == 'police':
            self.police_ai(dt)
        elif ai == 'mission' or ai == 'chase':
            if self.target:
                self.drive_to(self.target[0], self.target[1], self.sp['vmax'] * 0.85, dt)
        elif ai == 'flee':
            a = ang_to(G.player.x, G.player.y, self.x, self.y)
            self.drive_to(self.x + math.cos(a) * 300, self.y + math.sin(a) * 300, self.sp['vmax'] * 0.8, dt)
        elif ai == 'army':
            self.police_ai(dt)

    def traffic_ai(self, dt):
        W = G.world
        tx, ty = int(self.x // TILE), int(self.y // TILE)
        c, r = W.band_c(tx), W.band_r(ty)
        inter = c >= 0 and r >= 0
        if inter and not self.in_int:
            self.in_int = True
            opts = []
            for d, w in ((self.dir, 6), ((self.dir + 1) % 4, 2), ((self.dir + 3) % 4, 2)):
                if (d == 0 and c < COLS) or (d == 1 and r < ROWS) or (d == 2 and c > 0) or (d == 3 and r > 0):
                    opts += [d] * w
            if not opts:
                opts = [(self.dir + 2) % 4]
            self.dir = random.choice(opts)
        elif not inter:
            self.in_int = False
        d = self.dir
        look = 120
        if d == 0:
            tgt = (self.x + look, W.lane_pos(0, self.x, self.y))
        elif d == 2:
            tgt = (self.x - look, W.lane_pos(2, self.x, self.y))
        elif d == 1:
            tgt = (W.lane_pos(1, self.x, self.y), self.y + look)
        else:
            tgt = (W.lane_pos(3, self.x, self.y), self.y - look)
        if not W.is_road(self.x, self.y) and self.age > 3:
            # off road: head to nearest road centre
            tgt = (self.x, self.y)
            p = W.random_road_point((self.x, self.y), 40, 200)
            if p:
                tgt = p
        a = ang_to(self.x, self.y, tgt[0], tgt[1])
        self.steer = clamp(wrap(a - self.ang) * 2.6, -1, 1)
        vf = self.vx * math.cos(self.ang) + self.vy * math.sin(self.ang)
        want = self.cruise * (0.55 if inter else 1.0)
        if self.sense_ahead():
            self.wait_t += dt
            want = 0 if self.wait_t < 3.0 else 70
            if self.wait_t > 7.0:
                self.wait_t = 0.0
        else:
            self.wait_t = 0.0
        if self.stuck > 1.5:
            self.gas, self.brake = -1.0, 0.0
            self.steer = -self.steer
            if self.stuck > 3:
                self.stuck = 0
            return
        if vf < want:
            self.gas, self.brake = 1.0, 0.0
        elif vf > want + 25:
            self.gas, self.brake = 0.0, 1.0 if want == 0 else 0.5
        else:
            self.gas = self.brake = 0.0
        if self.hostile is False and self.hp < self.maxhp * 0.7 and self.last_hit == 'player' and self.age > 1:
            self.ai = 'flee'

    def police_ai(self, dt):
        P = G.player
        tx, ty = P.pos()
        d = dist(self.x, self.y, tx, ty)
        if G.wanted <= 0 and self.ai == 'police':
            self.ai = 'traffic'
            self.siren = False
            self.cruise = rnd(0.5, 0.65) * self.sp['vmax']
            return
        self.siren = True
        self.drive_to(tx, ty, self.sp['vmax'] * (0.95 if G.wanted >= 3 else 0.8), dt)
        if d < 70 and self.speed > 30:
            self.brake = 0.3
        if self.vt == 'tank':
            self.tur = lerp(self.tur, ang_to(self.x, self.y, tx, ty), 0.1)
            if d < 700 and self.cool <= 0 and G.world.line_clear(self.x, self.y, tx, ty, 24):
                self.cool = 2.2
                G.fire_bullet(self.x, self.y, self.tur, 'rpg', self, 'army')
        elif d < 380 and self.cool <= 0 and G.wanted >= 4 and self.vt == 'police' and chance(dt * 0.3):
            self.cool = 3.0
            for k in range(3):
                G.queue_shot(0.12 * k, self.x, self.y, ang_to(self.x, self.y, tx, ty) + rnd(-0.1, 0.1), 'smg', self, 'police')

    # ------------------------------------------------------------ DRAW
    def draw(self):
        px, py = self.x - CAM[0], self.y - CAM[1]
        if px < -120 or px > LW + 120 or py < -120 or py > LH + 120:
            return
        col = self.color
        if self.wreck:
            col = (40, 40, 44)
        img = car_sprite(self.vt, col)
        # shadow
        r = rotated(img, (self.vt, col), self.ang)
        CV.blit(r, (px - r.get_width() // 2, py - r.get_height() // 2))
        if self.vt == 'tank' and not self.wreck:
            tx, ty = math.cos(self.tur), math.sin(self.tur)
            pygame.draw.line(CV, (60, 75, 45), (px, py), (px + tx * 44, py + ty * 44), 5)
            pygame.draw.circle(CV, (95, 115, 70), (int(px), int(py)), 11)
        if self.driver is not None and self.vt == 'bike':
            pass
        if self.siren and not self.wreck:
            ph = int(self.t * 8) % 2
            cc = (255, 40, 40) if ph else (40, 80, 255)
            sx, sy = -math.sin(self.ang) * 5, math.cos(self.ang) * 5
            pygame.draw.circle(CV, cc, (int(px + sx), int(py + sy)), 4)
            pygame.draw.circle(CV, (255, 40, 40) if not ph else (40, 80, 255), (int(px - sx), int(py - sy)), 4)
        if self.fire > 0:
            pygame.draw.circle(CV, (255, 150, 30), (int(px), int(py)), int(8 + 5 * math.sin(self.t * 20)))


# ================================================================ PEDS
class Ped:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.x, self.y = x, y
        self.ang = rnd(0, 6.283)
        self.hp = self.maxhp = {'civ': 40, 'gang': 70, 'cop': 80, 'swat': 140, 'soldier': 200, 'player': 100,
                                'medic': 40, 'boss': 220}.get(kind, 40)
        self.armor = 0.0
        self.weapon = 'fist'
        self.cool = rnd(0, 1)
        self.in_car = None
        self.kx = self.ky = 0.0
        self.phase = rnd(0, 6)
        self.skin = random.choice(SKIN)
        self.color = random.choice(CIV_COLS)
        if kind == 'cop':
            self.color, self.weapon = (40, 60, 120), 'pistol'
        elif kind == 'swat':
            self.color, self.weapon = (30, 30, 35), 'rifle'
        elif kind == 'soldier':
            self.color, self.weapon = (70, 90, 55), 'rifle'
        elif kind in ('gang', 'boss'):
            self.color = random.choice([(120, 30, 150), (30, 110, 40), (160, 30, 30)]) if kind == 'gang' else (20, 20, 20)
            self.weapon = random.choice(['bat', 'pistol', 'pistol', 'smg']) if kind == 'gang' else 'smg'
        elif kind == 'medic':
            self.color = (240, 240, 240)
        self.state = 'wander'
        self.tx = self.ty = None
        self.timer = rnd(1, 5)
        self.fear = 0.0
        self.threat = None
        self.hostile = False
        self.dead = False
        self.dead_t = 0.0
        self.speed = rnd(48, 70)
        self.team = {'cop': 'police', 'swat': 'police', 'soldier': 'army', 'gang': 'gang', 'boss': 'gang',
                     'player': 'player'}.get(kind, 'civ')
        self.mission = None
        self.last_hit = None
        self.cash = random.randint(5, 60) if kind in ('civ', 'gang') else 0
        self.hurt_t = 0.0
        self.R = 8
        self.mv = True

    def pos(self):
        if self.in_car:
            return self.in_car.x, self.in_car.y
        return self.x, self.y

    def hurt(self, d, owner=None, how='bullet'):
        if self.dead:
            return
        if owner is not None:
            self.last_hit = owner
        if self.armor > 0 and how != 'fall':
            a = min(self.armor, d * 0.7)
            self.armor -= a
            d -= a
        self.hp -= d
        self.hurt_t = 0.15
        if how != 'explosion':
            blood(self.x, self.y, 3)
        if self.kind != 'player':
            self.fear = 6.0
            if owner == 'player' or owner is G.player:
                self.threat = (G.player.x, G.player.y)
                if self.kind in ('gang', 'boss', 'cop', 'swat', 'soldier'):
                    self.hostile = True
        if self.hp <= 0:
            self.die(owner, how)

    def die(self, owner, how):
        self.dead = True
        self.hp = 0
        self.dead_t = 0.0
        if self.in_car:
            v = self.in_car
            self.in_car = None
            if v.driver == 'player':
                v.driver = None
        G.on_ped_killed(self, owner, how)

    def move(self, dx, dy, dt):
        if self.in_car:
            return
        self.mv = abs(dx) + abs(dy) > 5
        self.x += (dx + self.kx) * dt
        self.y += (dy + self.ky) * dt
        self.kx *= max(0.0, 1 - 8 * dt)
        self.ky *= max(0.0, 1 - 8 * dt)
        nx, ny, h = G.world.push_circle(self.x, self.y, self.R)
        self.x, self.y = nx, ny
        if G.world.terrain_at(self.x, self.y) == WATER:
            self.hurt(25 * dt, None, 'fall')

    def can_see(self, x, y, rng=420):
        return dist(self.x, self.y, x, y) < rng and G.world.line_clear(self.x, self.y, x, y, 20)

    def melee_or_shoot(self, tx, ty, dt, team):
        w = WEAPONS[self.weapon]
        a = ang_to(self.x, self.y, tx, ty)
        self.ang = lerp_ang(self.ang, a, 0.25)
        d = dist(self.x, self.y, tx, ty)
        if self.cool > 0:
            return
        if w.get('melee'):
            if d < w['rng'] + 8:
                self.cool = w['rate'] + 0.2
                G.melee_hit(self, a, w, team)
        elif d < w['rng'] * 0.9 and G.world.line_clear(self.x, self.y, tx, ty, 20):
            self.cool = w['rate'] * rnd(2.0, 3.2) + (0.2 if self.kind == 'cop' else 0.0)
            G.fire_bullet(self.x, self.y, a + rnd(-0.12, 0.12), self.weapon, self, team)

    def update(self, dt):
        if self.dead:
            self.dead_t += dt
            return
        if self.cool > 0:
            self.cool -= dt
        if self.hurt_t > 0:
            self.hurt_t -= dt
        if self.fear > 0:
            self.fear -= dt
        if self.in_car:
            self.x, self.y = self.in_car.x, self.in_car.y
            return
        P = G.player
        px, py = P.pos()
        d = dist(self.x, self.y, px, py)
        k = self.kind
        self.phase += dt * 9
        if k in ('cop', 'swat', 'soldier'):
            self.law_ai(dt, px, py, d)
        elif k in ('gang', 'boss'):
            self.gang_ai(dt, px, py, d)
        elif k == 'medic':
            self.wander(dt, 60)
        else:
            self.civ_ai(dt, px, py, d)

    def wander(self, dt, spd):
        self.timer -= dt
        if self.tx is None or self.timer <= 0 or dist(self.x, self.y, self.tx, self.ty) < 12:
            self.timer = rnd(3, 9)
            a = rnd(0, 6.283)
            dd = rnd(60, 220)
            nx, ny = self.x + math.cos(a) * dd, self.y + math.sin(a) * dd
            t = G.world.terrain_at(nx, ny)
            if t in (SIDE, GRASS, PARK, PLAZA, LOT, SAND, DOCK):
                self.tx, self.ty = nx, ny
            else:
                self.tx = None
                self.timer = 0.3
                return
        a = ang_to(self.x, self.y, self.tx, self.ty)
        self.ang = lerp_ang(self.ang, a, 0.15)
        # avoid roads with traffic: stop if car close
        self.move(math.cos(self.ang) * spd, math.sin(self.ang) * spd, dt)

    def civ_ai(self, dt, px, py, d):
        # panic
        danger = self.fear > 0
        if not danger:
            for v in G.cars_near(self.x, self.y, 130):
                if v.speed > 160 and dist(self.x, self.y, v.x, v.y) < 90:
                    danger = True
                    self.threat = (v.x, v.y)
                    self.fear = 1.5
                    break
        if danger and self.threat:
            a = ang_to(self.threat[0], self.threat[1], self.x, self.y)
            self.ang = lerp_ang(self.ang, a + math.sin(self.phase * 0.1) * 0.3, 0.2)
            self.move(math.cos(self.ang) * 135, math.sin(self.ang) * 135, dt)
        else:
            self.wander(dt, self.speed)
        if self.mission == 'ambient_fight' and d < 200:
            pass

    def gang_ai(self, dt, px, py, d):
        if G.player_has_gun_out() and d < 240 and chance(dt * 0.4):
            self.hostile = True
        if self.hostile and d < 520 and self.can_see(px, py, 520):
            w = WEAPONS[self.weapon]
            keep = 28 if w.get('melee') else 220
            a = ang_to(self.x, self.y, px, py)
            if d > keep:
                self.ang = lerp_ang(self.ang, a, 0.2)
                self.move(math.cos(self.ang) * 115, math.sin(self.ang) * 115, dt)
            self.melee_or_shoot(px, py, dt, 'gang')
        elif self.hostile and d < 900:
            a = ang_to(self.x, self.y, px, py)
            self.ang = lerp_ang(self.ang, a, 0.15)
            self.move(math.cos(self.ang) * 110, math.sin(self.ang) * 110, dt)
        else:
            if d > 1000:
                self.hostile = False
            self.wander(dt, 45)

    def law_ai(self, dt, px, py, d):
        if G.wanted > 0 or self.hostile:
            if d < 1100:
                a = ang_to(self.x, self.y, px, py)
                keep = 160 if self.kind != 'cop' else 120
                if d > keep or not self.can_see(px, py, 450):
                    # head toward player, slide along walls
                    self.ang = lerp_ang(self.ang, a, 0.2)
                    self.move(math.cos(self.ang) * 128, math.sin(self.ang) * 128, dt)
                else:
                    self.ang = lerp_ang(self.ang, a, 0.3)
                if self.can_see(px, py, 450):
                    self.melee_or_shoot(px, py, dt, 'police' if self.kind != 'soldier' else 'army')
        else:
            self.wander(dt, 42)

    def draw(self):
        px, py = int(self.x - CAM[0]), int(self.y - CAM[1])
        if px < -30 or px > LW + 30 or py < -30 or py > LH + 30:
            return
        if self.dead:
            s = max(0.0, 1.0 - self.dead_t / 18.0)
            c = shade(self.color, 0.6 * (0.5 + s * 0.5))
            pygame.draw.ellipse(CV, (110, 15, 15), (px - 11, py - 7, 22, 14))
            pygame.draw.ellipse(CV, c, (px - 8, py - 5, 16, 10))
            pygame.draw.circle(CV, self.skin, (px + int(math.cos(self.ang) * 8), py + int(math.sin(self.ang) * 8)), 4)
            return
        if self.in_car:
            return
        ca, sa = math.cos(self.ang), math.sin(self.ang)
        pygame.draw.ellipse(CV, (0, 0, 0), (px - 8, py - 3, 16, 10)) if False else None
        sw = math.sin(self.phase) * 4 if (abs(self.kx) + 1) > 0 and self.moving() else 0
        # legs
        pygame.draw.circle(CV, shade(self.color, 0.5), (int(px - sa * 3 + ca * sw), int(py + ca * 3 + sa * sw)), 3)
        pygame.draw.circle(CV, shade(self.color, 0.5), (int(px + sa * 3 - ca * sw), int(py - ca * 3 - sa * sw)), 3)
        body = self.color if self.hurt_t <= 0 else (255, 255, 255)
        pygame.draw.circle(CV, shade(body, 0.7), (px, py), 8)
        pygame.draw.circle(CV, body, (px, py), 7)
        # arms / weapon
        w = WEAPONS[self.weapon]
        hx, hy = px + ca * 9, py + sa * 9
        pygame.draw.circle(CV, self.skin, (int(hx), int(hy)), 3)
        if self.weapon != 'fist':
            ln = {'bat': 16, 'pistol': 10, 'smg': 13, 'shotgun': 17, 'rifle': 18, 'rpg': 20, 'grenade': 5}.get(self.weapon, 10)
            pygame.draw.line(CV, w['col'], (hx, hy), (hx + ca * ln, hy + sa * ln), 3)
        pygame.draw.circle(CV, self.skin, (int(px + ca * 1), int(py + sa * 1)), 4)
        if self.kind in ('cop', 'swat'):
            pygame.draw.circle(CV, (20, 20, 30), (int(px + ca * 1), int(py + sa * 1)), 4, 2)
        if self.mission == 'target':
            pygame.draw.polygon(CV, (255, 60, 60), [(px, py - 22), (px - 5, py - 30), (px + 5, py - 30)])

    def moving(self):
        return self.mv


def lerp_ang(a, b, t):
    return a + wrap(b - a) * t


# ================================================================ BULLETS, PICKUPS, HELI
class Bullet:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'dmg', 'team', 'owner', 'kind', 'rad', 'fuse', 'px', 'py', 'wid')

    def __init__(self, x, y, ang, wid, owner, team):
        w = WEAPONS[wid]
        self.wid = wid
        self.x, self.y = x, y
        spd = w.get('spd', 900)
        self.vx, self.vy = math.cos(ang) * spd, math.sin(ang) * spd
        self.life = w.get('rng', 500) / float(spd)
        self.dmg = w.get('dmg', 10)
        self.team, self.owner = team, owner
        self.kind = 'rocket' if w.get('rocket') else ('grenade' if w.get('gren') else 'bullet')
        self.fuse = 1.7
        self.rad = 110
        self.px, self.py = x, y
        if self.kind == 'grenade':
            self.life = 3.0

    def update(self, dt):
        """returns False when dead"""
        self.px, self.py = self.x, self.y
        W = G.world
        steps = 2 if self.kind == 'bullet' else 1
        for _ in range(steps):
            self.x += self.vx * dt / steps
            self.y += self.vy * dt / steps
            if self.kind == 'grenade':
                continue
            if W.solid_px(self.x, self.y):
                self.impact(None)
                return False
            if self.collide():
                return False
        self.life -= dt
        if self.kind == 'grenade':
            nx = self.x
            if W.solid_px(self.x, self.py):
                self.vx *= -0.5
                self.x = self.px
            if W.solid_px(self.x, self.y):
                self.vy *= -0.5
                self.y = self.py
            self.vx *= (1 - 2.2 * dt)
            self.vy *= (1 - 2.2 * dt)
            self.fuse -= dt
            if self.fuse <= 0:
                explosion(self.x, self.y, 120, 150, self.owner)
                return False
            return True
        if self.kind == 'rocket':
            spawn_part('smoke', self.x, self.y, rnd(-10, 10), rnd(-10, 10), 0.6, 4, (200, 200, 200), 8)
            spawn_part('fire', self.x, self.y, 0, 0, 0.2, 4, (255, 180, 60), -4)
        if self.life <= 0:
            if self.kind == 'rocket':
                explosion(self.x, self.y, 110, self.dmg, self.owner)
            return False
        return True

    def impact(self, what):
        if self.kind == 'rocket':
            explosion(self.x, self.y, 110, self.dmg, self.owner)
        else:
            sparks(self.x, self.y, 3)

    def collide(self):
        for pr in G.world.props_near(self.x, self.y):
            if pr.alive and dist(self.x, self.y, pr.x, pr.y) < pr.r:
                G.hit_prop(pr, self.dmg * 0.3, self.vx * 0.05, self.vy * 0.05)
                self.impact(pr)
                return True
        if self.team != 'player' or True:
            cand = [G.player] + G.peds if self.team != 'player' else G.peds
            for p in cand:
                if p.dead or p.in_car or p is self.owner:
                    continue
                if abs(p.x - self.x) < 14 and abs(p.y - self.y) < 14 and dist(p.x, p.y, self.x, self.y) < 10:
                    if p.team == self.team and p is not G.player:
                        continue
                    if self.kind == 'rocket':
                        self.impact(p)
                    else:
                        p.hurt(self.dmg, self.owner, 'bullet')
                        if p is not G.player:
                            G.noise(p.x, p.y, 250)
                        play('hit', 0.6, p.x, p.y)
                    return True
        for v in G.cars:
            if not v.alive or abs(v.x - self.x) > 60 or abs(v.y - self.y) > 60:
                continue
            if v.driver == 'player' and self.team == 'player':
                continue
            for (cx, cy) in v.circles():
                if dist(cx, cy, self.x, self.y) < v.R + 2:
                    if self.kind == 'rocket':
                        self.impact(v)
                    else:
                        v.damage(self.dmg * 0.5, self.owner if self.team == 'player' else None)
                        sparks(self.x, self.y, 3)
                        if v.driver == 'player' and self.team != 'player':
                            G.player_car_shot(self.dmg * 0.25)
                    return True
        return False

    def draw(self):
        px, py = self.x - CAM[0], self.y - CAM[1]
        if self.kind == 'bullet':
            n = math.hypot(self.vx, self.vy)
            pygame.draw.line(CV, (255, 240, 150), (px, py), (px - self.vx / n * 14, py - self.vy / n * 14), 2)
        elif self.kind == 'rocket':
            pygame.draw.circle(CV, (230, 230, 230), (int(px), int(py)), 4)
        else:
            pygame.draw.circle(CV, (40, 90, 40), (int(px), int(py)), 5)
            if int(self.fuse * 8) % 2:
                pygame.draw.circle(CV, (255, 60, 60), (int(px), int(py)), 2)


class Pickup:
    def __init__(self, kind, x, y, val=0, wid=None):
        self.kind, self.x, self.y, self.val, self.wid = kind, x, y, val, wid
        self.t = rnd(0, 6)
        self.life = 60.0 if kind in ('cash', 'weapon_drop') else 1e9
        self.alive = True

    def update(self, dt):
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self):
        px, py = int(self.x - CAM[0]), int(self.y - CAM[1] + math.sin(self.t * 3) * 3)
        if px < -20 or px > LW + 20 or py < -20 or py > LH + 20:
            return
        k = self.kind
        pygame.draw.circle(CV, (0, 0, 0), (px, py + 8), 6)
        if k == 'health':
            pygame.draw.circle(CV, (255, 255, 255), (px, py), 10)
            CV.fill((220, 30, 30), (px - 6, py - 2, 12, 4))
            CV.fill((220, 30, 30), (px - 2, py - 6, 4, 12))
        elif k == 'armor':
            pygame.draw.circle(CV, (70, 130, 230), (px, py), 10)
            pygame.draw.polygon(CV, WHITE, [(px - 5, py - 5), (px + 5, py - 5), (px + 4, py + 2), (px, py + 7), (px - 4, py + 2)])
        elif k == 'cash':
            pygame.draw.circle(CV, (60, 170, 70), (px, py), 8)
            draw_text('$', px, py, 18, WHITE, 'mc', False)
        elif k in ('weapon', 'weapon_drop'):
            pygame.draw.circle(CV, (230, 120, 40), (px, py), 11)
            pygame.draw.line(CV, WHITE, (px - 6, py), (px + 6, py), 4)
            pygame.draw.line(CV, WHITE, (px + 2, py - 3), (px + 2, py + 3), 3)
        elif k == 'package':
            pygame.draw.rect(CV, (200, 90, 220), (px - 7, py - 7, 14, 14), border_radius=3)
            draw_text('?', px, py, 16, WHITE, 'mc', False)
        elif k == 'sprunk':
            pygame.draw.circle(CV, (250, 220, 40), (px, py), 9)
            draw_text('*', px, py + 2, 22, (30, 30, 30), 'mc', False)


class Heli:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = 260.0
        self.ang = 0.0
        self.vx = self.vy = 0.0
        self.rot = 0.0
        self.cool = 2.0
        self.alive = True
        self.team = 'police'

    def update(self, dt):
        P = G.player
        tx, ty = P.pos()
        a = ang_to(self.x, self.y, tx, ty)
        d = dist(self.x, self.y, tx, ty)
        want = 230.0
        sp = 190 if d > want else (-60 if d < want * 0.6 else 0)
        self.vx = lerp(self.vx, math.cos(a) * sp + math.cos(a + 1.57) * 70, dt * 2)
        self.vy = lerp(self.vy, math.sin(a) * sp + math.sin(a + 1.57) * 70, dt * 2)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.ang = lerp_ang(self.ang, a, 0.08)
        self.rot += dt * 30
        self.cool -= dt
        if G.wanted < 4 and d > 1400:
            self.alive = False
        if self.cool <= 0 and d < 520:
            self.cool = 1.6
            for k in range(4):
                G.queue_shot(0.1 * k, self.x, self.y, a + rnd(-0.12, 0.12), 'smg', self, 'police')
        if self.hp <= 0:
            self.alive = False
            explosion(self.x, self.y, 120, 120, None)
            G.add_cash_pop(self.x, self.y, 500)
            G.stats['helis'] = G.stats.get('helis', 0) + 1

    def draw(self):
        px, py = self.x - CAM[0], self.y - CAM[1]
        if px < -80 or px > LW + 80 or py < -80 or py > LH + 80:
            return
        pygame.draw.ellipse(CV, (20, 20, 20), (px - 16 + 18, py - 8 + 26, 36, 16))
        c, s = math.cos(self.ang), math.sin(self.ang)
        pygame.draw.line(CV, (40, 50, 100), (px - c * 12, py - s * 12), (px - c * 36, py - s * 36), 4)
        pygame.draw.ellipse(CV, (50, 70, 140), (px - 20, py - 13, 40, 26))
        pygame.draw.circle(CV, (140, 190, 230), (int(px + c * 10), int(py + s * 10)), 8)
        for k in range(2):
            a = self.rot + k * 1.57
            pygame.draw.line(CV, (210, 210, 210), (px - math.cos(a) * 46, py - math.sin(a) * 46),
                             (px + math.cos(a) * 46, py + math.sin(a) * 46), 2)
        pygame.draw.circle(CV, (230, 40, 40) if int(pygame.time.get_ticks() / 150) % 2 else (40, 80, 255), (int(px), int(py)), 4)


# ================================================================ GAME CORE
class Game:
    def __init__(self, screen):
        global G
        G = self
        self.screen = screen
        self.ctl = Controls()
        self.state = 'menu'
        self.prev_state = 'play'
        self.world = None
        self.cam_c = [0.0, 0.0]
        self.shake = 0.0
        self.menu_sel = 0
        self.menu_scroll = 0.0
        self.settings = {'vol': 0.8, 'lang': 'en', 'shake': True, 'fps': True, 'hud': 1.0}
        self.has_save = os.path.exists(SAVE_PATH)
        self.fps = 60.0
        self.msgs = []
        self.texts = []
        self.reset_vars()
        self.shop = None
        self.map_zoom = 0
        self.phone_tab = 0

    def reset_vars(self):
        self.peds, self.cars, self.bullets, self.parts, self.pickups, self.helis = [], [], [], [], [], []
        self.decals, self.skids, self.shots = [], [], []
        self.player = None
        self.money = 500
        self.wanted = 0.0
        self.hidden_t = 0.0
        self.seen = False
        self.weapons = {'fist': 0, 'bat': 0}
        self.stamina = 100.0
        self.clock = 9 * 60.0
        self.rain = 0.0
        self.rain_t = rnd(120, 400)
        self.stats = {'kills': 0, 'cars': 0, 'wasted': 0, 'busted': 0, 'packages': 0, 'time': 0.0, 'dist': 0.0,
                      'missions': 0, 'cops': 0, 'spent': 0, 'earned': 0, 'jumps': 0}
        self.done_missions = 0
        self.mission = None
        self.side = None
        self.pkg_found = set()
        self.home_car = None
        self.dealer_cars = []
        self.spawn_t = 0.0
        self.law_t = 0.0
        self.busted_t = 0.0
        self.death_t = 0.0
        self.death_kind = ''
        self.radio = 0
        self.last_dist = None
        self.district = ''
        self.dist_t = 0.0
        self.pending = []
        self.owned_cars = []
        self.hp_flash = 0.0
        self.cheat_god = False
        self.heat = 0.0
        self.banner = None
        self.dt = 0.016
        self.rain_target = 0.0

    # ------------------------------------------------------------ new / save / load
    def new_game(self, load=None):
        global LANG
        self.reset_vars()
        self.world = W = World(7)
        sx, sy = W.garages[-1][1], W.garages[-1][2]
        for g in W.garages:
            if g[0] == 'home':
                sx, sy = g[1], g[2]
        pl = Ped('player', sx - 60, sy + 10)
        pl.weapon = 'fist'
        self.player = pl
        self.weapons = {'fist': 0, 'bat': 0}
        # hidden packages, pickups
        for k in range(24):
            p = W.random_walk_point()
            if p:
                self.pickups.append(Pickup('package', p[0], p[1], k))
        for (px, py) in W.parks:
            self.pickups.append(Pickup('health', (px + 4) * TILE, (py + 4) * TILE))
        for k in range(8):
            p = W.random_walk_point()
            if p:
                self.pickups.append(Pickup('armor', p[0], p[1], 50))
        for k in range(8):
            p = W.random_walk_point()
            if p:
                self.pickups.append(Pickup('weapon', p[0], p[1], 0, random.choice(['pistol', 'smg', 'shotgun', 'rifle', 'grenade'])))
        # parked cars near start
        h = W.random_road_point((sx, sy), 80, 260)
        if h:
            v = Vehicle('compact', h[0], h[1], 0.0, (200, 60, 60), 'parked')
            self.cars.append(v)
        self.populate(initial=True)
        if load:
            self.apply_save(load)
        self.update_cam(1.0, snap=True)
        self.state = 'play'
        self.say(T("Welcome to Almaty City!"), 3)
        if not load:
            self.say(T("Press the phone icon for missions & menu"), 4)

    def save_game(self):
        try:
            d = {'money': self.money, 'weapons': self.weapons, 'done': self.done_missions, 'clock': self.clock,
                 'stats': self.stats, 'pkg': sorted(self.pkg_found), 'x': self.player.x, 'y': self.player.y,
                 'hp': self.player.hp, 'armor': self.player.armor, 'settings': self.settings,
                 'owned': self.owned_cars}
            with open(SAVE_PATH, 'w') as f:
                json.dump(d, f)
            self.has_save = True
            return True
        except Exception:
            return False

    def load_data(self):
        try:
            with open(SAVE_PATH) as f:
                return json.load(f)
        except Exception:
            return None

    def apply_save(self, d):
        self.money = d.get('money', 500)
        self.weapons = d.get('weapons', self.weapons)
        self.done_missions = d.get('done', 0)
        self.clock = d.get('clock', self.clock)
        self.stats.update(d.get('stats', {}))
        self.pkg_found = set(d.get('pkg', []))
        self.owned_cars = d.get('owned', [])
        self.player.hp = d.get('hp', 100)
        self.player.armor = d.get('armor', 0)
        for p in list(self.pickups):
            if p.kind == 'package' and p.val in self.pkg_found:
                self.pickups.remove(p)
        self.respawn_home_cars()

    def respawn_home_cars(self):
        W = self.world
        for g in W.garages:
            if g[0] == 'home':
                for k, vt in enumerate(self.owned_cars[:3]):
                    if vt in VTYPES:
                        v = Vehicle(vt, g[1] + 60 * k, g[2] + 30, 0.0, None, 'parked')
                        v.owned = True
                        self.cars.append(v)
                break

    # ------------------------------------------------------------ messages
    def say(self, text, t=3.0):
        self.msgs.append([text, t])
        if len(self.msgs) > 4:
            self.msgs.pop(0)

    def float_text(self, text, x, y, col=WHITE, life=1.2):
        self.texts.append([text, x, y, life, col])

    def add_cash_pop(self, x, y, amt):
        self.give_money(amt)
        self.float_text('+$%d' % amt, x, y - 10, (120, 255, 120))

    def give_money(self, a):
        self.money += a
        if a > 0:
            self.stats['earned'] += a
            play('cash', 0.6)
        else:
            self.stats['spent'] -= a

    # ------------------------------------------------------------ hooks
    def cars_near(self, x, y, r):
        return [v for v in self.cars if v.alive and abs(v.x - x) < r and abs(v.y - y) < r]

    def player_has_gun_out(self):
        return self.player.weapon not in ('fist', 'bat') and self.ctl.fire

    def noise(self, x, y, r):
        for p in self.peds:
            if p.kind == 'civ' and not p.dead and not p.in_car and abs(p.x - x) < r and abs(p.y - y) < r:
                if dist(p.x, p.y, x, y) < r:
                    p.fear = max(p.fear, rnd(3, 6))
                    p.threat = (x, y)

    def hit_prop(self, pr, dmg, vx=0, vy=0):
        pr.hp -= dmg
        if pr.hp <= 0 and pr.alive:
            pr.alive = False
            sparks(pr.x, pr.y, 6, (200, 200, 200))
            if pr.kind == 'hydrant':
                for k in range(12):
                    spawn_part('smoke', pr.x, pr.y, rnd(-25, 25), rnd(-80, -30), 0.8, 4, (150, 200, 255), 4)
            elif pr.kind == 'crate' and chance(0.5):
                self.pickups.append(Pickup('cash', pr.x, pr.y, random.randint(20, 120)))
            elif pr.kind == 'bin' and chance(0.4):
                self.pickups.append(Pickup('cash', pr.x, pr.y, random.randint(5, 40)))

    def add_wanted_event(self, x, y, amt, owner):
        if owner is not self.player and owner != 'player':
            return
        witness = False
        for p in self.peds:
            if p.kind in ('cop', 'swat', 'soldier') and not p.dead and dist(p.x, p.y, x, y) < 520:
                witness = True
                break
        if not witness:
            for v in self.cars:
                if v.alive and v.vt == 'police' and dist(v.x, v.y, x, y) < 600:
                    witness = True
                    break
        if witness or self.wanted > 0:
            self.add_heat(amt)
        elif amt >= 0.3:
            self.add_heat(amt * 0.5)

    def add_heat(self, amt):
        self.heat = getattr(self, 'heat', 0.0) + amt
        self.hidden_t = 0.0

    def stars(self):
        h = getattr(self, 'heat', 0.0)
        if h < 0.5:
            return 0
        for i, t in enumerate([0.5, 1.6, 3.2, 5.5, 8.5, 13.0]):
            if h < t:
                return i
        return 6

    def clear_wanted(self):
        self.heat = 0.0
        self.wanted = 0
        for v in self.cars:
            if v.ai in ('police', 'army'):
                v.ai = 'traffic'
                v.siren = False
        for p in self.peds:
            p.hostile = False if p.kind in ('cop', 'swat', 'soldier') else p.hostile

    def on_ped_killed(self, p, owner, how):
        mine = owner is self.player or owner == 'player'
        if p is self.player:
            self.on_player_dead(how)
            return
        if mine:
            self.stats['kills'] += 1
            if p.kind == 'civ':
                self.add_wanted_event(p.x, p.y, 0.5, owner)
            elif p.kind == 'cop':
                self.add_wanted_event(p.x, p.y, 1.8, owner)
                self.stats['cops'] += 1
            elif p.kind in ('swat', 'soldier'):
                self.add_wanted_event(p.x, p.y, 2.5, owner)
                self.stats['cops'] += 1
        if p.cash and p.kind != 'player':
            self.pickups.append(Pickup('cash', p.x, p.y, p.cash))
        if p.kind in ('cop', 'swat') and chance(0.4):
            self.pickups.append(Pickup('weapon_drop', p.x + 6, p.y, 0, p.weapon))
        if self.mission:
            self.mission.on_kill(p)
        self.noise(p.x, p.y, 300)

    def on_vehicle_wrecked(self, v):
        if v.last_hit in ('player', self.player):
            self.stats['cars'] += 1
            if v.vt in ('police', 'tank'):
                self.add_heat(1.2)
            if self.mission:
                self.mission.on_car_destroyed(v)

    def player_car_shot(self, d):
        self.hp_flash = 0.2
        pl = self.player
        if pl.in_car and not self.cheat_god:
            pl.hurt(d * 0.5, None, 'bullet')

    # ------------------------------------------------------------ shooting
    def queue_shot(self, delay, x, y, ang, wid, owner, team):
        self.shots.append([delay, x, y, ang, wid, owner, team])

    def fire_bullet(self, x, y, ang, wid, owner, team):
        w = WEAPONS[wid]
        if owner is not None and hasattr(owner, 'x') and not hasattr(owner, 'kind') is False:
            pass
        ox, oy = x + math.cos(ang) * 16, y + math.sin(ang) * 16
        for k in range(w.get('pel', 1)):
            a = ang + rnd(-1, 1) * w.get('spread', 0)
            b = Bullet(ox, oy, a, wid, owner, team)
            if b.kind == 'grenade':
                b.vx += getattr(owner, 'vx', 0.0) * 0.3
            self.bullets.append(b)
        if w.get('snd'):
            play(w['snd'], 0.8, x, y)
        if not w.get('gren'):
            spawn_part('fire', ox, oy, math.cos(ang) * 40, math.sin(ang) * 40, 0.06, 5, (255, 230, 120), 0)
        if team == 'player':
            self.noise(x, y, 520)
            self.add_wanted_event(x, y, 0.05 if not w.get('rocket') else 0.4, 'player')

    def melee_hit(self, att, ang, w, team):
        hit = False
        targets = list(self.peds)
        if att is not self.player:
            targets.append(self.player)
        for p in targets:
            if p is att or p.dead or p.in_car:
                continue
            if team == 'police' and p.kind in ('cop', 'swat'):
                continue
            if p.team == team and p is not self.player:
                continue
            d = dist(att.x, att.y, p.x, p.y)
            if d < w['rng'] + 10 and abs(wrap(ang_to(att.x, att.y, p.x, p.y) - ang)) < 1.0:
                dmg = w['dmg'] * (1.0 if att is not self.player else 1.0)
                p.hurt(dmg, att, 'melee')
                a = ang_to(att.x, att.y, p.x, p.y)
                p.kx += math.cos(a) * 220
                p.ky += math.sin(a) * 220
                hit = True
                if att is self.player and p.kind in ('cop', 'swat'):
                    self.add_wanted_event(p.x, p.y, 0.6, 'player')
                elif att is self.player and p.kind == 'civ':
                    self.add_wanted_event(p.x, p.y, 0.12, 'player')
        play('punch' if hit else 'click', 0.7, att.x, att.y)
        if hit:
            self.noise(att.x, att.y, 220)

    # ------------------------------------------------------------ spawning
    def make_traffic_car(self, x, y):
        W = self.world
        tx, ty = int(x // TILE), int(y // TILE)
        c, r = W.band_c(tx), W.band_r(ty)
        if c >= 0 and r >= 0:
            return None
        if r >= 0:
            d = random.choice([0, 2])
            y = W.lane_pos(d, x, y)
        elif c >= 0:
            d = random.choice([1, 3])
            x = W.lane_pos(d, x, y)
        else:
            return None
        for v in self.cars:
            if v.alive and abs(v.x - x) < 70 and abs(v.y - y) < 70:
                return None
        vt = random.choice(TRAFFIC_TYPES)
        v = Vehicle(vt, x, y, d * math.pi / 2, None, 'traffic')
        v.dir = d
        v.driver = None
        spd = v.cruise * 0.6
        v.vx, v.vy = math.cos(v.ang) * spd, math.sin(v.ang) * spd
        self.cars.append(v)
        return v

    def populate(self, initial=False):
        W = self.world
        P = self.player
        near = (P.x, P.y)
        rmin = 0 if initial else 520
        rmax = 1500 if initial else 1150
        ncar = len([v for v in self.cars if v.ai == 'traffic'])
        tries = 0
        while ncar < 26 and tries < (60 if initial else 6):
            tries += 1
            p = W.random_road_point(near, rmin, rmax)
            if p and self.make_traffic_car(p[0], p[1]):
                ncar += 1
        if initial:
            # parked cars on lots
            for k in range(36):
                p = W.random_walk_point()
                if p and W.terrain_at(p[0], p[1]) == LOT:
                    v = Vehicle(random.choice(TRAFFIC_TYPES[:9]), p[0], p[1], random.choice([0, 1.57, 3.14, 4.71]), None, 'parked')
                    ok = all(dist(v.x, v.y, o.x, o.y) > 70 for o in self.cars)
                    if ok:
                        self.cars.append(v)
        nped = len([p for p in self.peds if p.kind in ('civ', 'gang', 'boss') and not p.dead])
        tries = 0
        while nped < (40 if not initial else 50) and tries < (80 if initial else 6):
            tries += 1
            p = W.random_walk_point(near, rmin * 0.7, rmax * 0.8)
            if p is None or W.terrain_at(p[0], p[1]) == ROAD:
                continue
            kind = 'civ'
            if chance(0.07):
                kind = 'gang'
            ped = Ped(kind, p[0], p[1])
            self.peds.append(ped)
            nped += 1
            if kind == 'gang':
                for _ in range(random.randint(0, 2)):
                    g = Ped('gang', p[0] + rnd(-30, 30), p[1] + rnd(-30, 30))
                    self.peds.append(g)

    def despawn(self):
        P = self.player
        px, py = P.pos()
        keep = []
        for v in self.cars:
            if not v.alive:
                continue
            d = dist(v.x, v.y, px, py)
            if v.ai == 'traffic' and v.driver is None and d > 1500:
                continue
            if v.ai in ('police', 'army') and d > 2200:
                continue
            keep.append(v)
        self.cars = keep
        out = []
        for p in self.peds:
            d = dist(p.x, p.y, px, py)
            if p.mission:
                out.append(p)
            elif p.dead and p.dead_t > 20:
                continue
            elif d > 1300 and not p.in_car:
                continue
            else:
                out.append(p)
        self.peds = out
        self.pickups = [p for p in self.pickups if p.alive]
        self.helis = [h for h in self.helis if h.alive]

    def law_spawn(self, dt):
        s = self.stars()
        self.wanted = s
        self.law_t -= dt
        if self.law_t > 0 or s == 0:
            return
        self.law_t = 2.0
        W = self.world
        P = self.player
        px, py = P.pos()
        cars = [v for v in self.cars if v.alive and v.ai in ('police', 'army') and dist(v.x, v.y, px, py) < 1500]
        foot = [p for p in self.peds if p.kind in ('cop', 'swat', 'soldier') and not p.dead and dist(p.x, p.y, px, py) < 1300]
        want_cars = [0, 1, 2, 3, 4, 4, 1][s]
        want_foot = [0, 2, 3, 4, 5, 6, 6][s]
        if len(cars) < want_cars:
            pt = W.random_road_point((px, py), 640, 1000)
            if pt:
                tx, ty = int(pt[0] // TILE), int(pt[1] // TILE)
                if s >= 6 and not any(v.vt == 'tank' for v in cars):
                    v = Vehicle('tank', pt[0], pt[1], rnd(0, 6.28), None, 'army')
                else:
                    v = Vehicle('police', pt[0], pt[1], rnd(0, 6.28), None, 'police')
                if all(dist(v.x, v.y, o.x, o.y) > 60 for o in self.cars):
                    v.siren = True
                    v.driver = None
                    self.cars.append(v)
                    play('siren', 0.5, v.x, v.y)
        if len(foot) < want_foot:
            pt = W.random_walk_point((px, py), 600, 900)
            if pt and W.terrain_at(pt[0], pt[1]) != ROAD:
                kind = 'cop' if s < 3 else random.choice(['cop', 'swat', 'swat'])
                if s >= 6:
                    kind = 'soldier'
                p = Ped(kind, pt[0], pt[1])
                p.hostile = True
                self.peds.append(p)
        if s >= 4 and len(self.helis) < (1 if s < 5 else 2):
            pt = (px + rnd(-900, 900), py + rnd(-700, 700))
            self.helis.append(Heli(pt[0], pt[1]))

    def update_wanted(self, dt):
        P = self.player
        if getattr(self, 'heat', 0.0) <= 0:
            self.heat = 0.0
            self.hidden_t = 0.0
            return
        px, py = P.pos()
        seen = False
        for p in self.peds:
            if p.kind in ('cop', 'swat', 'soldier') and not p.dead and dist(p.x, p.y, px, py) < 480:
                seen = True
                break
        if not seen:
            for v in self.cars:
                if v.alive and v.ai in ('police', 'army') and dist(v.x, v.y, px, py) < 480:
                    seen = True
                    break
        for h in self.helis:
            if dist(h.x, h.y, px, py) < 560:
                seen = True
        self.seen = seen
        if seen:
            self.hidden_t = 0.0
        else:
            self.hidden_t += dt
            if self.hidden_t > 8:
                self.heat = max(0.0, self.heat - dt * 0.35)
                if self.heat < 0.5:
                    self.heat = 0.0
                    self.clear_wanted()
                    self.say(T("Wanted level lost"), 2)

    def on_player_dead(self, how):
        if self.state in ('dead', 'busted'):
            return
        self.state = 'dead'
        self.death_t = 0.0
        self.stats['wasted'] += 1
        play('fail')
        if self.mission:
            self.mission.fail(T("You died"))

    def respawn(self, busted=False):
        P = self.player
        if P.in_car:
            P.in_car.driver = None
            P.in_car = None
        hx, hy = self.world.hosp if not busted else self.world.police_hq
        P.x, P.y = hx, hy + 20
        P.hp = P.maxhp
        P.armor = 0
        P.dead = False
        self.heat = 0.0
        self.clear_wanted()
        fine = min(self.money, 200 if not busted else max(100, int(self.money * 0.1)))
        self.money -= fine
        if busted:
            self.weapons = {'fist': 0, 'bat': 0}
            P.weapon = 'fist'
        self.say(T("Hospital bill: $%d") % fine if not busted else T("Bail paid: $%d, weapons confiscated") % fine, 4)
        self.state = 'play'
        self.update_cam(1.0, snap=True)


# ================================================================ GAME UPDATE
class Target:
    def __init__(self, x, y):
        self.x, self.y, self.dead, self.in_car = x, y, False, None


def g_find_target(self, face):
    P = self.player
    px, py = P.pos()
    best, bs = None, 1e9
    for p in self.peds:
        if p.dead or p.in_car:
            continue
        d = dist(px, py, p.x, p.y)
        if d > 430:
            continue
        a = abs(wrap(ang_to(px, py, p.x, p.y) - face))
        if a > 1.15:
            continue
        if not self.world.line_clear(px, py, p.x, p.y, 24):
            continue
        hostile = p.hostile or (self.wanted > 0 and p.kind in ('cop', 'swat', 'soldier')) or p.mission == 'target'
        s = d + a * 90 - (220 if hostile else 0) + (120 if p.kind == 'civ' else 0)
        if s < bs:
            best, bs = p, s
    for h in self.helis:
        d = dist(px, py, h.x, h.y)
        if d < 520 and abs(wrap(ang_to(px, py, h.x, h.y) - face)) < 1.2:
            if -100 < bs:
                best, bs = h, -100
    return best


def g_player_shoot(self, tgt, face):
    P = self.player
    px, py = P.pos()
    wid = P.weapon
    w = WEAPONS[wid]
    if P.cool > 0:
        return
    if w.get('melee'):
        P.cool = w['rate']
        self.melee_hit(P, P.ang, w, 'player')
        return
    if self.weapons.get(wid, 0) <= 0:
        self.say(T("Out of ammo"), 1.5)
        self.cycle_weapon(1)
        P.cool = 0.4
        return
    self.weapons[wid] -= 1
    P.cool = w['rate']
    a = face
    if tgt is not None:
        a = ang_to(px, py, tgt.x, tgt.y)
    self.fire_bullet(px, py, a, wid, P, 'player')


def g_cycle_weapon(self, d=1):
    P = self.player
    owned = [w for w in WORDER if w in self.weapons and (w in ('fist', 'bat') or self.weapons[w] > 0)]
    if not owned:
        owned = ['fist']
    try:
        i = owned.index(P.weapon)
    except ValueError:
        i = 0
    P.weapon = owned[(i + d) % len(owned)]
    play('click')


def g_player_foot(self, dt):
    P, c = self.player, self.ctl
    spd = 98.0
    moving = abs(c.mx) + abs(c.my) > 0.05
    if c.sprint and self.stamina > 3 and moving:
        spd = 170.0
        self.stamina -= 28 * dt
    else:
        self.stamina = min(100.0, self.stamina + 16 * dt)
    mx, my = c.mx, c.my
    face = P.ang
    if moving:
        face = math.atan2(my, mx)
    tgt = None
    if c.fire:
        tgt = self.find_target(face if moving else P.ang)
        if tgt is not None:
            face = ang_to(P.x, P.y, tgt.x, tgt.y)
    P.ang = lerp_ang(P.ang, face, 0.35)
    P.move(mx * spd, my * spd, dt)
    P.mv = moving
    if moving:
        P.phase += dt * (spd / 10.0)
    if c.fire:
        self.player_shoot(tgt, P.ang)
    if P.cool > 0:
        P.cool -= dt
    if P.hurt_t > 0:
        P.hurt_t -= dt
    self.stats['dist'] += math.hypot(mx, my) * spd * dt


def g_player_car(self, dt):
    P, c = self.player, self.ctl
    v = P.in_car
    v.gas, v.brake, v.steer, v.hb = c.gas, c.brake, c.steer, c.hb
    if c.horn and v.hornt <= 0:
        v.hornt = 0.4
        play('horn', 0.7, v.x, v.y)
        self.noise(v.x, v.y, 300)
    P.x, P.y = v.x, v.y
    P.ang = v.ang
    if P.cool > 0:
        P.cool -= dt
    if c.fire:
        tgt = self.find_target(v.ang) if v.vt != 'tank' else None
        if v.vt == 'tank':
            tg = self.find_target(v.ang)
            if tg is not None:
                v.tur = lerp_ang(v.tur, ang_to(v.x, v.y, tg.x, tg.y), 0.2)
            else:
                v.tur = lerp_ang(v.tur, v.ang, 0.1)
            if P.cool <= 0:
                P.cool = 1.1
                self.fire_bullet(v.x, v.y, v.tur, 'rpg', P, 'player')
        elif P.weapon not in ('fist', 'bat'):
            self.player_shoot(tgt, v.ang)
    elif v.vt == 'tank':
        v.tur = lerp_ang(v.tur, v.ang, 0.1)
    self.stats['dist'] += v.speed * dt


def g_enter_exit(self):
    P = self.player
    if P.in_car:
        v = P.in_car
        c, s = math.cos(v.ang), math.sin(v.ang)
        for side in (1, -1):
            nx = v.x - s * side * (v.sp['W'] / 2 + 16)
            ny = v.y + c * side * (v.sp['W'] / 2 + 16)
            if not self.world.solid_px(nx, ny):
                break
        else:
            nx, ny = v.x, v.y
        P.in_car = None
        P.x, P.y = nx, ny
        v.driver = None
        v.ai = 'parked'
        v.gas = v.brake = v.steer = 0
        self.ctl.set_mode('foot')
        if self.mission:
            self.mission.on_exit_car(v)
        return True
    best, bd = None, 56
    for v in self.cars:
        if v.alive and not v.wreck:
            d = dist(P.x, P.y, v.x, v.y)
            if d < bd + (v.sp['L'] * 0.2):
                best, bd = v, d
    if best is None:
        return False
    v = best
    if v.ai in ('traffic', 'flee', 'police', 'army', 'chase', 'mission') and v.driver is None:
        if v.ai in ('police', 'army') or v.vt == 'police':
            self.add_heat(1.0)
        ped = Ped('civ', v.x, v.y + 16)
        ped.fear = 8
        ped.threat = (P.x, P.y)
        self.peds.append(ped)
        self.add_wanted_event(v.x, v.y, 0.25, 'player')
        self.float_text(T("Carjacked!"), v.x, v.y - 20, (255, 200, 80))
    v.driver = 'player'
    v.ai = 'none'
    v.hostile = False
    P.in_car = v
    self.ctl.set_mode('car')
    self.stats['cars_used'] = self.stats.get('cars_used', 0) + 1
    if v.vt in ('taxi',) and self.side is None:
        self.say(T("Taxi: pick up passengers! (phone > Side jobs)"), 3)
    if self.mission:
        self.mission.on_enter_car(v)
    return True


def g_poi_near(self, in_car=False):
    P = self.player
    for poi in self.world.pois:
        r = 70 if in_car else 58
        if dist(P.x, P.y, poi['x'], poi['y']) < r:
            return poi
    return None


def g_collisions(self, dt):
    P = self.player
    cars = [v for v in self.cars if v.alive and abs(v.x - P.x) < 900 and abs(v.y - P.y) < 700]
    n = len(cars)
    for i in range(n):
        a = cars[i]
        ac = a.circles()
        for j in range(i + 1, n):
            b = cars[j]
            if abs(a.x - b.x) > 90 or abs(a.y - b.y) > 90:
                continue
            for (ax, ay) in ac:
                hit = False
                for (bx, by) in b.circles():
                    dx, dy = ax - bx, ay - by
                    rr = a.R + b.R
                    d2 = dx * dx + dy * dy
                    if d2 < rr * rr:
                        d = math.sqrt(d2) or 0.01
                        nx, ny = dx / d, dy / d
                        pen = rr - d
                        ma, mb = a.sp['L'] * a.sp['W'], b.sp['L'] * b.sp['W']
                        if a.ai == 'parked' and a.driver is None:
                            ma *= 3
                        if b.ai == 'parked' and b.driver is None:
                            mb *= 3
                        ta, tb = mb / (ma + mb), ma / (ma + mb)
                        a.x += nx * pen * ta
                        a.y += ny * pen * ta
                        b.x -= nx * pen * tb
                        b.y -= ny * pen * tb
                        rvx, rvy = a.vx - b.vx, a.vy - b.vy
                        vn = rvx * nx + rvy * ny
                        if vn < 0:
                            j_ = -1.4 * vn
                            a.vx += nx * j_ * ta
                            a.vy += ny * j_ * ta
                            b.vx -= nx * j_ * tb
                            b.vy -= ny * j_ * tb
                            imp = -vn
                            if imp > 90:
                                a.damage(imp * 0.07 * tb * 2, b.driver and 'player' if b.driver == 'player' else None)
                                b.damage(imp * 0.07 * ta * 2, 'player' if a.driver == 'player' else None)
                                sparks((ax + bx) / 2, (ay + by) / 2, 3)
                                play('crash', clamp(imp / 300.0, 0.2, 1.0), a.x, a.y)
                                if a.driver == 'player' or b.driver == 'player':
                                    self.shake = max(self.shake, imp / 50.0)
                                    o = b if a.driver == 'player' else a
                                    if o.ai in ('traffic',) and o.hp < o.maxhp * 0.8:
                                        o.ai = 'flee'
                                    if o.vt == 'police':
                                        self.add_heat(0.3)
                        hit = True
                        break
                if hit:
                    break
    # cars vs people
    allp = [P] + self.peds
    for v in cars:
        sp = v.speed
        if sp < 45 or v.wreck and sp < 90:
            continue
        circ = v.circles()
        for p in allp:
            if p.dead or p.in_car or p.hurt_t > 0:
                continue
            if abs(p.x - v.x) > 60 or abs(p.y - v.y) > 60:
                continue
            for (cx, cy) in circ:
                if dist(cx, cy, p.x, p.y) < v.R + 6:
                    dmg = sp * 0.22
                    if p is P and self.cheat_god:
                        dmg = 0
                    owner = 'player' if v.driver == 'player' else None
                    p.hurt(dmg, owner, 'car')
                    p.hurt_t = 0.4
                    a = ang_to(v.x, v.y, p.x, p.y)
                    p.kx += v.vx * 0.9 + math.cos(a) * 120
                    p.ky += v.vy * 0.9 + math.sin(a) * 120
                    blood(p.x, p.y, 5)
                    play('hit', 0.8, p.x, p.y)
                    v.vx *= 0.93
                    v.vy *= 0.93
                    if owner:
                        self.add_wanted_event(p.x, p.y, 0.15 if p.kind == 'civ' else 0.6, 'player')
                        self.noise(p.x, p.y, 250)
                    break


def g_pickups(self, dt):
    P = self.player
    for pk in self.pickups:
        pk.update(dt)
        if not pk.alive or abs(pk.x - P.x) > 30 or abs(pk.y - P.y) > 30:
            continue
        if dist(pk.x, pk.y, P.x, P.y) > 24:
            continue
        k = pk.kind
        if k == 'health':
            if P.hp >= P.maxhp:
                continue
            P.hp = P.maxhp
            self.say(T("Health restored"), 1.5)
        elif k == 'armor':
            if P.armor >= 100:
                continue
            P.armor = 100
            self.say(T("Body armor"), 1.5)
        elif k == 'cash':
            self.give_money(pk.val)
            self.float_text('+$%d' % pk.val, pk.x, pk.y - 10, (120, 255, 120))
        elif k in ('weapon', 'weapon_drop'):
            w = WEAPONS.get(pk.wid)
            if w is None or pk.wid in ('fist', 'bat'):
                pk.alive = False
                continue
            self.weapons[pk.wid] = min(w['ammo'] * 2, self.weapons.get(pk.wid, 0) + max(10, w['ammo'] // 3))
            self.say(T("Picked up: ") + T(w['n']), 2)
            if P.weapon in ('fist', 'bat'):
                P.weapon = pk.wid
        elif k == 'package':
            self.pkg_found.add(pk.val)
            self.stats['packages'] += 1
            self.give_money(200)
            n = len(self.pkg_found)
            self.say(T("Hidden package %d/24 (+$200)") % n, 2.5)
            if n == 24:
                self.give_money(10000)
                self.say(T("All packages found! +$10000"), 4)
        pk.alive = False
        play('pickup', 0.8)


def g_update_cam(self, dt, snap=False):
    P = self.player
    px, py = P.pos()
    lead = (0.0, 0.0)
    if P.in_car:
        lead = (P.in_car.vx * 0.45, P.in_car.vy * 0.45)
    tx, ty = px + lead[0], py + lead[1]
    k = 1.0 if snap else clamp(dt * 5.0, 0, 1)
    self.cam_c[0] = lerp(self.cam_c[0], tx, k)
    self.cam_c[1] = lerp(self.cam_c[1], ty, k)
    sx = sy = 0.0
    if self.shake > 0.2 and self.settings.get('shake', True):
        sx, sy = rnd(-1, 1) * self.shake, rnd(-1, 1) * self.shake
    self.shake = max(0.0, self.shake - dt * 30)
    CAM[0] = clamp(self.cam_c[0] - LW / 2, 0, WPX - LW) + sx
    CAM[1] = clamp(self.cam_c[1] - LH / 2, 0, HPX - LH) + sy


def g_clock(self, dt):
    self.clock = (self.clock + dt * 1.2) % 1440.0
    self.rain_t -= dt
    if self.rain_t <= 0:
        self.rain_t = rnd(90, 300)
        self.rain_target = 0.0 if getattr(self, 'rain_target', 0.0) > 0 else 1.0
    self.rain = lerp(self.rain, getattr(self, 'rain_target', 0.0), dt * 0.2)


def g_darkness(self):
    h = self.clock / 60.0
    if h >= 21 or h < 5:
        return 1.0
    if h >= 19:
        return (h - 19) / 2.0
    if h < 7:
        return 1.0 - (h - 5) / 2.0
    return 0.0


def g_district_update(self, dt):
    P = self.player
    i = clamp(int((P.x / TILE - 1) // CELL), 0, COLS)
    j = clamp(int((P.y / TILE - 1) // CELL), 0, ROWS - 1)
    d = DIST_NAMES.get(district_of(i, j), '')
    if d != self.district:
        self.district = d
        self.dist_t = 3.0
    if self.dist_t > 0:
        self.dist_t -= dt


def g_update_play(self, dt):
    P, c = self.player, self.ctl
    W = self.world
    self.stats['time'] += dt
    # input toggles
    if 'pause' in c.pressed:
        self.state = 'pause'
        self.menu_sel = 0
        return
    if 'map' in c.pressed:
        self.state = 'map'
        return
    if 'phone' in c.pressed:
        self.state = 'phone'
        self.phone_tab = 0
        self.menu_sel = 0
        return
    if 'wpn' in c.pressed and not P.in_car:
        self.cycle_weapon(1)
    if 'radio' in c.pressed and P.in_car:
        self.radio = (self.radio + 1) % len(RADIO)
        self.say(T("Radio: ") + RADIO[self.radio], 1.5)
    if 'act' in c.pressed:
        poi = self.poi_near(bool(P.in_car))
        if poi and (not P.in_car or poi['kind'] in ('spray', 'scrap', 'garage', 'safehouse', 'police')):
            self.open_poi(poi)
            return
        self.enter_exit()
    c.set_mode('car' if P.in_car else 'foot')
    if P.in_car:
        self.player_car(dt)
    else:
        self.player_foot(dt)
    # world
    self.clock_tick(dt)
    for pk in self.shots[:]:
        pk[0] -= dt
        if pk[0] <= 0:
            self.shots.remove(pk)
            self.fire_bullet(pk[1], pk[2], pk[3], pk[4], pk[5], pk[6])
    px, py = P.pos()
    for v in self.cars:
        if v.alive and abs(v.x - px) < 1400 and abs(v.y - py) < 1200:
            v.update(dt)
        elif v.alive and v.driver == 'player':
            v.update(dt)
    for p in self.peds:
        if abs(p.x - px) < 1300 and abs(p.y - py) < 1100:
            p.update(dt)
    for h in self.helis:
        h.update(dt)
    for b in self.bullets[:]:
        if not b.update(dt):
            self.bullets.remove(b)
    for pt in self.parts[:]:
        pt.life -= dt
        if pt.life <= 0:
            self.parts.remove(pt)
            continue
        pt.x += pt.vx * dt
        pt.y += pt.vy * dt
        pt.size += pt.grow * dt
        if pt.kind in ('blood', 'spark'):
            pt.vx *= 0.9
            pt.vy *= 0.9
    for lst in (self.decals, self.skids):
        for d in lst:
            d[-1] -= dt
        lst[:] = [d for d in lst if d[-1] > 0]
    for t in self.texts:
        t[3] -= dt
        t[2] -= 22 * dt
    self.texts = [t for t in self.texts if t[3] > 0]
    for m in self.msgs:
        m[1] -= dt
    self.msgs = [m for m in self.msgs if m[1] > 0]
    self.collisions(dt)
    self.pickups_update(dt)
    # player in wreck
    if P.in_car and P.in_car.wreck:
        v = P.in_car
        if v.fire <= 0:
            P.hurt(40, None, 'explosion')
            self.enter_exit()
            v.alive = False
        else:
            P.hurt(8 * dt, None, 'fire')
    if P.hp <= 0 and not P.dead:
        P.die(None, 'x')
    if P.in_car and P.in_car.sink > 2.0:
        self.enter_exit()
    # regen / spawn
    self.spawn_t -= dt
    if self.spawn_t <= 0:
        self.spawn_t = 1.2
        self.populate()
        self.despawn()
    self.law_spawn(dt)
    self.update_wanted(dt)
    self.check_busted(dt)
    self.district_update(dt)
    if self.mission:
        self.mission.update(dt)
    elif self.side:
        self.side.update(dt)
    self.update_cam(dt)
    if self.hp_flash > 0:
        self.hp_flash -= dt


def g_check_busted(self, dt):
    P = self.player
    if self.wanted <= 0 or P.in_car and P.in_car.speed > 60:
        self.busted_t = 0
        return
    cops = [p for p in self.peds if p.kind in ('cop', 'swat') and not p.dead and dist(p.x, p.y, *P.pos()) < 34]
    if cops and P.hp < 100 * 0.999 and (P.hp < 35 or P.in_car is None and len(cops) >= 2):
        self.busted_t += dt
        if self.busted_t > 1.8:
            self.state = 'busted'
            self.death_t = 0
            self.stats['busted'] += 1
            play('fail')
            if self.mission:
                self.mission.fail(T("Busted"))
    else:
        self.busted_t = max(0, self.busted_t - dt)


Game.find_target = g_find_target
Game.player_shoot = g_player_shoot
Game.cycle_weapon = g_cycle_weapon
Game.player_foot = g_player_foot
Game.player_car = g_player_car
Game.enter_exit = g_enter_exit
Game.poi_near = g_poi_near
Game.collisions = g_collisions
Game.pickups_update = g_pickups
Game.update_cam = g_update_cam
Game.clock_tick = g_clock
Game.darkness = g_darkness
Game.district_update = g_district_update
Game.update_play = g_update_play
Game.check_busted = g_check_busted


# ================================================================ MISSIONS
class MissionFail(Exception):
    pass


class Mission:
    def __init__(self, name, fn, reward, repeat=False, info=''):
        self.name, self.fn, self.reward, self.repeat, self.info = name, fn, reward, repeat, info
        self.obj = ''
        self.blips = []
        self.timer = None
        self.gen = None
        self.ents = []
        self.kills = 0
        self.destroyed = []
        self.flags = {}
        self.over = False
        self.t = 0.0
        self.sub = ''

    # --- API for scripts ---------------------------------------------------
    def start(self):
        self.gen = self.fn(self)
        G.mission = self
        G.say(T("Mission: ") + T(self.name), 3)

    def blip(self, x, y, label='', col=YELLOW, follow=None):
        b = {'x': x, 'y': y, 'label': label, 'col': col, 'follow': follow}
        self.blips.append(b)
        return b

    def rm(self, b):
        if b in self.blips:
            self.blips.remove(b)

    def car(self, vt, x, y, ang=0.0, ai='parked', color=None):
        v = Vehicle(vt, x, y, ang, color, ai)
        v.mission = self
        G.cars.append(v)
        self.ents.append(v)
        return v

    def ped(self, kind, x, y, weapon=None, hostile=False, target=False):
        p = Ped(kind, x, y)
        if weapon:
            p.weapon = weapon
        p.hostile = hostile
        if target:
            p.mission = 'target'
        G.peds.append(p)
        self.ents.append(p)
        return p

    def on_kill(self, p):
        self.kills += 1

    def on_car_destroyed(self, v):
        self.destroyed.append(v)

    def on_enter_car(self, v):
        pass

    def on_exit_car(self, v):
        pass

    def fail(self, why):
        if self.over:
            return
        self.over = True
        G.say(T("MISSION FAILED: ") + why, 4)
        G.banner = (T("MISSION FAILED"), 3.0, (230, 60, 60))
        play('fail')
        self.cleanup()

    def cleanup(self):
        for e in self.ents:
            if isinstance(e, Vehicle) and e.driver != 'player':
                e.mission = None
                if e.ai in ('mission', 'chase'):
                    e.ai = 'traffic'
            elif isinstance(e, Ped):
                e.mission = None
        G.mission = None
        G.stats['missions'] = G.stats.get('missions', 0)

    def succeed(self):
        self.over = True
        G.give_money(self.reward)
        G.stats['missions'] += 1
        G.banner = (T("MISSION PASSED"), 3.5, (250, 220, 70))
        G.say("+$%d" % self.reward, 4)
        play('win')
        if not self.repeat:
            G.done_missions += 1
        self.cleanup()

    # --- generators ---------------------------------------------------------
    def wait(self, sec):
        t = 0.0
        while t < sec:
            t += G.dt
            yield

    def reach(self, b, r=48, car=None, speed=None):
        while True:
            px, py = G.player.pos()
            ok = dist(px, py, b['x'], b['y']) < r
            if ok and car is not None and bool(G.player.in_car) != car:
                ok = False
            if ok and speed is not None and G.player.in_car and G.player.in_car.speed > speed:
                ok = False
            if ok:
                break
            yield
        self.rm(b)

    def need_car(self, v=None):
        while not (G.player.in_car and (v is None or G.player.in_car is v)):
            if v is not None and (not v.alive or v.wreck):
                raise MissionFail(T("The vehicle was destroyed"))
            yield

    def kill_all(self, peds, label=True):
        bl = {}
        for p in peds:
            bl[p] = self.blip(p.x, p.y, '', RED, p) if label else None
        while True:
            left = [p for p in peds if not p.dead and p in G.peds]
            if not left:
                break
            self.sub = '%d/%d' % (len(peds) - len(left), len(peds))
            yield
        for b in bl.values():
            self.rm(b)
        self.sub = ''

    def update(self, dt):
        if self.over:
            return
        self.t += dt
        if self.timer is not None:
            self.timer -= dt
            if self.timer <= 0:
                self.fail(T("Time is up"))
                return
        for b in self.blips:
            f = b.get('follow')
            if f is not None:
                b['x'], b['y'] = f.pos() if hasattr(f, 'pos') else (f.x, f.y)
        try:
            next(self.gen)
        except StopIteration:
            self.succeed()
        except MissionFail as e:
            self.fail(str(e))


def poi_pos(kind):
    for p in G.world.pois:
        if p['kind'] == kind:
            return p['x'], p['y']
    return G.player.x, G.player.y


def far_road(minr=1400, maxr=2600):
    for _ in range(40):
        p = G.world.random_road_point((G.player.x, G.player.y), minr, maxr)
        if p and p[0] < (COLS * CELL) * TILE:
            return p
    return G.world.random_road_point()


def harbour_pos():
    return (COLS * CELL + 2 + 6.0) * TILE, (3 * 12 + 4.0) * TILE


def m_first(M):
    G.give_money(350)
    M.obj = T("Steal a car (stand next to one, press ACT)")
    while not G.player.in_car:
        yield
    b = M.blip(*poi_pos('ammu'), T('Ammu-Nation'))
    M.obj = T("Drive to Ammu-Nation")
    yield from M.reach(b, 80, car=True)
    M.obj = T("Get out (ACT) and buy a Pistol inside the shop (ACT near the door)")
    while G.weapons.get('pistol', 0) <= 0:
        if not G.player.in_car and dist(G.player.x, G.player.y, *poi_pos('ammu')) > 900:
            raise MissionFail(T("You left the area"))
        yield


def m_debt(M):
    G.weapons['bat'] = 0
    G.player.weapon = 'bat'
    x, y = far_road(900, 1500)
    p = M.ped('boss', x, y + 30, 'pistol', True, True)
    p.hp = p.maxhp = 120
    M.obj = T("Find and beat up 'Fat Tony' (red marker)")
    yield from M.kill_all([p])


def m_parcel(M):
    v = M.car('van', *poi_pos('junk'), 0.0, 'parked', (230, 230, 230))
    v.y += 60
    b = M.blip(v.x, v.y, T('Van'), GREEN, v)
    M.obj = T("Get in the delivery van")
    yield from M.need_car(v)
    M.rm(b)
    dx, dy = far_road(2000, 3000)
    d = M.blip(dx, dy, T('Drop-off'))
    M.timer = 110
    M.obj = T("Deliver the parcel fast - don't wreck the van!")
    while True:
        if v.hp < 25 or not v.alive:
            raise MissionFail(T("The van is wrecked"))
        px, py = G.player.pos()
        if dist(px, py, dx, dy) < 60 and G.player.in_car is v:
            break
        yield
    M.rm(d)


def m_taxi(M):
    v = M.car('taxi', *poi_pos('hospital'), 0.0, 'parked')
    v.y += 90
    b = M.blip(v.x, v.y, T('Taxi'), GREEN, v)
    M.obj = T("Get in the taxi")
    yield from M.need_car(v)
    M.rm(b)
    for fare in range(3):
        px_, py_ = far_road(700, 1500)
        p = M.blip(px_, py_, T('Passenger'))
        M.obj = T("Pick up passenger %d/3") % (fare + 1)
        M.timer = None
        yield from M.reach(p, 70, car=True, speed=60)
        yield from M.wait(1.2)
        qx, qy = far_road(1200, 2400)
        d = M.blip(qx, qy, T('Destination'))
        M.obj = T("Take the passenger to the destination")
        M.timer = 90
        yield from M.reach(d, 70, car=True, speed=60)
        G.add_cash_pop(qx, qy, 150)
    M.timer = None


def m_race(M):
    v = M.car('sport', *poi_pos('stunt'), 0.0, 'parked', (240, 60, 30))
    v.y += 90
    b = M.blip(v.x, v.y, T('Race car'), GREEN, v)
    M.obj = T("Get in the race car")
    yield from M.need_car(v)
    M.rm(b)
    W = G.world
    pts = []
    for k in range(8):
        for _ in range(30):
            p = W.random_road_point(poi_pos('stunt'), 400, 3000)
            if p and (not pts or dist(p[0], p[1], pts[-1][0], pts[-1][1]) > 500):
                pts.append(p)
                break
    M.timer = 30 + 9 * len(pts) + 20
    for k, p in enumerate(pts):
        bb = M.blip(p[0], p[1], str(k + 1))
        M.obj = T("Checkpoint %d/%d") % (k + 1, len(pts))
        yield from M.reach(bb, 70, car=True)
        play('pickup')
        M.timer += 6


def m_war(M):
    x, y = poi_pos('junk')
    gs = [M.ped('gang', x + rnd(-250, 250), y + rnd(100, 400), random.choice(['pistol', 'smg', 'bat']), True)
          for _ in range(8)]
    for g in gs:
        g.x = clamp(g.x, 100, WPX - 800)
    G.weapons['smg'] = max(G.weapons.get('smg', 0), 120)
    M.obj = T("Wipe out the gang near the Scrapyard")
    yield from M.kill_all(gs)


def m_heist(M):
    b = M.blip(*poi_pos('clothes'), T('Mall'))
    M.obj = T("Go to the Mall")
    yield from M.reach(b, 90)
    G.add_heat(3.5)
    G.float_text(T("ROBBERY!"), G.player.x, G.player.y - 30, RED)
    G.give_money(3000)
    G.say(T("Got $3000! Cops are coming!"), 3)
    M.obj = T("Lose the cops! (or use Pay'n'Spray)")
    yield from M.wait(3)
    while G.stars() > 0:
        yield


def m_chase(M):
    p = far_road(800, 1200)
    v = M.car('sport', p[0], p[1], 0.0, 'flee', (240, 220, 30))
    v.hp = v.maxhp = 180
    v.driver = None
    v.cruise = 420
    d = M.blip(v.x, v.y, T('Target'), RED, v)
    M.timer = 140
    M.obj = T("Catch and destroy the yellow sports car!")
    while v.alive and not v.wreck:
        if v.ai != 'flee':
            v.ai = 'flee'
        a = ang_to(G.player.x, G.player.y, v.x, v.y)
        v.drive_to(v.x + math.cos(a) * 500, v.y + math.sin(a) * 500, v.sp['vmax'] * 0.85, G.dt)
        yield
    M.rm(d)


def m_harbour(M):
    v = M.car('truck', *poi_pos('junk'), 0.0, 'parked', (60, 100, 150))
    v.y += 70
    b = M.blip(v.x, v.y, T('Truck'), GREEN, v)
    M.obj = T("Get in the truck")
    yield from M.need_car(v)
    M.rm(b)
    hx, hy = harbour_pos()
    d = M.blip(hx, hy, T('Harbour'))
    M.obj = T("Deliver the truck to the Harbour - watch for ambush!")
    amb = False
    chasers = []
    while True:
        if not v.alive or v.wreck:
            raise MissionFail(T("The truck was destroyed"))
        px, py = G.player.pos()
        if not amb and dist(px, py, hx, hy) < 2300:
            amb = True
            for k in range(3):
                pt = G.world.random_road_point((px, py), 500, 800)
                if pt:
                    c = M.car('muscle', pt[0], pt[1], 0.0, 'chase', (30, 30, 30))
                    c.hp = c.maxhp = 90
                    chasers.append(c)
            G.say(T("Ambush! Gang cars incoming!"), 3)
        for c in chasers:
            c.target = (px, py)
            if c.alive and not c.wreck and dist(c.x, c.y, px, py) < 120 and G.player.in_car is v:
                v.damage(G.dt * 14, None)
        if dist(px, py, hx, hy) < 90 and G.player.in_car is v:
            break
        yield
    M.rm(d)


def m_rampage(M):
    G.weapons['rpg'] = max(G.weapons.get('rpg', 0), 12)
    G.player.weapon = 'rpg'
    cs = []
    for k in range(6):
        p = G.world.random_road_point((4.5 * 12 * TILE, 3.5 * 12 * TILE), 100, 900)
        if p:
            c = M.car('sedan', p[0], p[1], rnd(0, 6.28), 'parked', (250, 30, 30))
            cs.append(c)
            M.blip(c.x, c.y, '', RED, c)
    M.timer = 160
    M.obj = T("Blow up all 6 red cars in Downtown (Rocket Launcher given)")
    while True:
        left = [c for c in cs if c.alive and not c.wreck]
        M.sub = '%d/%d' % (len(cs) - len(left), len(cs))
        if not left:
            break
        yield
    M.blips[:] = []
    M.sub = ''


def m_bank(M):
    bx, by = poi_pos('police')
    cx, cy = 4.5 * 12 * TILE + 100, 3.5 * 12 * TILE
    b = M.blip(cx, cy, T('Bank'))
    M.obj = T("Go to the Downtown Bank")
    yield from M.reach(b, 140)
    guards = [M.ped('gang', cx + rnd(-120, 120), cy + rnd(-120, 120), 'rifle', True) for _ in range(6)]
    G.add_heat(2.0)
    M.obj = T("Kill the guards")
    yield from M.kill_all(guards)
    sx, sy = poi_pos('safehouse')
    d = M.blip(cx, cy, T('Vault'))
    M.obj = T("Grab the cash from the vault")
    yield from M.reach(d, 40)
    G.give_money(5000)
    G.add_heat(5.0)
    G.say(T("Cops everywhere! Reach the Safehouse!"), 3)
    h = M.blip(sx, sy, T('Safehouse'))
    M.obj = T("Escape to the Safehouse")
    yield from M.reach(h, 80)


def m_boss(M):
    sx, sy = poi_pos('stunt')
    b = M.blip(sx, sy, T('Stadium'))
    M.obj = T("Go to the Stadium")
    G.weapons['rifle'] = max(G.weapons.get('rifle', 0), 200)
    G.player.armor = 100
    yield from M.reach(b, 260)
    boss = M.ped('boss', sx, sy - 100, 'smg', True, True)
    boss.hp = boss.maxhp = 400
    guards = [M.ped('gang', sx + rnd(-200, 200), sy + rnd(-150, 150), random.choice(['smg', 'rifle', 'shotgun']), True)
              for _ in range(6)]
    M.obj = T("Kill the Boss and his bodyguards")
    yield from M.kill_all(guards + [boss])
    G.say(T("You ruled Almaty City! Keep playing freely."), 6)


def m_vigil(M):
    G.weapons['pistol'] = max(G.weapons.get('pistol', 0), 60)
    cs = []
    for k in range(5):
        p = G.world.random_walk_point((G.player.x, G.player.y), 500, 1600)
        if p:
            cs.append(M.ped('gang', p[0], p[1], random.choice(['pistol', 'bat', 'smg']), True, True))
    M.obj = T("Vigilante: hunt 5 criminals")
    yield from M.kill_all(cs)


def m_range(M):
    sx, sy = poi_pos('range')
    ts = []
    M.timer = 45
    M.obj = T("Shooting range: kill all dummies in 45 s")
    for k in range(10):
        p = M.ped('civ', sx + rnd(-300, 300), sy + rnd(80, 400))
        p.color = (200, 200, 60)
        p.hp = 25
        p.fear = 0
        ts.append(p)
    for p in ts:
        p.speed = 0
    G.weapons['pistol'] = max(G.weapons.get('pistol', 0), 80)
    yield from M.kill_all(ts)


MISSION_LIST = [
    ('First Wheels', m_first, 300, 'Steal a car, get a gun.'),
    ('Debt Collector', m_debt, 700, 'Beat up a gangster with a bat.'),
    ('Parcel Express', m_parcel, 900, 'Time-limited delivery.'),
    ('Taxi Driver', m_taxi, 1000, 'Three taxi fares.'),
    ('Time Trial', m_race, 1800, '8 checkpoints in a sports car.'),
    ('Gang War', m_war, 2000, 'Wipe out a gang.'),
    ('Mall Heist', m_heist, 2500, 'Rob it, then lose the cops.'),
    ('Hit & Run', m_chase, 2500, 'Destroy a fleeing car.'),
    ('Harbour Deal', m_harbour, 4000, 'Deliver a truck through an ambush.'),
    ('Rocket Rampage', m_rampage, 3500, 'RPG fun in Downtown.'),
    ('Bank Job', m_bank, 9000, 'Big score, big heat.'),
    ('The Boss', m_boss, 20000, 'Final showdown at the Stadium.'),
]
SIDE_LIST = [
    ('Vigilante', m_vigil, 1200, 'Hunt 5 criminals.'),
    ('Shooting Range', m_range, 600, 'Quick target practice.'),
    ('Street Race', m_race, 1500, 'Race through the city.'),
    ('Taxi Fares', m_taxi, 800, 'Earn money as a cabbie.'),
]


def start_mission(entry, repeat=False):
    if G.mission:
        G.say(T("Finish the current mission first"), 2)
        return
    n, fn, rew, info = entry
    m = Mission(n, fn, rew, repeat, info)
    m.start()
    G.state = 'play'


# ================================================================ SHOPS / POI
def g_open_poi(self, poi):
    k = poi['kind']
    P = self.player
    items = []
    title = T(poi['name'])

    def buy_weapon(wid):
        w = WEAPONS[wid]

        def f():
            if self.money < w['price']:
                self.say(T("Not enough money"), 2)
                return
            self.give_money(-w['price'])
            self.weapons[wid] = self.weapons.get(wid, 0) + w['ammo'] // 2
            if P.weapon in ('fist', 'bat'):
                P.weapon = wid
            self.say(T("Bought ") + T(w['n']), 2)
            self.open_poi(poi)
        return f

    def buy_ammo(wid):
        w = WEAPONS[wid]
        cost = max(20, int(w['price'] * 0.15))

        def f():
            if self.money < cost:
                self.say(T("Not enough money"), 2)
                return
            self.give_money(-cost)
            self.weapons[wid] = min(w['ammo'] * 2, self.weapons.get(wid, 0) + w['ap'])
            self.open_poi(poi)
        return f

    if k == 'ammu':
        for wid in WORDER[2:]:
            w = WEAPONS[wid]
            if self.weapons.get(wid, 0) > 0 or wid in self.weapons:
                items.append((T("Ammo: ") + T(w['n']) + " +%d" % w['ap'], max(20, int(w['price'] * 0.15)), buy_ammo(wid)))
            else:
                items.append((T("Buy ") + T(w['n']), w['price'], buy_weapon(wid)))
        items.append((T("Body armor"), 400, lambda: self.buy_simple(400, lambda: setattr(P, 'armor', 100), poi)))
    elif k == 'range':
        items.append((T("Start Shooting Range"), 0, lambda: (setattr(self, 'state', 'play'), start_mission(SIDE_LIST[1], True))))
    elif k == 'hospital':
        items.append((T("Treatment (full health)"), 100, lambda: self.buy_simple(100, lambda: setattr(P, 'hp', P.maxhp), poi)))
        items.append((T("Body armor"), 300, lambda: self.buy_simple(300, lambda: setattr(P, 'armor', 100), poi)))
    elif k == 'clothes':
        items.append((T("Burger (+40 HP)"), 30, lambda: self.buy_simple(30, lambda: setattr(P, 'hp', min(P.maxhp, P.hp + 40)), poi)))
        items.append((T("Body armor"), 300, lambda: self.buy_simple(300, lambda: setattr(P, 'armor', 100), poi)))
    elif k == 'spray':
        if P.in_car:
            cost = 250 + 150 * self.stars()
            items.append((T("Respray & repair (clears wanted)"), cost, lambda: self.buy_simple(cost, self.respray, poi)))
        else:
            items.append((T("Drive a car in first!"), 0, lambda: None))
    elif k == 'police':
        items.append((T("Bribe an officer (clears wanted)"), 1500 + 500 * self.stars(), lambda: self.buy_simple(1500 + 500 * self.stars(), self.clear_wanted, poi)))
    elif k == 'garage':
        for vt in ['compact', 'sedan', 'suv', 'van', 'bike', 'muscle', 'truck', 'sport']:
            sp = VTYPES[vt]
            items.append((T(sp['n']), sp['price'], (lambda vt=vt: self.buy_car(vt))))
    elif k == 'scrap':
        if P.in_car and P.in_car.vt not in ('police', 'tank'):
            v = P.in_car
            val = int(v.sp['price'] * 0.25 * v.hp / v.maxhp) + 150
            items.append((T("Sell current car"), -val, lambda: self.sell_car(val)))
        else:
            items.append((T("Bring a car to sell"), 0, lambda: None))
    elif k == 'safehouse':
        items.append((T("Save game"), 0, lambda: self.say(T("Game saved") if self.save_game() else T("Save failed"), 2)))
        items.append((T("Sleep until 8:00 (+heal)"), 0, lambda: (setattr(self, 'clock', 8 * 60.0), setattr(P, 'hp', P.maxhp), self.say(T("Good morning!"), 2))))
        items.append((T("Hide wanted level (sleep)"), 0, lambda: self.clear_wanted() if self.stars() == 0 else self.say(T("Cops are watching!"), 2)))
    elif k == 'stunt':
        items.append((T("Street Race"), 0, lambda: (setattr(self, 'state', 'play'), start_mission(SIDE_LIST[2], True))))
        items.append((T("Vigilante"), 0, lambda: (setattr(self, 'state', 'play'), start_mission(SIDE_LIST[0], True))))
    if not items:
        return
    self.shop = {'title': title, 'items': items, 'page': 0}
    self.state = 'shop'


def g_buy_simple(self, cost, fn, poi):
    if self.money < cost:
        self.say(T("Not enough money"), 2)
        return
    self.give_money(-cost)
    fn()
    self.say(T("Done"), 1.5)
    self.open_poi(poi)


def g_respray(self):
    v = self.player.in_car
    if v:
        v.hp = v.maxhp
        v.wreck = False
        v.color = random.choice(v.sp['cols'])
    self.clear_wanted()


def g_buy_car(self, vt):
    sp = VTYPES[vt]
    if self.money < sp['price']:
        self.say(T("Not enough money"), 2)
        return
    gs = [g for g in self.world.garages if g[0] == 'home']
    g = gs[0] if gs else None
    if g is None:
        return
    self.give_money(-sp['price'])
    if len(self.owned_cars) >= 3:
        self.owned_cars.pop(0)
    self.owned_cars.append(vt)
    v = Vehicle(vt, g[1] + rnd(-30, 60), g[2] + 40, 0.0, None, 'parked')
    v.owned = True
    self.cars.append(v)
    self.say(T("Bought ") + T(sp['n']) + T(" - delivered to your Safehouse"), 3.5)
    self.state = 'play'


def g_sell_car(self, val):
    P = self.player
    v = P.in_car
    if not v:
        return
    self.enter_exit()
    v.alive = False
    self.give_money(val)
    self.state = 'play'


Game.open_poi = g_open_poi
Game.buy_simple = g_buy_simple
Game.respray = g_respray
Game.buy_car = g_buy_car
Game.sell_car = g_sell_car


# ================================================================ UI WIDGETS
def btn(x, y, w, h, label, col=(48, 60, 96), size=24, enabled=True, sel=False):
    hit = False
    for (tx, ty) in G.ctl.downs:
        if x <= tx <= x + w and y <= ty <= y + h:
            hit = True
    c = col if enabled else (50, 50, 55)
    if sel:
        c = shade(c, 1.4)
    pygame.draw.rect(CV, c, (x, y, w, h), border_radius=8)
    pygame.draw.rect(CV, (200, 210, 240) if enabled else (90, 90, 95), (x, y, w, h), 2, border_radius=8)
    draw_text(label, x + w // 2, y + h // 2, size, WHITE if enabled else GRAY, 'mc')
    if hit and enabled:
        play('click', 0.6)
    return hit and enabled


def panel(x, y, w, h, alpha=210):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (12, 14, 24, alpha), (0, 0, w, h), border_radius=12)
    pygame.draw.rect(s, (120, 140, 200, 255), (0, 0, w, h), 2, border_radius=12)
    CV.blit(s, (x, y))


def set_lang(l):
    global LANG
    LANG = l
    G.settings['lang'] = l
    TEXT_CACHE.clear()


def draw_shop(self):
    self.draw_world_frozen()
    sh = self.shop
    panel(180, 40, 600, 460)
    draw_text(sh['title'], 480, 66, 34, YELLOW, 'mc')
    draw_text(T("Cash") + ": $%d" % self.money, 480, 98, 24, (120, 255, 120), 'mc')
    items = sh['items']
    per = 6
    page = sh['page']
    for i, (label, price, fn) in enumerate(items[page * per:(page + 1) * per]):
        y = 122 + i * 56
        txt = label + ("   $%d" % price if price > 0 else ("   +$%d" % -price if price < 0 else ""))
        if btn(210, y, 540, 48, txt, (46, 64, 110), 24, price <= 0 or self.money >= price or price < 0):
            fn()
            if self.state != 'shop':
                return
    if len(items) > per:
        if btn(210, 462, 80, 30, '<', size=22) and page > 0:
            sh['page'] -= 1
        if btn(670, 462, 80, 30, '>', size=22) and (page + 1) * per < len(items):
            sh['page'] += 1
    if btn(400, 458, 160, 38, T("Close"), (110, 40, 40)) or 'pause' in self.ctl.pressed:
        self.state = 'play'


def draw_menu(self):
    CV.fill((14, 16, 28))
    t = pygame.time.get_ticks() / 1000.0
    for k in range(14):
        x = (k * 97 + t * 30) % (LW + 100) - 50
        pygame.draw.rect(CV, (24, 28, 46), (x, 300 - (k * 37) % 160, 60, 300))
    draw_text("ALMATY CITY", 480, 100, 80, (250, 210, 60), 'mc')
    draw_text(T("Open-world crime sandbox"), 480, 160, 28, (200, 205, 230), 'mc')
    y = 210
    if self.has_save:
        if btn(330, y, 300, 52, T("Continue"), (50, 100, 60), 30):
            d = self.load_data()
            self.new_game(d)
            if d and 'settings' in d:
                self.settings.update(d['settings'])
        y += 62
    if btn(330, y, 300, 52, T("New Game"), (48, 60, 110), 30):
        self.new_game()
    y += 62
    if btn(330, y, 300, 52, T("Language: ") + ('RU' if LANG == 'ru' else 'EN'), (70, 50, 100), 26):
        set_lang('en' if LANG == 'ru' else 'ru')
    y += 62
    if btn(330, y, 300, 44, T("Sound: ") + ("%d%%" % int(self.settings['vol'] * 100)), (60, 60, 80), 24):
        self.settings['vol'] = (self.settings['vol'] + 0.25) % 1.25
        if SFX:
            SFX.volume = self.settings['vol']
    draw_text(T("Tip: set Pydroid orientation to Landscape"), 480, 520, 18, GRAY, 'mc')
    if self.ctl.sw < self.ctl.sh:
        draw_text(T("Rotate your phone to landscape!"), 480, 20, 26, (255, 120, 120), 'mc')


def draw_pause(self):
    self.draw_world_frozen()
    panel(300, 70, 360, 400)
    draw_text(T("PAUSED"), 480, 105, 40, YELLOW, 'mc')
    if btn(330, 140, 300, 46, T("Resume"), (50, 100, 60), 26) or 'pause' in self.ctl.pressed:
        self.state = 'play'
    if btn(330, 196, 300, 46, T("Phone"), (48, 60, 110), 26):
        self.state = 'phone'
        self.phone_tab = 0
    if btn(330, 252, 300, 46, T("Save game"), (48, 60, 110), 26):
        self.say(T("Game saved") if self.save_game() else T("Save failed"), 2)
        self.state = 'play'
    if btn(330, 308, 300, 46, T("Language: ") + ('RU' if LANG == 'ru' else 'EN'), (70, 50, 100), 24):
        set_lang('en' if LANG == 'ru' else 'ru')
    if btn(330, 364, 300, 46, T("Sound: ") + ("%d%%" % int(self.settings['vol'] * 100)), (60, 60, 80), 24):
        self.settings['vol'] = (self.settings['vol'] + 0.25) % 1.25
        if SFX:
            SFX.volume = self.settings['vol']
    if btn(330, 420, 300, 40, T("Main menu"), (110, 40, 40), 24):
        self.state = 'menu'


def draw_phone(self):
    self.draw_world_frozen()
    panel(110, 20, 740, 500)
    tabs = [T("Story"), T("Side jobs"), T("Stats"), T("Settings")]
    for i, tname in enumerate(tabs):
        if btn(130 + i * 180, 32, 170, 40, tname, (60, 70, 120), 24, sel=(i == self.phone_tab)):
            self.phone_tab = i
            self.menu_sel = 0
    if btn(790, 32, 50, 40, 'X', (120, 40, 40), 26) or 'pause' in self.ctl.pressed or 'phone' in self.ctl.pressed:
        self.state = 'play'
        return
    tab = self.phone_tab
    if tab == 0:
        for i, ent in enumerate(MISSION_LIST):
            col, y = i % 2, i // 2
            x, yy = 130 + col * 360, 86 + y * 70
            n, fn, rew, info = ent
            if i < self.done_missions:
                st, c = T("Done"), (40, 90, 50)
            elif i == self.done_missions:
                st, c = "$%d" % rew, (70, 90, 150)
            else:
                st, c = T("Locked"), (45, 45, 55)
            if btn(x, yy, 350, 62, "%d. %s  [%s]" % (i + 1, T(n), st), c, 22, i <= self.done_missions):
                start_mission(ent, i < self.done_missions)
            draw_text(T(info), x + 175, yy + 50, 16, (190, 190, 210), 'mc', False)
    elif tab == 1:
        for i, ent in enumerate(SIDE_LIST):
            n, fn, rew, info = ent
            if btn(130, 90 + i * 80, 710, 70, "%s   +$%d" % (T(n), rew), (60, 70, 120), 28):
                start_mission(ent, True)
            draw_text(T(info), 480, 90 + i * 80 + 55, 18, (190, 190, 210), 'mc', False)
    elif tab == 2:
        s = self.stats
        rows = [(T("Missions"), "%d/%d" % (self.done_missions, len(MISSION_LIST))), (T("Kills"), s['kills']),
                (T("Cops killed"), s['cops']), (T("Cars destroyed"), s['cars']), (T("Times wasted"), s['wasted']),
                (T("Times busted"), s['busted']), (T("Packages"), "%d/24" % len(self.pkg_found)),
                (T("Distance (km)"), "%.1f" % (s['dist'] / 1000.0)), (T("Play time (min)"), int(s['time'] / 60)),
                (T("Money earned"), "$%d" % s['earned']), (T("Money spent"), "$%d" % s['spent'])]
        for i, (a, b) in enumerate(rows):
            col, r = i % 2, i // 2
            draw_text(a, 140 + col * 360, 100 + r * 50, 26, (200, 205, 230))
            draw_text(str(b), 440 + col * 360, 100 + r * 50, 26, YELLOW, 'tr')
    else:
        if btn(130, 100, 340, 50, T("Language: ") + ('RU' if LANG == 'ru' else 'EN'), (70, 50, 100), 26):
            set_lang('en' if LANG == 'ru' else 'ru')
        if btn(130, 160, 340, 50, T("Sound: ") + ("%d%%" % int(self.settings['vol'] * 100)), (60, 60, 80), 26):
            self.settings['vol'] = (self.settings['vol'] + 0.25) % 1.25
            if SFX:
                SFX.volume = self.settings['vol']
        if btn(130, 220, 340, 50, T("Screen shake: ") + (T("On") if self.settings['shake'] else T("Off")), (60, 60, 80), 26):
            self.settings['shake'] = not self.settings['shake']
        if btn(130, 280, 340, 50, T("Show FPS: ") + (T("On") if self.settings['fps'] else T("Off")), (60, 60, 80), 26):
            self.settings['fps'] = not self.settings['fps']
        if btn(130, 340, 340, 50, T("Save game"), (48, 100, 60), 26):
            self.say(T("Game saved") if self.save_game() else T("Save failed"), 2)
        if btn(130, 400, 340, 50, T("Cancel mission"), (110, 40, 40), 26, self.mission is not None):
            self.mission.fail(T("Cancelled"))
        draw_text(T("Controls:"), 500, 100, 26, YELLOW)
        for i, l in enumerate([T("Left side: move (floating stick)"), T("FIRE: shoot / punch (auto-aim)"),
                               T("ACT: enter/exit car, use shops"), T("WPN: switch weapon, RUN: sprint"),
                               T("In car: arrows steer, GAS/BRK, HB drift"), T("Rob, race, fight - and stay alive!")]):
            draw_text(l, 500, 140 + i * 34, 20, (200, 205, 230))


def draw_map(self):
    self.draw_world_frozen()
    panel(40, 20, 880, 500)
    mw, mh = 800, int(800 * HT / float(WT))
    mh = min(mh, 460)
    mw = int(mh * WT / float(HT))
    ox, oy = 480 - mw // 2, 30
    img = pygame.transform.scale(self.world.mini, (mw, mh))
    CV.blit(img, (ox, oy))
    sx, sy = mw / float(WPX), mh / float(HPX)
    for poi in self.world.pois:
        col = {'ammu': (255, 120, 60), 'hospital': (255, 255, 255), 'spray': (255, 220, 60), 'garage': (100, 200, 255),
               'safehouse': (120, 255, 120), 'police': (80, 120, 255)}.get(poi['kind'], (220, 120, 255))
        pygame.draw.circle(CV, col, (int(ox + poi['x'] * sx), int(oy + poi['y'] * sy)), 4)
        pygame.draw.circle(CV, BLACK, (int(ox + poi['x'] * sx), int(oy + poi['y'] * sy)), 4, 1)
    for pk in self.pickups:
        if pk.kind == 'package' and pk.val not in self.pkg_found:
            pass
    if self.mission:
        for b in self.mission.blips:
            pygame.draw.circle(CV, b['col'], (int(ox + b['x'] * sx), int(oy + b['y'] * sy)), 6)
    px, py = self.player.pos()
    pygame.draw.circle(CV, WHITE, (int(ox + px * sx), int(oy + py * sy)), 6)
    pygame.draw.circle(CV, RED, (int(ox + px * sx), int(oy + py * sy)), 4)
    draw_text(T("MAP - tap to close"), 480, 506, 22, WHITE, 'mc')
    names = [('ind', 0.5, 0.82), ('down', 0.45, 0.4), ('sub', 0.2, 0.2), ('park', 0.37, 0.15), ('port', 0.95, 0.5),
             ('res', 0.7, 0.2), ('com', 0.7, 0.75)]
    for key, fx, fy in names:
        draw_text(T(DIST_NAMES[key]), ox + fx * mw, oy + fy * mh, 16, (255, 255, 200), 'mc')
    if self.ctl.downs or 'map' in self.ctl.pressed or 'pause' in self.ctl.pressed:
        self.state = 'play'


def draw_end(self):
    self.draw_world_frozen()
    wasted = self.state == 'dead'
    self.death_t += 1 / 60.0
    s = pygame.Surface((LW, LH), pygame.SRCALPHA)
    s.fill((0, 0, 0, int(min(160, self.death_t * 120))))
    CV.blit(s, (0, 0))
    draw_text(T("WASTED") if wasted else T("BUSTED"), 480, 240, 110,
              (200, 30, 30) if wasted else (70, 120, 240), 'mc')
    if self.death_t > 2.5 or (self.death_t > 1.0 and self.ctl.downs):
        self.respawn(not wasted)


Game.draw_shop = draw_shop
Game.draw_menu = draw_menu
Game.draw_pause = draw_pause
Game.draw_phone = draw_phone
Game.draw_map = draw_map
Game.draw_end = draw_end


# ================================================================ RENDER
LIGHT_CACHE = {}


def light_sprite(r):
    s = LIGHT_CACHE.get(r)
    if s is None:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -1):
            a = int(255 * (1 - i / float(r)) ** 0.8)
            pygame.draw.circle(s, (255, 255, 255, a), (r, r), i)
        LIGHT_CACHE[r] = s
    return s


def draw_prop(pr):
    px, py = int(pr.x - CAM[0]), int(pr.y - CAM[1])
    if px < -30 or px > LW + 30 or py < -30 or py > LH + 30:
        return
    k = pr.kind
    if k == 'lamp':
        pygame.draw.circle(CV, (50, 50, 55), (px, py), 4)
        pygame.draw.circle(CV, (230, 230, 170) if G.darkness() > 0.3 else (130, 130, 130), (px, py), 2)
    elif k == 'hydrant':
        pygame.draw.circle(CV, (200, 40, 40), (px, py), 4)
    elif k == 'bin':
        pygame.draw.circle(CV, (70, 90, 80), (px, py), 6)
        pygame.draw.circle(CV, (40, 55, 50), (px, py), 4)
    elif k == 'bench':
        pygame.draw.rect(CV, (120, 80, 40), (px - 9, py - 4, 18, 8))
    elif k == 'box':
        pygame.draw.rect(CV, (60, 100, 170), (px - 6, py - 6, 12, 12))
    elif k == 'crate':
        pygame.draw.rect(CV, pr.col, (px - 12, py - 12, 24, 24))
        pygame.draw.rect(CV, shade(pr.col, 0.6), (px - 12, py - 12, 24, 24), 2)
        pygame.draw.line(CV, shade(pr.col, 0.6), (px - 12, py - 12), (px + 12, py + 12), 2)


def draw_tree(pr):
    px, py = int(pr.x - CAM[0]), int(pr.y - CAM[1])
    if px < -40 or px > LW + 40 or py < -40 or py > LH + 40:
        return
    pygame.draw.circle(CV, (0, 0, 0), (px + 5, py + 5), 17) if False else None
    pygame.draw.circle(CV, (30, 90, 40), (px + 2, py + 3), 19)
    pygame.draw.circle(CV, (46, 130, 56), (px, py), 18)
    pygame.draw.circle(CV, (66, 160, 74), (px - 5, py - 5), 10)


def g_render_world(self):
    W = self.world
    W.draw(CAM, 0)
    cx, cy = CAM[0], CAM[1]
    for d in self.decals:
        x, y = d[0] - cx, d[1] - cy
        if -60 < x < LW + 60 and -60 < y < LH + 60:
            pygame.draw.circle(CV, d[3], (int(x), int(y)), int(d[2]))
    for s in self.skids:
        x, y = s[0] - cx, s[1] - cy
        if 0 < x < LW and 0 < y < LH:
            CV.fill((32, 32, 36), (int(x), int(y), 3, 3))
    trees = []
    for pr in W.props:
        if not pr.alive:
            continue
        if pr.kind == 'tree':
            trees.append(pr)
        else:
            draw_prop(pr)
    for poi in W.pois:
        x, y = poi['x'] - cx, poi['y'] - cy
        if -40 < x < LW + 40 and -40 < y < LH + 40:
            col = {'ammu': (255, 120, 60), 'hospital': (255, 90, 90), 'spray': (255, 220, 60), 'garage': (100, 200, 255),
                   'safehouse': (120, 255, 120), 'police': (90, 130, 255)}.get(poi['kind'], (220, 120, 255))
            r = 14 + 3 * math.sin(pygame.time.get_ticks() / 250.0)
            pygame.draw.circle(CV, col, (int(x), int(y)), int(r), 3)
            pygame.draw.circle(CV, shade(col, 0.5), (int(x), int(y)), 6)
            if dist(poi['x'], poi['y'], self.player.x, self.player.y) < 140:
                draw_text(T(poi['name']), x, y - 26, 18, col, 'mc')
    for pk in self.pickups:
        pk.draw()
    for p in self.peds:
        if p.dead:
            p.draw()
    for v in self.cars:
        v.draw()
    for p in self.peds:
        if not p.dead:
            p.draw()
    if not self.player.in_car:
        self.player.draw()
    for b in self.bullets:
        b.draw()
    for pt in self.parts:
        x, y = int(pt.x - cx), int(pt.y - cy)
        if x < -20 or x > LW + 20 or y < -20 or y > LH + 20:
            continue
        f = pt.life / pt.max
        if pt.kind == 'smoke':
            c = shade(pt.col, 0.6 + 0.4 * f)
            pygame.draw.circle(CV, c, (x, y), int(max(1, pt.size)))
        else:
            pygame.draw.circle(CV, pt.col, (x, y), int(max(1, pt.size * (0.5 + f * 0.5))))
    for t in trees:
        draw_tree(t)
    for h in self.helis:
        h.draw()
    self.draw_markers()
    self.draw_night()
    if self.rain > 0.05:
        self.draw_rain()
    for t in self.texts:
        draw_text(t[0], t[1] - cx, t[2] - cy, 22, t[4], 'mc')


def g_draw_markers(self):
    if not self.mission:
        return
    t = pygame.time.get_ticks() / 1000.0
    for b in self.mission.blips:
        x, y = b['x'] - CAM[0], b['y'] - CAM[1]
        col = b['col']
        if 0 <= x <= LW and 0 <= y <= LH:
            r = 16 + 4 * math.sin(t * 5)
            pygame.draw.circle(CV, col, (int(x), int(y)), int(r), 3)
            pygame.draw.polygon(CV, col, [(x, y - 30), (x - 8, y - 42), (x + 8, y - 42)])
            if b['label']:
                draw_text(b['label'], x, y - 54, 18, col, 'mc')
        else:
            cx_, cy_ = LW / 2, LH / 2
            a = math.atan2(y - cy_, x - cx_)
            ex = clamp(cx_ + math.cos(a) * 1000, 24, LW - 24)
            ey = clamp(cy_ + math.sin(a) * 1000, 70, LH - 24)
            ex, ey = clamp(ex, 24, LW - 24), clamp(ey, 70, LH - 24)
            pts = [(ex + math.cos(a) * 14, ey + math.sin(a) * 14),
                   (ex + math.cos(a + 2.5) * 12, ey + math.sin(a + 2.5) * 12),
                   (ex + math.cos(a - 2.5) * 12, ey + math.sin(a - 2.5) * 12)]
            pygame.draw.polygon(CV, col, pts)
            pygame.draw.polygon(CV, BLACK, pts, 1)


NIGHT_SURF = None


def g_draw_night(self):
    global NIGHT_SURF
    dk = self.darkness()
    dk = max(dk, self.rain * 0.25)
    if dk < 0.04:
        return
    sw, sh = LW // 4, LH // 4
    if NIGHT_SURF is None:
        NIGHT_SURF = pygame.Surface((sw, sh), pygame.SRCALPHA)
    NIGHT_SURF.fill((6, 10, 34, int(185 * dk)))
    cx, cy = CAM[0], CAM[1]
    sub = pygame.BLEND_RGBA_SUB
    P = self.player
    if dk > 0.3:
        for v in self.cars:
            if not v.alive or v.wreck:
                continue
            x, y = (v.x - cx) / 4.0, (v.y - cy) / 4.0
            if -30 < x < sw + 30 and -30 < y < sh + 30:
                c, s = math.cos(v.ang), math.sin(v.ang)
                sp = light_sprite(20)
                NIGHT_SURF.blit(sp, (x + c * 22 - 20, y + s * 22 - 20), special_flags=sub)
                sp2 = light_sprite(9)
                NIGHT_SURF.blit(sp2, (x + c * 8 - 9, y + s * 8 - 9), special_flags=sub)
        for pr in self.world.props:
            if pr.kind == 'lamp' and pr.alive:
                x, y = (pr.x - cx) / 4.0, (pr.y - cy) / 4.0
                if -30 < x < sw + 30 and -30 < y < sh + 30:
                    NIGHT_SURF.blit(light_sprite(16), (x - 16, y - 16), special_flags=sub)
        px, py = (P.x - cx) / 4.0, (P.y - cy) / 4.0
        NIGHT_SURF.blit(light_sprite(12), (px - 12, py - 12), special_flags=sub)
    CV.blit(pygame.transform.scale(NIGHT_SURF, (LW, LH)), (0, 0))


def g_draw_rain(self):
    t = pygame.time.get_ticks() / 1000.0
    n = int(90 * self.rain)
    for i in range(n):
        x = (i * 97 + t * 160) % (LW + 40) - 20
        y = (i * 53 + t * 900) % (LH + 40) - 20
        pygame.draw.line(CV, (170, 190, 230), (x, y), (x - 4, y + 12), 1)


def g_draw_world_frozen(self):
    if self.world:
        self.render_world()


# ================================================================ HUD
BTN_LABEL = {'fire': 'FIRE', 'act': 'ACT', 'sprint': 'RUN', 'left': '<', 'right': '>', 'gas': 'GAS', 'brake': 'BRK',
             'horn': 'HORN', 'hb': 'HB', 'pause': 'II', 'map': 'MAP', 'phone': 'TEL', 'radio': 'RAD', 'wpn': 'WPN'}
BTN_CACHE = {}


def btn_sprite(r, held):
    k = (r, held)
    s = BTN_CACHE.get(k)
    if s is None:
        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 255, 255, 120 if held else 50), (r + 2, r + 2), r)
        pygame.draw.circle(s, (255, 255, 255, 200), (r + 2, r + 2), r, 2)
        BTN_CACHE[k] = s
    return s


def g_draw_controls(self):
    c = self.ctl
    for name, (x, y, r) in c.layout.items():
        held = name in c.held
        CV.blit(btn_sprite(r, held), (x - r - 2, y - r - 2))
        lab = BTN_LABEL.get(name, name)
        if name == 'wpn':
            lab = T(WEAPONS[self.player.weapon]['n']).split(' ')[-1][:7]
        draw_text(lab, x, y, 18 if r < 40 else 24, WHITE, 'mc')
    f = c.stick_state()
    if f:
        pygame.draw.circle(CV, (255, 255, 255), (int(f['sx']), int(f['sy'])), 60, 2)
        dx, dy = f['x'] - f['sx'], f['y'] - f['sy']
        d = math.hypot(dx, dy)
        if d > 60:
            dx, dy = dx / d * 60, dy / d * 60
        pygame.draw.circle(CV, (255, 255, 255), (int(f['sx'] + dx), int(f['sy'] + dy)), 26)
    elif not c.layout is CAR_LAYOUT:
        pygame.draw.circle(CV, (255, 255, 255), (170, 400), 56, 1)
        draw_text(T("MOVE"), 170, 400, 18, (255, 255, 255), 'mc')


def g_draw_minimap(self):
    W = self.world
    mw, mh = 150, 112
    zx = 6.0
    px, py = self.player.pos()
    tw, th = mw / zx, mh / zx
    cx, cy = px / TILE, py / TILE
    rx, ry = int(cx - tw / 2), int(cy - th / 2)
    surf = pygame.Surface((int(tw) + 2, int(th) + 2))
    surf.fill((10, 10, 14))
    src = pygame.Rect(rx, ry, int(tw) + 2, int(th) + 2)
    clip = src.clip(pygame.Rect(0, 0, WT, HT))
    if clip.w > 0 and clip.h > 0:
        surf.blit(W.mini, (clip.x - rx, clip.y - ry), clip)
    surf = pygame.transform.scale(surf, (int((tw + 2) * zx), int((th + 2) * zx)))
    ox = int((cx - rx) * zx - mw / 2)
    oy = int((cy - ry) * zx - mh / 2)
    mm = pygame.Surface((mw, mh))
    mm.blit(surf, (-ox, -oy))

    def mp(x, y):
        return int((x / TILE - cx) * zx + mw / 2), int((y / TILE - cy) * zx + mh / 2)
    for poi in W.pois:
        x, y = mp(poi['x'], poi['y'])
        if 0 <= x < mw and 0 <= y < mh:
            pygame.draw.circle(mm, (255, 190, 60), (x, y), 3)
    if self.wanted > 0:
        for p in self.peds:
            if p.kind in ('cop', 'swat', 'soldier') and not p.dead:
                x, y = mp(p.x, p.y)
                if 0 <= x < mw and 0 <= y < mh:
                    pygame.draw.circle(mm, (80, 120, 255), (x, y), 2)
        for v in self.cars:
            if v.ai in ('police', 'army') and v.alive:
                x, y = mp(v.x, v.y)
                if 0 <= x < mw and 0 <= y < mh:
                    pygame.draw.rect(mm, (255, 60, 60) if int(pygame.time.get_ticks() / 250) % 2 else (60, 90, 255), (x - 2, y - 2, 5, 5))
    if self.mission:
        for b in self.mission.blips:
            x, y = mp(b['x'], b['y'])
            x, y = clamp(x, 4, mw - 4), clamp(y, 4, mh - 4)
            pygame.draw.circle(mm, b['col'], (x, y), 4)
            pygame.draw.circle(mm, BLACK, (x, y), 4, 1)
    a = self.player.ang
    pts = [(mw / 2 + math.cos(a) * 6, mh / 2 + math.sin(a) * 6), (mw / 2 + math.cos(a + 2.5) * 5, mh / 2 + math.sin(a + 2.5) * 5),
           (mw / 2 + math.cos(a - 2.5) * 5, mh / 2 + math.sin(a - 2.5) * 5)]
    pygame.draw.polygon(mm, WHITE, pts)
    CV.blit(mm, (10, 10))
    pygame.draw.rect(CV, (200, 210, 240), (10, 10, mw, mh), 2)


def bar(x, y, w, h, frac, col, bg=(30, 30, 36)):
    pygame.draw.rect(CV, bg, (x, y, w, h))
    pygame.draw.rect(CV, col, (x, y, int(w * clamp(frac, 0, 1)), h))
    pygame.draw.rect(CV, (220, 220, 230), (x, y, w, h), 1)


def g_draw_hud(self):
    P = self.player
    self.draw_minimap()
    bar(10, 128, 150, 12, P.hp / float(P.maxhp), (210, 50, 50))
    if P.armor > 0:
        bar(10, 144, 150, 8, P.armor / 100.0, (80, 140, 240))
    if not P.in_car and self.stamina < 99:
        bar(10, 156, 150, 5, self.stamina / 100.0, (240, 220, 80))
    if self.hp_flash > 0:
        s = pygame.Surface((LW, LH), pygame.SRCALPHA)
        s.fill((200, 0, 0, 60))
        CV.blit(s, (0, 0))
    # money / stars / weapon (right column below buttons)
    draw_text("$%d" % self.money, LW - 14, 62, 34, (120, 255, 120), 'tr')
    st = self.stars()
    blink = self.seen and int(pygame.time.get_ticks() / 250) % 2 == 0
    for i in range(6):
        on = i < st
        col = (255, 220, 60) if on else (70, 70, 80)
        if on and blink:
            col = (255, 255, 255)
        cx, cy = LW - 24 - i * 26, 100
        pts = []
        for k in range(10):
            r = 11 if k % 2 == 0 else 5
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        pygame.draw.polygon(CV, col, pts)
        pygame.draw.polygon(CV, BLACK, pts, 1)
    if P.in_car:
        v = P.in_car
        draw_text("%s  %d km/h" % (T(v.sp['n']), int(v.speed * 0.28)), LW - 14, 124, 22, WHITE, 'tr')
        bar(LW - 154, 150, 140, 8, v.hp / v.maxhp, (220, 160, 40))
        draw_text(RADIO[self.radio], LW - 14, 164, 18, (170, 200, 255), 'tr')
    else:
        w = WEAPONS[P.weapon]
        a = '' if w.get('melee') else '  %d' % self.weapons.get(P.weapon, 0)
        draw_text(T(w['n']) + a, LW - 14, 124, 22, WHITE, 'tr')
    # clock
    hh, mm_ = int(self.clock // 60), int(self.clock % 60)
    draw_text("%02d:%02d" % (hh, mm_), 170, 14, 22, WHITE)
    if self.settings.get('fps'):
        draw_text("%d fps" % self.fps, 170, 36, 18, (200, 200, 120))
    # objective
    M = self.mission
    if M:
        panel(300, 6, 360, 52, 170)
        draw_text(M.obj[:52], 480, 22, 19, WHITE, 'mc')
        tx = ''
        if M.timer is not None:
            tx += "%d:%02d" % (int(M.timer) // 60, int(M.timer) % 60)
        if M.sub:
            tx += "   " + M.sub
        if tx:
            draw_text(tx, 480, 44, 22, YELLOW, 'mc')
    # district
    if self.dist_t > 0:
        a = clamp(self.dist_t, 0, 1)
        draw_text(T(self.district), 480, 80 if not M else 78, 30, (255, 255, 255), 'mc')
    # messages
    for i, m in enumerate(reversed(self.msgs)):
        draw_text(m[0], 480, 500 - i * 24, 22, WHITE, 'mc')
    # poi prompt
    poi = self.poi_near(bool(P.in_car))
    if poi:
        draw_text(T("ACT: ") + T(poi['name']), 480, 462, 24, YELLOW, 'mc')
    elif not P.in_car:
        for v in self.cars:
            if v.alive and not v.wreck and dist(P.x, P.y, v.x, v.y) < 56:
                draw_text(T("ACT: enter ") + T(v.sp['n']), 480, 462, 22, (220, 230, 255), 'mc')
                break
    if self.busted_t > 0:
        bar(380, 420, 200, 10, self.busted_t / 1.8, (80, 120, 240))
    b = getattr(self, 'banner', None)
    if b and b[1] > 0:
        draw_text(b[0], 480, 200, 70, b[2], 'mc')
        self.banner = (b[0], b[1] - 1 / 60.0, b[2])
    self.draw_controls()


Game.render_world = g_render_world
Game.draw_markers = g_draw_markers
Game.draw_night = g_draw_night
Game.draw_rain = g_draw_rain
Game.draw_world_frozen = g_draw_world_frozen
Game.draw_controls = g_draw_controls
Game.draw_minimap = g_draw_minimap
Game.draw_hud = g_draw_hud


# ================================================================ DISPATCH
def g_update(self, dt):
    self.dt = dt
    if self.state == 'play':
        self.update_play(dt)
    self.ctl.menu_mode = self.state != 'play'


def g_draw(self):
    st = self.state
    if st == 'menu':
        self.draw_menu()
    elif st == 'play':
        self.render_world()
        self.draw_hud()
    elif st == 'pause':
        self.draw_pause()
    elif st == 'phone':
        self.draw_phone()
    elif st == 'map':
        self.draw_map()
    elif st == 'shop':
        self.draw_shop()
    elif st in ('dead', 'busted'):
        self.draw_end()


Game.update = g_update
Game.draw = g_draw


# ================================================================ RUSSIAN
RU.update({
    ' - delivered to your Safehouse': ' - доставлена в твоё убежище',
    '8 checkpoints in a sports car.': '8 точек на спорткаре.',
    'ACT: ': 'ДЕЙСТВ: ',
    'ACT: enter ': 'ДЕЙСТВ: сесть в ',
    'ACT: enter/exit car, use shops': 'ACT: сесть/выйти из машины, магазины',
    'All packages found! +$10000': 'Все посылки найдены! +$10000',
    'Ambulance': 'Скорая', 'Ambush! Gang cars incoming!': 'Засада! Машины банды!',
    'Ammo: ': 'Патроны: ', 'Ammu-Nation': 'Оружейный', 'Army Tank': 'Танк', 'Assault Rifle': 'Автомат',
    'BUSTED': 'ПОЙМАН', 'Bail paid: $%d, weapons confiscated': 'Залог $%d, оружие изъято',
    'Bank': 'Банк', 'Bank Job': 'Налёт на банк', 'Baseball Bat': 'Бита',
    'Beat up a gangster with a bat.': 'Побей бандита битой.', 'Big score, big heat.': 'Большой куш, большой розыск.',
    'Blow up all 6 red cars in Downtown (Rocket Launcher given)': 'Взорви 6 красных машин в центре (дан гранатомёт)',
    'Body armor': 'Бронежилет', 'Bought ': 'Куплено: ', 'Bribe an officer (clears wanted)': 'Взятка копу (снимает розыск)',
    'Bring a car to sell': 'Приведи машину на продажу', 'Burger (+40 HP)': 'Бургер (+40 HP)', 'Busted': 'Поймали',
    'Buy ': 'Купить ', 'Cancel mission': 'Отменить миссию', 'Cancelled': 'Отменено', 'Car Dealer': 'Автосалон',
    'Carjacked!': 'Угон!', 'Cars destroyed': 'Машин уничтожено', 'Cash': 'Наличные',
    'Catch and destroy the yellow sports car!': 'Догони и уничтожь жёлтый спорткар!',
    'Central Park': 'Центральный парк', 'Checkpoint': 'Точка', 'Checkpoint %d/%d': 'Точка %d/%d',
    'City Bus': 'Автобус', 'Close': 'Закрыть', 'Compact': 'Компакт', 'Continue': 'Продолжить',
    'Controls:': 'Управление:', 'Cops are watching!': 'Копы следят!',
    'Cops everywhere! Reach the Safehouse!': 'Копы повсюду! Доберись до убежища!', 'Cops killed': 'Копов убито',
    'Debt Collector': 'Выбивание долга', 'Deliver a truck through an ambush.': 'Довези грузовик через засаду.',
    "Deliver the parcel fast - don't wreck the van!": 'Быстро доставь посылку, не разбей фургон!',
    'Deliver the truck to the Harbour - watch for ambush!': 'Доставь грузовик в порт - берегись засады!',
    'Destination': 'Пункт назначения', 'Destroy a fleeing car.': 'Уничтожь убегающую машину.',
    'Distance (km)': 'Пройдено (км)', 'Done': 'Готово', 'Downtown': 'Даунтаун', 'Drive a car in first!': 'Сначала заезжай на машине!',
    'Drive to Ammu-Nation': 'Езжай к оружейному', 'Drop-off': 'Место доставки',
    'Earn money as a cabbie.': 'Заработай деньги таксистом.', 'Escape to the Safehouse': 'Скройся в убежище',
    'FIRE: shoot / punch (auto-aim)': 'FIRE: стрелять / бить (автонаведение)',
    'Final showdown at the Stadium.': 'Финальная разборка на стадионе.',
    "Find and beat up 'Fat Tony' (red marker)": "Найди и побей 'Толстяка Тони' (красная метка)",
    'Finish the current mission first': 'Сначала закончи текущую миссию', 'First Wheels': 'Первые колёса',
    'Fists': 'Кулаки', 'Game saved': 'Игра сохранена', 'Gang War': 'Война банд',
    'Get in the delivery van': 'Сядь в фургон', 'Get in the race car': 'Сядь в гоночную машину',
    'Get in the taxi': 'Сядь в такси', 'Get in the truck': 'Сядь в грузовик',
    'Get out (ACT) and buy a Pistol inside the shop (ACT near the door)': 'Выйди (ACT) и купи пистолет в магазине (ACT у двери)',
    'Go to the Downtown Bank': 'Езжай к банку в центре', 'Go to the Mall': 'Иди в торговый центр',
    'Go to the Stadium': 'Езжай на стадион', 'Good morning!': 'Доброе утро!',
    'Got $3000! Cops are coming!': 'Взял $3000! Копы едут!', 'Grab the cash from the vault': 'Забери деньги из хранилища',
    'Green Hills': 'Зелёные холмы', 'Grenade': 'Граната', 'Harbour': 'Порт', 'Harbour Deal': 'Сделка в порту',
    'Health restored': 'Здоровье восстановлено', 'Hidden package %d/24 (+$200)': 'Тайник %d/24 (+$200)',
    'Hide wanted level (sleep)': 'Переждать розыск', 'Hit & Run': 'Погоня', 'Hospital': 'Больница',
    'Hospital bill: $%d': 'Счёт за лечение: $%d', 'Hunt 5 criminals.': 'Выследи 5 преступников.',
    'In car: arrows steer, GAS/BRK, HB drift': 'В машине: стрелки руль, GAS газ, BRK тормоз, HB дрифт',
    'Industrial Zone': 'Промзона', 'Kill the Boss and his bodyguards': 'Убей босса и его охрану',
    'Kill the guards': 'Убей охрану', 'Kills': 'Убийства', 'Language: ': 'Язык: ',
    'Left side: move (floating stick)': 'Слева: движение (плавающий стик)', 'Locked': 'Закрыто',
    "Lose the cops! (or use Pay'n'Spray)": "Оторвись от копов! (или Pay'n'Spray)",
    'MAP - tap to close': 'КАРТА - нажми, чтобы закрыть', 'MISSION FAILED': 'МИССИЯ ПРОВАЛЕНА',
    'MISSION FAILED: ': 'МИССИЯ ПРОВАЛЕНА: ', 'MISSION PASSED': 'МИССИЯ ВЫПОЛНЕНА', 'MOVE': 'ХОД',
    'Main menu': 'Главное меню', 'Mall': 'Торговый центр', 'Mall (armor & food)': 'Торговый центр (броня и еда)',
    'Mall Heist': 'Ограбление ТЦ', 'Market District': 'Рынок', 'Micro SMG': 'Микро-СМГ', 'Mission: ': 'Миссия: ',
    'Missions': 'Миссии', 'Money earned': 'Заработано', 'Money spent': 'Потрачено', 'Motorbike': 'Мотоцикл',
    'Muscle Car': 'Масл-кар', 'New Game': 'Новая игра', 'Not enough money': 'Не хватает денег', 'Off': 'Выкл',
    'Old Town': 'Старый город', 'On': 'Вкл', 'Open-world crime sandbox': 'Криминальная песочница с открытым миром',
    'Out of ammo': 'Нет патронов', 'PAUSED': 'ПАУЗА', 'Packages': 'Посылки', 'Parcel Express': 'Срочная доставка',
    'Passenger': 'Пассажир', "Pay'n'Spray": 'Покраска', 'Phone': 'Телефон',
    'Pick up passenger %d/3': 'Забери пассажира %d/3', 'Picked up: ': 'Подобрано: ', 'Pistol': 'Пистолет',
    'Play time (min)': 'Время игры (мин)', 'Police Cruiser': 'Полицейская', 'Police HQ': 'Полицейский участок',
    'Press the phone icon for missions & menu': 'Значок TEL: миссии и меню',
    'Quick target practice.': 'Быстрая стрельба по мишеням.', 'ROBBERY!': 'ОГРАБЛЕНИЕ!',
    'RPG fun in Downtown.': 'Гранатомёт в центре города.', 'Race car': 'Гоночная', 'Race through the city.': 'Гонка по городу.',
    'Radio: ': 'Радио: ', 'Respray & repair (clears wanted)': 'Покраска и ремонт (снимает розыск)', 'Resume': 'Продолжить',
    'Rob it, then lose the cops.': 'Ограбь и оторвись от копов.', 'Rob, race, fight - and stay alive!': 'Грабь, гоняй, дерись - и выживай!',
    'Rocket Launcher': 'Гранатомёт', 'Rocket Rampage': 'Ракетный шторм', 'Rotate your phone to landscape!': 'Поверни телефон горизонтально!',
    'SUV': 'Внедорожник', 'Safehouse': 'Убежище', 'Save failed': 'Не удалось сохранить', 'Save game': 'Сохранить игру',
    'Scrapyard (sell cars)': 'Свалка (продажа машин)', 'Screen shake: ': 'Тряска экрана: ', 'Sedan': 'Седан',
    'Sell current car': 'Продать эту машину', 'Settings': 'Настройки', 'Shooting Range': 'Тир',
    'Shooting range: kill all dummies in 45 s': 'Тир: убери все мишени за 45 с', 'Shotgun': 'Дробовик',
    'Show FPS: ': 'Показать FPS: ', 'Side jobs': 'Подработки', 'Sleep until 8:00 (+heal)': 'Спать до 8:00 (+лечение)',
    'Sound: ': 'Звук: ', 'Sport Coupe': 'Спорт-купе', 'Stadium': 'Стадион', 'Start Shooting Range': 'Начать стрельбу в тире',
    'Stats': 'Статистика', 'Steal a car (stand next to one, press ACT)': 'Угони машину (подойди и нажми ACT)',
    'Steal a car, get a gun.': 'Угони машину, добудь ствол.', 'Story': 'Сюжет', 'Street Race': 'Уличная гонка',
    'Stunt Arena': 'Арена трюков', 'Take the passenger to the destination': 'Отвези пассажира',
    'Target': 'Цель', 'Taxi': 'Такси', 'Taxi Driver': 'Таксист', 'Taxi Fares': 'Такси-заказы',
    'Taxi: pick up passengers! (phone > Side jobs)': 'Такси: возить пассажиров! (телефон > Подработки)',
    'The Boss': 'Босс', 'The truck was destroyed': 'Грузовик уничтожен', 'The van is wrecked': 'Фургон разбит',
    'The vehicle was destroyed': 'Машина уничтожена', 'Three taxi fares.': 'Три поездки на такси.',
    'Time Trial': 'Заезд на время', 'Time is up': 'Время вышло', 'Time-limited delivery.': 'Доставка на время.',
    'Times busted': 'Раз пойман', 'Times wasted': 'Раз погиб', 'Tip: set Pydroid orientation to Landscape': 'Совет: в Pydroid включи горизонтальную ориентацию',
    'Treatment (full health)': 'Лечение (полное здоровье)', 'Truck': 'Грузовик', 'Van': 'Фургон', 'Vault': 'Хранилище',
    'Vigilante': 'Мститель', 'Vigilante: hunt 5 criminals': 'Мститель: выследи 5 преступников', 'WASTED': 'ТЫ ПОГИБ',
    'WPN: switch weapon, RUN: sprint': 'WPN: смена оружия, RUN: бег', 'Wanted level lost': 'Розыск снят',
    'Welcome to Almaty City!': 'Добро пожаловать в Алматы Сити!', 'Wipe out a gang.': 'Уничтожь банду.',
    'Wipe out the gang near the Scrapyard': 'Уничтожь банду у свалки', 'You died': 'Ты погиб',
    'You left the area': 'Ты покинул зону', 'You ruled Almaty City! Keep playing freely.': 'Ты покорил Алматы Сити! Играй свободно.',
    'ALMATY CITY': 'ALMATY CITY',
})


# ================================================================ MAIN
def main():
    global CV, SFX, LANG, FONT_PATH
    pygame.init()
    on_android = ('ANDROID_ROOT' in os.environ and 'ANDROID_DATA' in os.environ) or hasattr(sys, 'getandroidapilevel')
    screen = None
    try:
        if on_android:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode((LW, LH), pygame.RESIZABLE)
    except Exception:
        screen = pygame.display.set_mode((LW, LH))
    pygame.display.set_caption("Almaty City")
    CV = pygame.Surface((LW, LH)).convert()
    # font with Cyrillic support
    try:
        path = pygame.font.match_font('dejavusans,notosans,roboto,droidsans,arial,liberationsans,freesans')
    except Exception:
        path = None
    FONT_PATH = None
    TEXT_CACHE.clear()
    FONTS.clear()
    if font_has_cyrillic():
        LANG = 'ru'
    elif path:
        FONT_PATH = path
        FONTS.clear()
        TEXT_CACHE.clear()
        LANG = 'ru' if font_has_cyrillic() else 'en'
    else:
        LANG = 'en'
    SFX = Sfx()
    game = Game(screen)
    game.settings['lang'] = LANG
    ctl = game.ctl
    clock = pygame.time.Clock()
    sw, sh = screen.get_size()
    ctl.set_screen(sw, sh)
    dest = None
    dest_size = None
    running = True
    fps_acc, fps_n = 0.0, 0
    back_key = getattr(pygame, 'K_AC_BACK', -999)
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        fps_acc += dt
        fps_n += 1
        if fps_acc > 0.5:
            game.fps = fps_n / fps_acc
            fps_acc, fps_n = 0.0, 0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.VIDEORESIZE:
                try:
                    screen = pygame.display.get_surface()
                except Exception:
                    pass
            elif e.type in (pygame.WINDOWFOCUSLOST,) and game.state == 'play':
                game.state = 'pause'
            elif e.type == pygame.KEYDOWN and e.key == back_key:
                ctl.pressed.add('pause')
            else:
                ctl.handle(e)
        screen = pygame.display.get_surface() or screen
        sw, sh = screen.get_size()
        if (sw, sh) != (ctl.sw, ctl.sh):
            ctl.set_screen(sw, sh)
        ctl.poll()
        if game.state == 'menu' and game.world is None and ctl.keys and pygame.K_ESCAPE in ctl.keys:
            running = False
        game.update(dt)
        CV.fill((0, 0, 0))
        game.draw()
        # scale to the screen (letterboxed)
        dw, dh = int(LW * ctl.scale), int(LH * ctl.scale)
        if dest is None or dest_size != (dw, dh, sw, sh):
            screen.fill((0, 0, 0))
            dest = screen.subsurface(pygame.Rect(int(ctl.ox), int(ctl.oy), dw, dh))
            dest_size = (dw, dh, sw, sh)
        if (dw, dh) == (LW, LH):
            dest.blit(CV, (0, 0))
        else:
            pygame.transform.scale(CV, (dw, dh), dest)
        pygame.display.flip()
        ctl.end_frame()
    pygame.quit()


if __name__ == '__main__':
    main()
