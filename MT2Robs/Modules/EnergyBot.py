
import sys
_chr = chr

import __builtin__ as buildin
try:
	import time
except:
	pass

def HasArguments(module, attrlist):
    for attr in attrlist:
        if not buildin.hasattr(module, attr):
            return False
    return True

for modulename, module in iter(sys.modules.items()):
    if HasArguments(module, ['clock']):time = module
    if HasArguments(module, ['GetPlayTime']):player = module
    if HasArguments(module, ['GetNameByVID']):chr = module
    if HasArguments(module, ['DirectEnter']):net = module
    if HasArguments(module, ['SetCameraMaxDistance']):app = module
    if HasArguments(module, ['ArrangeShowingChat']):chat = module
    if HasArguments(module, ['GetCurrentMapName']):background = module
    if HasArguments(module, ['GetItemName', 'SelectItem']):item = module
    if HasArguments(module, ['SelectAnswer']):event = module
    if HasArguments(module, ['IsPrivateShop']):shop = module
    if HasArguments(module, ['ScriptWindow']):ui = module
    if HasArguments(module, ['factorial']):math = module
    if HasArguments(module, ['uniform']):random = module

try:
    import random
except:
    pass

# FALLBACK RANDOM: este cliente nao tem o modulo random na lib e o scan de
# sys.modules pode nao o encontrar a hora da importacao (log: NameError
# 'random is not defined' -> WASD morto, jitter morto, rotas random mortas).
# Resolve LAZY (re-tenta sempre que e usado; quando o jogo carregar o dele
# passa a usa-lo) e entretanto usa um LCG proprio.
_lcg_seed = [2463534242]
_rnd_cache = [None]

def _rnd():
    if _rnd_cache[0] is not None:
        return _rnd_cache[0]
    for _mn in list(sys.modules.keys()):
        _m = sys.modules.get(_mn)
        try:
            if _m is not None and buildin.hasattr(_m, 'uniform') and buildin.hasattr(_m, 'choice'):
                _rnd_cache[0] = _m
                return _m
        except:
            pass
    return None

def _fallback_uniform(a, b):
    _lcg_seed[0] = (1103515245 * _lcg_seed[0] + 12345) & 0x7fffffff
    return a + (b - a) * (_lcg_seed[0] / 2147483647.0)

def _rnd_uniform(a, b):
    r = _rnd()
    if r is not None:
        try:
            return r.uniform(a, b)
        except:
            pass
    return _fallback_uniform(a, b)

def _rnd_choice(seq):
    try:
        if not seq:
            return None
    except:
        return None
    r = _rnd()
    if r is not None:
        try:
            return r.choice(seq)
        except:
            pass
    return seq[int(_fallback_uniform(0, len(seq))) % len(seq)]

import UIComponents, eXLib
from MT2Robs.Modules import OpenLib, Movement
try:
    import PathRunner
except:
    PathRunner = None

try:
    import ZoneGuard
except:
    ZoneGuard = None

# ===== TELEMETRY (dedicated energy log on tr-TR) =====
ENERGY_LOG = eXLib.PATH + 'energy_telemetry.txt'
_tel = {'cycle_start': 0.0, 'buy_start': 0.0, 'walk_alch': 0.0,
        'give': 0.0, 'walk_back': 0.0, 'click_dist': 0,
        'knives': 0, 'stuck': 0, 'dialogs': 0, 'errors': 0}


def _tel_log(msg):
    try:
        from datetime import datetime
        stamp = datetime.now().strftime('%H:%M:%S')
        f = open(ENERGY_LOG, 'a')
        f.write('[%s] %s\n' % (stamp, msg))
        f.close()
    except:
        pass


def _tel_summary(cycle_n):
    try:
        total = OpenLib.Monotonic() - _tel['cycle_start']
        _tel_log('=== CICLO %d: %.0fs | facas=%d | dist=%d | stuck=%d | dlg=%d | err=%d ===' % (
            cycle_n, total, _tel['knives'], _tel['click_dist'], _tel['stuck'], _tel['dialogs'], _tel['errors']))
        _tel['knives'] = 0
        _tel['stuck'] = 0
        _tel['dialogs'] = 0
        _tel['errors'] = 0
    except:
        pass
# ===== END TELEMETRY =====

# ===== MULTI-ROUTE LIBRARY (tr-TR) =====
# Cada caminhada vendedor<->alquimista e GRAVADA (waypoints com distancia
# minima). As rotas ficam em ficheiro e sao depois usadas AO ACASO com jitter
# +-80px -- nunca o mesmo caminho duas vezes.
ROUTES_FILE = eXLib.PATH + 'MT2Robs/Saves/energy_routes.txt'
# SEM LIMITE de rotas: quantas mais melhor (o dedupe abaixo evita guardar
# caminhos repetidos; rotas mesmo diferentes ficam todas guardadas)
ROUTE_WP_MIN_DIST = 150      # grava um waypoint pelo menos a esta distancia
ROUTE_TELEPORT_JUMP = 4000   # salto maior mid-route = teleport -> descartar
ROUTE_PLAY_ARRIVE = 220      # waypoint considerado alcancado neste raio
ROUTE_JITTER = 80            # offset aleatorio aplicado em cada replay
ROUTE_START_MAX = 2500       # so usa rota cujo inicio esteja perto de nos
ROUTE_MIN_WPS = 3            # gravacoes mais curtas sao ruido

_ROUTES = []                 # [{'map':str,'type':'to_alch'|'to_weapon','wps':[(x,y),..]}]


def _routes_load():
    global _ROUTES
    _ROUTES = []
    try:
        for line in open(ROUTES_FILE, 'r'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|')
            if len(parts) != 3:
                continue
            mapname, rtype, coords = parts[0].strip(), parts[1].strip(), parts[2]
            wps = []
            for p in coords.split():
                xy = p.split(',')
                if len(xy) == 2:
                    try:
                        wps.append((float(xy[0]), float(xy[1])))
                    except:
                        pass
            if wps:
                _ROUTES.append({'map': mapname, 'type': rtype, 'wps': wps})
    except:
        pass


def _routes_save():
    try:
        f = open(ROUTES_FILE, 'w')
        f.write('# map|type|x1,y1 x2,y2 ...\n')
        for r in _ROUTES:
            cs = ' '.join('%d,%d' % (int(x), int(y)) for x, y in r['wps'])
            f.write('%s|%s|%s\n' % (r['map'], r['type'], cs))
        f.close()
    except:
        pass


def _routes_count(mapname):
    n = 0
    for r in _ROUTES:
        if r['map'] == mapname:
            n += 1
    return n


def _routes_get(mapname, rtype):
    out = []
    for r in _ROUTES:
        if r['map'] == mapname and r['type'] == rtype:
            out.append(r)
    return out


def _routes_too_similar(a, b):
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if OpenLib.dist(a[i][0], a[i][1], b[i][0], b[i][1]) > 160.0:
            return False
    return True


def _routes_add(mapname, rtype, wps):
    if len(wps) < ROUTE_MIN_WPS:
        return False
    for r in _routes_get(mapname, rtype):
        if _routes_too_similar(wps, r['wps']):
            return False
    _ROUTES.append({'map': mapname, 'type': rtype,
                    'wps': [(int(x), int(y)) for x, y in wps]})
    _routes_save()
    return True


_routes_load()
# ===== END ROUTE LIBRARY =====

# --- stuck recovery: spam WASD -> funcao ESC que solta a personagem ---
DIK_W, DIK_A, DIK_S, DIK_D = 17, 30, 31, 32
DIK_UP, DIK_LEFT, DIK_RIGHT = 200, 203, 205   # setas tambem (DOWN e tecla stealth)
WASD_KEYS = (DIK_W, DIK_A, DIK_S, DIK_D, DIK_UP, DIK_LEFT, DIK_RIGHT)
STUCK_TICKS = 5           # ~2s sem andar -> preso
WASD_ROUNDS = 8           # rondas WASD+rota antes do ESC livre (mais tentativas de escapar)
ESC_CMDS = ('/restart', '/restart_town', '/restart_here', '/unstuck', '/escape')
ESC_CMD_TICKS = 12        # 4.8s entre comandos candidatos
ESC_WAIT_TICKS = 45       # espera maxima apos o ultimo comando
ESC_TELEPORT_DIST = 2500  # salto de posicao maior que isto = personagem solta
ESC_MAX_PER_SESSION = 10  # teto de seguranca (deadlock real -> parar)




def _ub_log(text):
    try:
        from datetime import datetime
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f = open(eXLib.PATH + 'mt2robs.txt', 'a')
        f.write('[%s] %s\n' % (stamp, text))
        f.close()
    except:
        pass


# =============================================================================
# EnergyBot -- YOU walk, the bot acts when you arrive:
#   * "Auto-buy knives" ON  + Start: waits until YOU are at the weapon dealer,
#     then opens the shop and buys the 15k knives until the inventory is full.
#     Then waits for YOU to walk to the alchemist.
#   * On arrival near the alchemist: short CLIENT-SIDE walk to a RANDOM spot near
#     the NPC (never the same standing point), then exchanges everything, human-paced.
#   * Toggle OFF + Start: exchange-only (same wait + random positioning).
# All movement between NPCs is yours; the only packets are exactly what a manual
# player sends (NPC click, dialog answer, buy, give). Debug -> mt2robs.txt.
# =============================================================================

# Cheap gear the alchemist converts into energy fragments.
ALL_GIVABLE_ITEMS = [
    1040, 1041, 1042, 1043, 1044,
    12260, 12261, 12262, 12263, 12264,
    12390, 12391, 12392, 12393, 12394,
    12530, 12531, 12532, 12533, 12534,
    12670, 12671, 12672, 12673, 12674,
    21530, 21531, 21532, 21533, 21534,
]

WEAPON_RACE    = 9001     # weapon dealer (sells the givable gear)
ALCHEMIST_RACE = 20001    # alchemist (converts gear -> energy fragments)
BUY_SHOP_SLOT  = 4        # shop slot holding the givable item at the weapon dealer
KNIFE_PRICE    = 15000    # yang per knife (informational + money floor)

# Per-map NPC world positions, in GetMainCharacterPosition() world units.
NPC_POSITIONS = {
    'metin2_map_a1': {'weapon': (60100, 56100), 'alchemist': (62200, 51600)},
    'metin2_map_b1': {'weapon': (67700, 65600), 'alchemist': (65900, 72800)},
    'metin2_map_c1': {'weapon': (42800, 61200), 'alchemist': (29700, 81500)},
}

NEAR_DIST      = 1800     # YOU are "at the NPC" when closer than this
NPC_CLICK_DIST = 300      # only CLICK the NPC when THIS close (colado).
NPC_SAVE_FILE = eXLib.PATH + 'MT2Robs/Saves/npc_positions.txt'
ALCH_GIVE_DIST = 600      # the alchemist EXCHANGE works from further away
                          # (SendGiveItemPacket has a bigger server range than
                          # dialog clicks, and the NPC is solid at <300px).
                          # Clicking from far = dialog opens from far =
                          # 3-button quest dialog lingers + crash risk.
ALCH_STAND_MIN = 480      # parar MAIS LONGE do alquimista (480-580px): os
ALCH_STAND_MAX = 580      # outros jogadores deixam de abrir trade/misclique
ALCH_GIVE_TRY   = 1000    # TENTAR a troca ate desta distancia (o pedido de
                          # troca tem alcance maior no servidor; se recusar,
                          # o GIVE aproxima-se sozinho ao anel 480-580)
POS_RMIN, POS_RMAX = 250, 420   # random standing spot: distance from the alchemist
POS_ARRIVE     = 110      # close enough to the random spot
POS_MAX_TRIES  = 6        # re-roll the random spot this many times if no path

# --- humanized GIVE pacing (exchange) ---
GIVE_DELAY_MIN = 1.0
GIVE_DELAY_MAX = 2.0
PAUSE_CHANCE   = 0.08
PAUSE_MIN      = 4.0
PAUSE_MAX      = 7.0
FIRST_DELAY_MIN = 1.5   # pause after positioning before the first give
FIRST_DELAY_MAX = 3.5

# --- humanized BUY pacing (knives) ---
BUY_DELAY_MIN  = 1.4
BUY_DELAY_MAX  = 2.8
BUY_PAUSE_CHANCE = 0.10
BUY_PAUSE_MIN  = 4.0
BUY_PAUSE_MAX  = 8.0
BUY_STALL      = 12.0   # no NEW item this long while buying -> inventory full
SHOP_RETRY_MAX = 6
DIALOG_WAIT_MAX = 25
DIK_LALT = 56
DIK_G = 34   # wait up to 10s (25 * 0.4s) for the dialog

# state machine
(S_STOP, S_WAIT_WEAPON, S_OPEN_SHOP, S_WAIT_DIALOG, S_BUY,
 S_WAIT_ALCH, S_POSITION, S_GIVE, S_WAIT_HAMMER, S_GOTO_ALCH,
 S_GOTO_WEAPON, S_POST_DIALOG, S_WANDER) = range(13)

_STATE_NAMES = {
    S_STOP: 'STOP', S_WAIT_WEAPON: 'WAIT_WEAPON', S_OPEN_SHOP: 'OPEN_SHOP',
    S_WAIT_DIALOG: 'WAIT_DIALOG', S_BUY: 'BUY', S_WAIT_ALCH: 'WAIT_ALCH',
    S_POSITION: 'POSITION', S_GIVE: 'GIVE', S_WAIT_HAMMER: 'WAIT_HAMMER',
    S_GOTO_ALCH: 'GOTO_ALCH', S_GOTO_WEAPON: 'GOTO_WEAPON',
    S_POST_DIALOG: 'POST_DIALOG', S_WANDER: 'WANDER'
}



class EnergyBot(ui.ScriptWindow):
    def __init__(self):
        # Self-contained frame pump: OnUpdate ticks Frame while State == 1.
        ui.ScriptWindow.__init__(self)
        self.Show()
        self.State = 0
        self._frameTimer = 0.0
        self.time_wait = 0.4
        self.state = S_STOP
        self.autoBuy = False
        self._lastGiveAt = 0.0
        self._nextGiveDelay = 0.0
        self._questHooked = False
        self._shopTries = 0
        self._dialogWait = 0
        self._lastGivable = -1
        self._buyProgressAt = 0.0
        self._lastBuyAt = 0.0
        self._nextBuyDelay = 0.0
        self._posTarget = None
        self._posTries = 0
        self._alchTries = 0
        self._alchStart = 0.0
        self._walkLastPos = None
        self._walkStuckN = 0
        self._lastDismount = 0.0
        self._dismountCd = 0   # tick countdown: 120 ticks * 0.5s = 60s
        self._wpnTries = 0
        self._wpnStart = 0.0
        self._runsDone = 0
        self._pauseUntil = 0.0
        self._nextPauseAt = 0.0
        # multi-route: gravacao + replay aleatorio
        self._recRoute = None
        self._playRoute = None
        self._playIdx = 0
        # stuck escalation: WASD -> ESC livre
        self._stuckRound = 0
        self._wasdHeld = 0
        self._escActive = False
        self._escCmdIdx = 0
        self._escTickN = 0
        self._escPos = None
        self._escCount = 0
        self._escReason = ''
        self._escHopAt = 0.0
        self._escHopOk = False
        # pausa: valor usado no ultimo armamento (detectar mudancas no campo)
        self._pauseEveryUsed = -1
        self._backoffN = 0
        # rotas de emergencia (pool manual separado)
        self.emergMode = False
        self._emergLearn = 0
        # gravar manual: nunca andar sozinho, esperar o jogador
        self.recManual = False
        self.BuildWindow()

    def Start(self):
        self.State = 1

    def Stop(self):
        self.State = 0

    def _setState(self, s, reason=''):
        old = _STATE_NAMES.get(self.state, str(self.state))
        new = _STATE_NAMES.get(s, str(s))
        self.state = s
        _ub_log('[Energy] %s -> %s%s' % (old, new, (' (%s)' % reason) if reason else ''))
        _tel_log('%s -> %s' % (old, new))
        try:
            now = OpenLib.Monotonic()
            if s == S_OPEN_SHOP:
                _tel['buy_start'] = now
                _tel['cycle_start'] = now
            elif s == S_GOTO_ALCH:
                _tel['walk_alch'] = now
            elif s == S_GIVE:
                _tel['give'] = now
            elif s == S_GOTO_WEAPON:
                _tel['walk_back'] = now
        except:
            pass
        # MULTI-ROUTE: ao entrar em caminhada comeca a GRAVAR e escolhe uma
        # rota gravada AO ACASO (com jitter) para seguir; ao sair sem chegar
        # ao destino a gravacao parcial e descartada. Grava TAMBEM quando e
        # o JOGADOR a andar (estados WAIT) -- mais rotas gravadas.
        try:
            # REC MANUAL: nunca caminhar sozinho -- converter a caminhada em
            # "espera o jogador" (que grava a rota manual ao andar)
            if self.recManual and s in (S_GOTO_ALCH, S_GOTO_WEAPON):
                self._playRoute = None
                self._setState(S_WAIT_ALCH if s == S_GOTO_ALCH else S_WAIT_WEAPON,
                    'rec-manual: espera o jogador andar')
                return
            if self._recRoute and s not in (S_GOTO_ALCH, S_GOTO_WEAPON, S_WAIT_ALCH, S_WAIT_WEAPON):
                self._recRoute = None
            if s == S_GOTO_ALCH or s == S_WAIT_ALCH:
                self._recStart(self._recBaseType('to_alch'))
                if s == S_GOTO_ALCH:
                    self._playRoute = self._routePick('to_alch')
                    self._playIdx = 0
            elif s == S_GOTO_WEAPON or s == S_WAIT_WEAPON:
                self._recStart(self._recBaseType('to_weapon'))
                if s == S_GOTO_WEAPON:
                    self._playRoute = self._routePick('to_weapon')
                    self._playIdx = 0
        except:
            pass

    def OnUpdate(self):
        if not self.State:
            return
        val, self._frameTimer = OpenLib.timeSleep(self._frameTimer, self.time_wait)
        if not val:
            return
        try:
            self.Frame()
        except:
            pass

    # ------------------------------------------------------------------ UI ----
    def BuildWindow(self):
        comp = UIComponents.Component()
        self.Board = ui.BoardWithTitleBar()
        self.Board.SetSize(260, 386)
        self.Board.SetPosition(52, 40)
        self.Board.AddFlag('movable')
        self.Board.AddFlag('float')   # float windows never steal keyboard focus
        self.Board.SetTitleName('MT2Robs Bot - Energy')
        self.Board.SetCloseEvent(self.switch_state)
        self.Board.Hide()

        self.lInfo = comp.TextLine(self.Board, 'Stopped', 20, 38, comp.RGB(255, 255, 0))
        self.lEta = comp.TextLine(self.Board, '', 20, 62, comp.RGB(200, 200, 200))

        self.buyKnivesBtn = comp.OnOffButton(self.Board, 'Auto-buy knives', 'You walk to the dealer; the bot buys + then exchanges at the alchemist', 20, 90,
            funcState=self.OnAutoBuy)

        self.lRuns = comp.TextLine(self.Board, 'ciclos (0=inf):', 20, 172, comp.RGB(255, 220, 120))
        self.edRuns = comp.OnlyEditLine(self.Board, 80, 18, 118, 168, '0', 10)
        self.allinBtn = comp.Button(self.Board, 'INF', 'Ciclos ilimitados (0 = infinito)', 210, 170, self.OnAllIn,
            'd:/ymir work/ui/public/small_button_01.sub', 'd:/ymir work/ui/public/small_button_02.sub', 'd:/ymir work/ui/public/small_button_03.sub')
        self.lSpent = comp.TextLine(self.Board, 'ciclo: 0', 20, 194, comp.RGB(200, 150, 150))

        self.lPause = comp.TextLine(self.Board, 'pausa a cada', 20, 204, comp.RGB(200, 200, 200))
        self.edPause = comp.OnlyEditLine(self.Board, 28, 18, 98, 200, '0', 3)
        self.lDur = comp.TextLine(self.Board, 'min durante', 138, 204, comp.RGB(200, 200, 200))
        self.edDur = comp.OnlyEditLine(self.Board, 28, 18, 218, 200, '5', 2)
        self.lDur2 = comp.TextLine(self.Board, 'min', 254, 204, comp.RGB(200, 200, 200))

        self.lJit = comp.TextLine(self.Board, 'jitter: pausas e intervalos variam', 20, 232, comp.RGB(160, 160, 160))
        self.lJit2 = comp.TextLine(self.Board, '+-20% para quebrar o padrao detectavel', 20, 250, comp.RGB(160, 160, 160))

        # multi-route: rotas gravadas neste mapa (usadas ao acaso)
        self.lRoutes = comp.TextLine(self.Board, 'rotas gravadas: 0 (uso random)', 20, 294, comp.RGB(150, 200, 255))

        # ROTAS DE EMERGENCIA: 2 rotas manuais gravadas pelo jogador; ligado =
        # usa/grava SO o pool de emergencia; desligado = rotas normais
        self.emergBtn = comp.OnOffButton(self.Board, 'Rotas EMERG', 'ON: usa/grava so rotas de emergencia (1a vez: gravar as 2 rotas manuais)', 20, 316,
            funcState=self.OnEmerg)

        # GRAVAR MANUAL: ligado = o bot NUNCA anda sozinho (n procura rotas,
        # n da voltas) -- pede-te para andar e grava cada caminhada tua
        self.recManBtn = comp.OnOffButton(self.Board, 'Gravar manual', 'ON: pede movimento manual em vez de andar sozinho (grava rota nova a cada caminhada)', 20, 338,
            funcState=self.OnRecManual)

        # countdown to the NEXT pause (or 'desligado' / 'em pausa')
        self.lPauseCd = comp.TextLine(self.Board, 'proxima pausa: desligado', 20, 272, comp.RGB(150, 200, 255))

        # PAUSE POPUP (shown during anti-detection pauses)
        self.PauseBoard = ui.BoardWithTitleBar()
        self.PauseBoard.SetSize(300, 130)
        self.PauseBoard.SetCenterPosition()
        self.PauseBoard.AddFlag('float')
        self.PauseBoard.SetTitleName('MODO PAUSA ANTI-DETECCAO')
        self.PauseBoard.SetCloseEvent(self._dismissPause)
        self.PauseBoard.Hide()

        pl1 = comp.TextLine(self.PauseBoard, 'Pausa activa para quebrar o padrao de bot.', 20, 38, comp.RGB(255, 220, 120))
        pl2 = comp.TextLine(self.PauseBoard, 'Protege contra deteccao do servidor e report.', 20, 58, comp.RGB(200, 200, 200))
        pl3 = comp.TextLine(self.Board, '', 0, 0, comp.RGB(0, 0, 0))  # spacer
        self.lPauseCountdown = comp.TextLine(self.PauseBoard, 'Retoma em --s', 20, 82, comp.RGB(120, 255, 120))
        self.btnPauseStop = comp.Button(self.PauseBoard, 'PARAR TUDO', 'Cancelar o ciclo e parar o bot', 100, 102, self._onPauseStop,
            'd:/ymir work/ui/public/large_button_01.sub', 'd:/ymir work/ui/public/large_button_02.sub', 'd:/ymir work/ui/public/large_button_03.sub')

        self.enableEnergyBot = comp.OnOffButton(self.Board, '', '', 100, 120,
            OffUpVisual=eXLib.PATH + 'MT2Robs/Images/start_0.tga',
            OffOverVisual=eXLib.PATH + 'MT2Robs/Images/start_1.tga',
            OffDownVisual=eXLib.PATH + 'MT2Robs/Images/start_2.tga',
            OnUpVisual=eXLib.PATH + 'MT2Robs/Images/stop_0.tga',
            OnOverVisual=eXLib.PATH + 'MT2Robs/Images/stop_1.tga',
            OnDownVisual=eXLib.PATH + 'MT2Robs/Images/stop_2.tga',
            funcState=self.SwitchEnableEnergyBot, defaultValue=False)

    def switch_state(self):
        if self.Board.IsShow():
            self.Board.Hide()
        else:
            self.Board.Show()

    def OnAutoBuy(self, val):
        self.autoBuy = bool(val)
        _ub_log('[Energy] auto-buy toggle -> %s' % self.autoBuy)

    def OnEmerg(self, val):
        # ROTAS DE EMERGENCIA: ligado = usa/grava so o pool de emergencia.
        # Primeira vez ligado (pool vazio) -> modo de gravacao manual guiada
        # das 2 rotas: vendedor -> alquimista.
        self.emergMode = bool(val)
        _ub_log('[Energy] modo rotas EMERGENCIA -> %s' % self.emergMode)
        if self.emergMode:
            try:
                mapname = str(background.GetCurrentMapName())
                have = len(_routes_get(mapname, 'emerg_to_alch')) + len(_routes_get(mapname, 'emerg_to_weapon'))
            except:
                have = 0
            if have <= 0:
                self._emergLearn = 1
                self.Start()
                self._setState(S_WAIT_WEAPON, 'emerg 1/2: anda ao vendedor')
                self._msg('EMERG 1/2: ANDA ao VENDEDOR (a gravar)')
                return
        self._emergLearn = 0
        self._routesLabel()

    def OnRecManual(self, val):
        # GRAVAR MANUAL: ligado = o bot nunca anda sozinho; quando precisa de
        # ir a um NPC pede para TU andares (e grava a rota). Compra/troca
        # continuam automaticos. Funciona ate desligar o botao.
        self.recManual = bool(val)
        _ub_log('[Energy] modo GRAVAR MANUAL -> %s' % self.recManual)
        if self.recManual:
            self._playRoute = None
            self._msg('REC MANUAL: anda TU, eu gravo as rotas')
        else:
            self._msg('Gravar manual: OFF (voltou ao automatico)')

    def _msg(self, s):
        try:
            self.lInfo.SetText(s)
        except:
            pass

    def _setEta(self, secs):
        try:
            secs = int(secs)
            if secs < 60:
                t = '~%ds' % secs
            elif secs < 3600:
                t = '~%dm %02ds' % (secs // 60, secs % 60)
            else:
                t = '~%dh %02dm' % (secs // 3600, (secs % 3600) // 60)
            self.lEta.SetText('ETA: ' + t)
        except:
            pass

    def _clearEta(self):
        try:
            self.lEta.SetText('')
        except:
            pass

    # ------------------------------------------------------------ helpers ----
    def _rollDelay(self, dmin, dmax):
        try:
            return _rnd_uniform(dmin, dmax)
        except:
            return (dmin + dmax) / 2.0

    def _rollNextGiveDelay(self):
        if self._rollDelay(0.0, 1.0) < PAUSE_CHANCE:
            return self._rollDelay(PAUSE_MIN, PAUSE_MAX)
        return self._rollDelay(GIVE_DELAY_MIN, GIVE_DELAY_MAX)

    def _rollNextBuyDelay(self):
        if self._rollDelay(0.0, 1.0) < BUY_PAUSE_CHANCE:
            return self._rollDelay(BUY_PAUSE_MIN, BUY_PAUSE_MAX)
        return self._rollDelay(BUY_DELAY_MIN, BUY_DELAY_MAX)

    def _avgGiveDelay(self):
        avg_normal = (GIVE_DELAY_MIN + GIVE_DELAY_MAX) / 2.0
        avg_pause = (PAUSE_MIN + PAUSE_MAX) / 2.0
        return (1.0 - PAUSE_CHANCE) * avg_normal + PAUSE_CHANCE * avg_pause

    def _avgBuyDelay(self):
        avg_normal = (BUY_DELAY_MIN + BUY_DELAY_MAX) / 2.0
        avg_pause = (BUY_PAUSE_MIN + BUY_PAUSE_MAX) / 2.0
        return (1.0 - BUY_PAUSE_CHANCE) * avg_normal + BUY_PAUSE_CHANCE * avg_pause

    def _loadSavedNpcs(self):
        # merge saved positions (learned) with the hardcoded defaults
        try:
            for line in open(NPC_SAVE_FILE, 'r'):
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                parts = line.split('=')
                if len(parts) != 2:
                    continue
                mapname = parts[0]
                coords = parts[1].split(',')
                if len(coords) == 4:
                    NPC_POSITIONS[mapname] = {
                        'weapon': (float(coords[0]), float(coords[1])),
                        'alchemist': (float(coords[2]), float(coords[3]))}
        except:
            pass

    _npcSaved = {}  # per-session cache: {(map, npc): (x, y)} already saved

    def _saveNpcPos(self, mapname, npc, x, y):
        # ONLY write when the position CHANGED (was writing 19x/tick = lag!)
        key = (mapname, npc)
        if key in self._npcSaved:
            ox, oy = self._npcSaved[key]
            if abs(ox - x) < 200 and abs(oy - y) < 200:
                return   # same position, already saved -> skip (no I/O)
        self._npcSaved[key] = (x, y)
        try:
            saved = {}
            try:
                for line in open(NPC_SAVE_FILE, 'r'):
                    line = line.strip()
                    if '=' not in line or line.startswith('#'):
                        continue
                    parts = line.split('=')
                    if len(parts) == 2:
                        saved[parts[0]] = parts[1]
            except:
                pass
            if mapname in saved:
                old = saved[mapname].split(',')
                if npc == 'weapon':
                    saved[mapname] = '%d,%d,%s,%s' % (int(x), int(y), old[2], old[3])
                else:
                    saved[mapname] = '%s,%s,%d,%d' % (old[0], old[1], int(x), int(y))
            else:
                if npc == 'weapon':
                    saved[mapname] = '%d,%d,0,0' % (int(x), int(y))
                else:
                    saved[mapname] = '0,0,%d,%d' % (int(x), int(y))
            f = open(NPC_SAVE_FILE, 'w')
            f.write('# map=weaponX,weaponY,alchemistX,alchemistY\n')
            for m, v in saved.items():
                if v != '0,0,0,0':
                    f.write('%s=%s\n' % (m, v))
            f.close()
            _ub_log('[Energy] NPC learned: %s %s at (%d,%d)' % (mapname, npc, x, y))
        except:
            pass

    def _mapNpcs(self):
        try:
            self._loadSavedNpcs()
            return NPC_POSITIONS.get(background.GetCurrentMapName())
        except:
            return None

    def _pos(self):
        x, y, z = player.GetMainCharacterPosition()
        return x, y

    def _dist(self, p):
        mx, my = self._pos()
        return OpenLib.dist(mx, my, p[0], p[1])

    def _invSize(self):
        # scan 200 slots: GetItemIndex returns 0 for locked slots so it's safe
        return 200

    def _givableSlots(self):
        slots = []
        for i in range(self._invSize()):
            if player.GetItemIndex(i) in ALL_GIVABLE_ITEMS:
                slots.append(i)
        return slots

    def _countGivable(self):
        return len(self._givableSlots())

    def _nextGivableSlot(self):
        # human-like: click a random givable slot, not always the first
        slots = self._givableSlots()
        if not slots:
            return -1
        try:
            return _rnd_choice(slots)
        except:
            return slots[0]

    def _freeCells(self):
        try:
            free = 0
            for i in range(self._invSize()):
                if player.GetItemIndex(i) == 0:
                    free += 1
            return free
        except:
            return 999

    def _rollSpotNear(self, p):
        # RANDOM standing spot around the NPC: random angle + random distance.
        # This is why the bot never parks on the same pixel twice.
        # ZONAS: o spot tem de ficar em area LIVRE/NAO MARCADA (nunca morta);
        # se o mapa tiver zonas livres definidas, prefere-as nas 1as tentativas
        wantFree = self._zoneHasFree()
        for _try in range(14):
            ang = self._rollDelay(0.0, 6.28318)
            r = self._rollDelay(POS_RMIN, POS_RMAX)
            tx = int(p[0] + math.cos(ang) * r)
            ty = int(p[1] + math.sin(ang) * r)
            if not self._zoneOK(tx, ty):
                continue
            if wantFree and not self._zoneFree(tx, ty) and _try < 10:
                continue
            return (tx, ty)
        return (int(p[0]), int(p[1]))

    def _unhookQuest(self):
        if self._questHooked:
            self._questHooked = False
            try: OpenLib.showAnswers()
            except: pass

    def _myPos(self):
        try:
            x, y, z = player.GetMainCharacterPosition()
            if x == 0 and y == 0:
                return None
            return (x, y)
        except:
            return None

    # ------------------------------------------------------------ zonas ----
    def _zoneMap(self):
        try:
            return str(background.GetCurrentMapName())
        except:
            return None

    def _zoneOK(self, x, y):
        # True = pode andar/gravar em (x,y): zona LIVRE ou NAO MARCADA.
        # Zona MORTA (vermelha) -> False. Sem zonas definidas -> True.
        if ZoneGuard is None:
            return True
        m = self._zoneMap()
        if not m:
            return True
        try:
            return ZoneGuard.Allowed(x, y, m)
        except:
            return True

    def _zoneSegOK(self, fx, fy, x, y):
        # True se (x,y) e permitido E a linha desde (fx,fy) nao corta
        # nenhuma zona morta
        if ZoneGuard is None:
            return True
        m = self._zoneMap()
        if not m:
            return True
        try:
            return ZoneGuard.SafeWaypoint(fx, fy, x, y, m)
        except:
            return True

    def _zoneFree(self, x, y):
        if ZoneGuard is None:
            return False
        m = self._zoneMap()
        if not m:
            return False
        try:
            return ZoneGuard.IsFree(x, y, m)
        except:
            return False

    def _zoneHasFree(self):
        if ZoneGuard is None:
            return False
        m = self._zoneMap()
        if not m:
            return False
        try:
            return ZoneGuard.HasFree(m)
        except:
            return False

    def _walkSmart(self, now, me, tx, ty):
        # caminho direto (click-move) para trocos curtos de aproximacao
        try:
            chr.MoveToDestPosition(player.GetMainCharacterIndex(), int(tx), int(ty))
        except:
            pass

    # ------------------------------------------------ route recording ----
    def _recBaseType(self, base):
        # tipo de gravacao: pool de EMERGENCIA se o modo esta ligado (ou
        # durante a gravatura manual), senao o pool normal
        try:
            if self._emergLearn or self.emergMode:
                return 'emerg_' + base
        except:
            pass
        return base

    def _recStart(self, rtype):
        try:
            mapname = str(background.GetCurrentMapName())
        except:
            self._recRoute = None
            return
        me = self._myPos()
        if not mapname or me is None:
            self._recRoute = None
            return
        self._recRoute = {'map': mapname, 'type': rtype,
                          'wps': [(int(me[0]), int(me[1]))]}

    def _recTick(self):
        r = self._recRoute
        if not r:
            return
        me = self._myPos()
        if me is None:
            return
        lx, ly = r['wps'][-1]
        d = OpenLib.dist(me[0], me[1], lx, ly)
        if d >= ROUTE_TELEPORT_JUMP:
            # teleport no meio da rota (ESC livre, GM, ...) -> descartar
            self._recRoute = None
            _ub_log('[Energy] rota: salto de %dpx -> gravacao descartada' % int(d))
            return
        if d >= ROUTE_WP_MIN_DIST:
            # ZONAS: so gravar waypoints em area LIVRE/NAO MARCADA e sem
            # zona MORTA no troco -- caminhos por predios/agua nao sao gravados
            if self._zoneSegOK(lx, ly, me[0], me[1]):
                r['wps'].append((int(me[0]), int(me[1])))
            else:
                _ub_log('[Energy] rota: wp (%d,%d) em/cruzando zona MORTA -> nao gravado' % (
                    int(me[0]), int(me[1])))

    def _recFinish(self):
        r = self._recRoute
        self._recRoute = None
        if not r:
            return
        try:
            wps = r['wps']
            # ZONAS: filtrar a rota gravada (protege tambem rotas antigas)
            if ZoneGuard is not None:
                wps = ZoneGuard.FilterRoute(wps, r['map'])
            if _routes_add(r['map'], r['type'], wps):
                _ub_log('[Energy] ROTA gravada: %s %s (%d pontos, total %d)' % (
                    r['map'], r['type'], len(wps), _routes_count(r['map'])))
                _tel_log('ROTA gravada %s %s (%d pts)' % (r['type'], r['map'], len(wps)))
                self._routesLabel()
        except:
            pass

    def _routePick(self, rtype):
        # escolhe uma rota AO ACASO cujo inicio esteja perto de nos, com
        # jitter. POOLS FUNDIDOS: prefere o pool do modo atual (emergencia
        # se EMERG ligado, senao normal) mas cai AUTOMATICAMENTE no outro
        # quando o preferido nao tem rotas comecaveis daqui -- a ideia da
        # emergencia e evitar players/NPCs no meio da cidade.
        try:
            mapname = str(background.GetCurrentMapName())
            pref = 'emerg_' + rtype if self.emergMode else rtype
            other = rtype if self.emergMode else 'emerg_' + rtype
            pref_pool = _routes_get(mapname, pref)
            other_pool = _routes_get(mapname, other)
            me = self._myPos()
            cands = []
            if me is not None:
                for pool in (pref_pool, other_pool):
                    for r in pool:
                        try:
                            if r['wps'] and OpenLib.dist(me[0], me[1], r['wps'][0][0], r['wps'][0][1]) < ROUTE_START_MAX:
                                cands.append(r)
                        except:
                            pass
                    if cands:
                        break   # so o primeiro pool com rotas proximas
            if not cands:
                cands = pref_pool or other_pool   # nada perto: usa o que houver
            if not cands:
                return None
            r = _rnd_choice(cands)
            wps = []
            for (x, y) in r['wps']:
                jx = int(x + _rnd_uniform(-ROUTE_JITTER, ROUTE_JITTER))
                jy = int(y + _rnd_uniform(-ROUTE_JITTER, ROUTE_JITTER))
                # ZONAS: jitter nao pode empurrar o waypoint para zona MORTA
                if not self._zoneOK(jx, jy):
                    jx, jy = int(x), int(y)
                wps.append((jx, jy))
            return wps
        except:
            return None

    def _routeWalkTick(self):
        # segue a rota escolhida waypoint a waypoint (click-move por ponto).
        # WATCHDOG: waypoint sem progresso (jitter pode te-lo posto dentro
        # dum predio/players) -> SKIP; muitos skips -> trocar de rota (retoma
        # no goto tick, pode vir do outro pool).
        if not self._playRoute:
            return False
        me = self._myPos()
        if me is None:
            return True
        # AVANCO RAPIDO: se ficamos atras da rota (resgate manual do jogador,
        # skips), salta para o waypoint RESTANTE mais proximo de nos -- nunca
        # voltar atras a waypoints ja passados
        try:
            best_i = -1
            best_d = 1e9
            i = self._playIdx
            while i < len(self._playRoute) and i <= self._playIdx + 8:
                di = OpenLib.dist(me[0], me[1], self._playRoute[i][0], self._playRoute[i][1])
                # ZONAS: waypoint em zona MORTA nunca e alvo (rota antiga)
                if di < best_d and self._zoneOK(self._playRoute[i][0], self._playRoute[i][1]):
                    best_d = di
                    best_i = i
                i += 1
            if best_i > self._playIdx and best_d <= ROUTE_PLAY_ARRIVE:
                self._playIdx = best_i
                self._wpStallN = 0
        except:
            pass
        if self._playIdx >= len(self._playRoute):
            self._playRoute = None   # rota terminada -> re-pick assume
            return False
        tx, ty = self._playRoute[self._playIdx]
        # ZONAS: waypoint dentro de zona MORTA -> saltar (e trocar de rota
        # se a rota tiver muitos pontos invalidos)
        if not self._zoneOK(tx, ty):
            self._wpSkips = getattr(self, '_wpSkips', 0) + 1
            _ub_log('[Energy] zona: wp %d/%d MORTO -> skip' % (
                self._playIdx + 1, len(self._playRoute)))
            self._playIdx += 1
            if self._wpSkips >= 5:
                self._wpSkips = 0
                _ub_log('[Energy] rota com wps em zona morta -> TROCAR de rota')
                self._playRoute = None
            return True
        d = OpenLib.dist(me[0], me[1], tx, ty)
        if d <= ROUTE_PLAY_ARRIVE:
            self._playIdx += 1
            self._wpStallN = 0
            self._wpSkips = 0
            return True
        # limite escalado pela distancia do troco (30 ticks minimo)
        limit = 30
        try:
            if d > 750:
                limit = int(d / 25.0)
        except:
            pass
        self._wpStallN = getattr(self, '_wpStallN', 0) + 1
        if self._wpStallN > limit:
            self._wpStallN = 0
            self._wpSkips = getattr(self, '_wpSkips', 0) + 1
            _ub_log('[Energy] rota: wp %d/%d sem progresso -> skip (%d)' % (
                self._playIdx + 1, len(self._playRoute), self._wpSkips))
            self._playIdx += 1
            if self._wpSkips >= 5:
                self._wpSkips = 0
                _ub_log('[Energy] rota com ma passagem -> TROCAR de rota')
                self._playRoute = None
                return False
            return True
        try:
            chr.MoveToDestPosition(player.GetMainCharacterIndex(), int(tx), int(ty))
        except:
            pass
        return True

    def _routeEscapeStep(self, me):
        # PRESO em players/obstaculos: escolhe uma ROTA GRAVADA ao acaso e
        # caminha para o waypoint DELA mais proximo de nos -- corredor
        # comprovado onde ja se conseguiu andar. True se conseguiu mandar.
        try:
            mapname = str(background.GetCurrentMapName())
            # PRIORIZAR SEMPRE as rotas de EMERGENCIA (sao as seguras, gravadas
            # a mao); sem elas -> pools normais
            cands = _routes_get(mapname, 'emerg_to_alch') + _routes_get(mapname, 'emerg_to_weapon')
            if not cands:
                cands = _routes_get(mapname, 'to_alch') + _routes_get(mapname, 'to_weapon')
            if not cands:
                return False
            r = _rnd_choice(cands)
            if not r or not r['wps']:
                return False
            best = None
            bd = 1e9
            for (wx, wy) in r['wps']:
                # ZONAS: waypoint de fuga em zona MORTA nao serve (predio/agua)
                if not self._zoneOK(wx, wy):
                    continue
                d = OpenLib.dist(me[0], me[1], wx, wy)
                if d < bd:
                    bd = d
                    best = (wx, wy)
            if best is None:
                return False
            chr.MoveToDestPosition(player.GetMainCharacterIndex(), int(best[0]), int(best[1]))
            _ub_log('[Energy] PRESO: escape por rota %s -> wp (%d,%d) a %dpx' % (
                r['type'], best[0], best[1], int(bd)))
            return True
        except:
            return False

    def _routeProgressCheck(self, dx_, dy_, rtype):
        # ANTI-CIRCULOS: medir o progresso REAL ate ao destino enquanto
        # seguimos a rota. Se ha ~45s que nao nos aproximamos do destino
        # (a andar as voltas), trocar de rota (pode vir do outro pool).
        try:
            mx, my = self._pos()
            dn = OpenLib.dist(mx, my, dx_, dy_)
        except:
            return
        best = getattr(self, '_routeBestDn', None)
        if best is None or dn < best - 100.0:
            self._routeBestDn = dn
            self._routeStallN = 0
            return
        self._routeStallN = getattr(self, '_routeStallN', 0) + 1
        if self._routeStallN > 110:
            self._routeStallN = 0
            self._routeBestDn = None
            _ub_log('[Energy] rota: sem progresso real ate ao destino -> TROCAR')
            self._playRoute = None
            self._playIdx = 0
            self._wpSkips = 0
            np_ = self._routePick(rtype)
            if np_:
                self._playRoute = np_

    def _routesLabel(self):
        try:
            mapname = str(background.GetCurrentMapName())
            n = len(_routes_get(mapname, 'to_alch')) + len(_routes_get(mapname, 'to_weapon'))
            e = len(_routes_get(mapname, 'emerg_to_alch')) + len(_routes_get(mapname, 'emerg_to_weapon'))
            txt = 'rotas: %d | emerg: %d%s' % (
                n, e, ' [EMERG ON]' if self.emergMode else '')
            # ZONAS: estado do ficheiro de zonas deste mapa
            if ZoneGuard is not None:
                try:
                    if ZoneGuard.HasZones(mapname):
                        nd, nf = ZoneGuard.Counts(mapname)
                        txt += ' | zonas M%d/L%d' % (nd, nf)
                    else:
                        txt += ' | zonas: NENHUMA'
                except:
                    pass
            self.lRoutes.SetText(txt)
        except:
            pass

    # ------------------------------------------------------------ control ----
    def SwitchEnableEnergyBot(self, val):
        if val:
            self._startBot()
        else:
            self._stopBot()

    def _startBot(self):
        # CRITICAL: stop the hunt bot -- while it runs it sends click packets
        # on ANYTHING nearby (players, blacksmiths, general store NPCs...)
        try:
            import HuntBot as _HBstop
            hb = getattr(_HBstop, 'instance', None)
            if hb is not None and hb.running:
                hb.SwitchEnabled(False)
                try:
                    hb.enableBtn.SetOff()
                except:
                    pass
                _ub_log('[Energy] hunt auto-OFF (energy takes over)')
        except:
            pass
        # also stop the follow bot (it would drag the char away from NPCs)
        try:
            import FollowBot as _FBstop
            fb = getattr(_FBstop, 'instance', None)
            if fb is not None and fb.running:
                fb.SwitchEnabled(False)
                try:
                    fb.enableBtn.SetOff()
                except:
                    pass
                _ub_log('[Energy] follow auto-OFF (energy takes over)')
        except:
            pass

        # load any learned positions first
        self._loadSavedNpcs()
        self._routesLabel()
        # CHECK: PathRunner learned for this map?
        try:
            if PathRunner is not None and not PathRunner.hasLearnedPath():
                _ub_log('[Energy] AVISO: sem rota aprendida (F7->APRENDER) -- a usar pathfinding (pode falhar)')
                self._msg('AVISO: sem ROTA APRENDIDA (F7)')
        except:
            pass

        npcs = self._mapNpcs()
        if not npcs:
            mapname = 'unknown'
            try:
                mapname = background.GetCurrentMapName()
            except:
                pass
            self._msg('Mapa %s: ANDA ao vendedor e alquimista (aprende)' % mapname)
            _ub_log('[Energy] mapa %s sem NPCs conhecidos -> MODO APRENDER (anda aos NPCs)' % mapname)
            # DON'T stop: stay in a learning state that scans for NPCs
            self.Start()
            self._setState(S_WAIT_WEAPON, 'learning map positions')
            return

        self.Start()
        self._shopTries = 0
        self._runsDone = 0
        self._pauseUntil = 0.0
        self._nextPauseAt = 0.0
        self._pauseEveryUsed = -1
        self._escCount = 0   # nova sessao: limpa o budget de ESC livre
        self._escActive = False
        self._escHopAt = 0.0
        self._escHopOk = False
        # arm the pause timer NOW so it counts from the session start
        try:
            every = self._pauseEvery() * 60.0
            if every > 0:
                self._nextPauseAt = OpenLib.Monotonic() + every * self._rollDelay(0.8, 1.2)
                self._pauseEveryUsed = every
                _ub_log('[Energy] pausa armada: primeira em ~%d min' % (every / 60.0))
        except:
            pass
        have = self._countGivable()

        if self.autoBuy and self._dist(npcs['weapon']) <= NPC_CLICK_DIST:
            # CLOSE to the dealer (300px not 1800!) -> buy right away
            self._pauseCheck()
            if self._pauseUntil > 0.0:
                self._setState(S_STOP, 'starting in pause')
                self._msg('pausa inicial activa...')
                return
            self._setState(S_OPEN_SHOP, 'at dealer, have=%d' % have)
        elif self.autoBuy and self._dist(npcs['weapon']) <= NEAR_DIST:
            # NEAR but not close enough to click -> walk the last stretch
            self._wpnTries = 0
            self._wpnStart = OpenLib.Monotonic()
            self._setState(S_GOTO_WEAPON, 'walking to dealer (start)')
            self._msg('A ANDAR ao vendedor...')
            self._msg('Buying knives')
        elif have > 0:
            # something to exchange -> wait for YOU to walk to the alchemist
            self._setState(S_WAIT_ALCH, 'have=%d' % have)
            self._msg('Walk to the alchemist')
        elif self.autoBuy:
            self._setState(S_WAIT_WEAPON, 'waiting for player')
            self._msg('Walk to the weapon dealer')
        else:
            self._msg('Nothing to exchange - buy first')
            try: self.enableEnergyBot.SetOff()
            except: pass
            self.Stop()
            return
        _ub_log('[Energy] start: autoBuy=%s have=%d pos=(%d,%d)' % (self.autoBuy, have, self._pos()[0], self._pos()[1]))

    def _stopBot(self):
        # ALWAYS restore dialogs when stopping
        try:
            self.PauseBoard.Hide()   # nunca deixar o popup da pausa congelado
        except:
            pass
        # limpar o estado do ESC livre (senao continua activo depois de
        # religar o bot -- viu-se no log: '/restart' depois de um restart)
        self._escActive = False
        self._escHopAt = 0.0
        self._escHopOk = False
        self._keysRelease()
        try:
            if self._questHooked:
                OpenLib.showAnswers()
                self._questHooked = False
        except:
            pass
        self._setState(S_STOP, 'user stop')
        try: Movement.StopMovement()
        except: pass
        try:
            mx, my = self._pos()
            chr.MoveToDestPosition(player.GetMainCharacterIndex(), int(mx), int(my))
        except: pass
        self._unhookQuest()
        try:
            if shop.IsOpen():
                net.SendShopEndPacket()
        except: pass
        self.Stop()
        self._msg('Stopped')
        self._clearEta()

    # ------------------------------------------------------------ loop ----
    def Frame(self):
        try:
            if not background.GetCurrentMapName():
                return
            if not player.GetMainCharacterIndex():
                return
        except:
            return

        # ESC LIVRE: enquanto activo e a unica coisa que corre (o WASD ja
        # falhou); ao soltar a personagem retoma o ciclo sozinho
        if self._escActive:
            self._escFreeTick()
            return

        # NPC AUTO-LEARN: ALWAYS scan and update (even on known maps -- the
        # hardcoded positions can be wrong, and NPCs can move between
        # maintenance patches). Runs every tick, saves only when the NPC is
        # actually visible nearby.
        try:
            mapname = background.GetCurrentMapName()
            if mapname:
                wvid = OpenLib.GetInstanceByID(WEAPON_RACE)
                if wvid >= 0:
                    x, y, z = eXLib.GetPixelPosition(wvid)
                    self._saveNpcPos(mapname, 'weapon', x, y)
                avid = OpenLib.GetInstanceByID(ALCHEMIST_RACE)
                if avid >= 0:
                    x, y, z = eXLib.GetPixelPosition(avid)
                    self._saveNpcPos(mapname, 'alchemist', x, y)
        except:
            pass

        # CONTINUOUS DIALOG CLEANUP: quest dialogs (3-button) open during
        # walking when passing near NPCs. Close them EVERY tick while we're
        # in a walking state (not just at specific points).
        try:
            if self.state in (S_GOTO_ALCH, S_GOTO_WEAPON, S_WAIT_ALCH):
                dc = eXLib.GetDialogAnswerCount()
                if isinstance(dc, int) and dc >= 2:
                    try:
                        event.SelectAnswer(1, 0)
                    except:
                        pass
                    _ub_log('[Energy] dialog while walking (cnt=%d) -> closed' % dc)
                    _tel['dialogs'] += 1
        except:
            pass

        # QUEST HOOK STAYS ON for the ENTIRE session (was unhooking during
        # walks -> 3-button dialog reappeared when passing NPCs)
        pass

        # FOREIGN SHOP GUARD: any shop open while NOT buying = wrong shop
        try:
            if shop.IsOpen() and self.state not in (S_BUY, S_POST_DIALOG):
                net.SendShopEndPacket()
                _ub_log('[Energy] foreign shop closed (state=%s)' % _STATE_NAMES.get(self.state, self.state))
                _tel['errors'] += 1
                _tel_log('FOREIGN_SHOP state=%s' % _STATE_NAMES.get(self.state, self.state))
        except:
            pass

        # CONTINUOUS PAUSE CHECK: arm the timer on the FIRST tick (not at
        # dealer arrival) and let it count down independently of NPC visits.
        # BUGFIX: mudar o campo "pausa a cada" AGORA aplica imediatamente --
        # antes o valor so era lido no arranque (nunca deixava baixar <60)
        try:
            every0 = self._pauseEvery() * 60.0
            if every0 <= 0:
                if self._nextPauseAt != 0.0:
                    self._nextPauseAt = 0.0
                    _ub_log('[Energy] pausa desligada (campo a 0)')
                self._pauseEveryUsed = 0
            elif self._nextPauseAt == 0.0 or every0 != self._pauseEveryUsed:
                self._nextPauseAt = OpenLib.Monotonic() + every0 * self._rollDelay(0.8, 1.2)
                self._pauseEveryUsed = every0
                _ub_log('[Energy] pausa (re)armada: proxima em ~%d min' % (every0 / 60.0))
        except:
            pass

        # HUNT KILL-SWITCH: enforce hunt OFF every tick while energy runs
        # (the syncGlobals was re-enabling it behind our back -> hunt clicked
        # on players/NPCs/shops while energy walked through town)
        try:
            import HuntBot as _HBguard
            _hbg = getattr(_HBguard, 'instance', None)
            if _hbg is not None and _hbg.running:
                _hbg.running = False
                _hbg._zoneOn = False
                _hbg._cur = 0
                try:
                    _hbg.zoneBtn.SetText('Zona: OFF')
                except:
                    pass
                _ub_log('[Energy] hunt re-enabled by sync -> killed again')
        except:
            pass

        # anti-pattern pause: when active, do NOTHING this frame
        if self._pauseTick():
            return

        npcs = self._mapNpcs()
        if not npcs:
            try:
                _ub_log('[Energy] STOP: mapa sem NPCs conhecidos (%r) -- causa do user stop' % (
                    background.GetCurrentMapName(),))
            except:
                pass
            self._msg('Left supported map - stopped')
            self._stopBot()
            try: self.enableEnergyBot.SetOff()
            except: pass
            return

        if self.state == S_WAIT_WEAPON:
            # YOU are walking; when you reach the dealer the bot starts buying
            self._recTick()   # gravar a caminhada manual (multi-rota)
            self._msg('Walk to the weapon dealer (%d)' % self._dist(npcs['weapon']))
            if self._dist(npcs['weapon']) <= NEAR_DIST:
                if self._emergLearn == 1:
                    # EMERG 1/2 gravada (vendedor) -> pedir a 2a (alquimista)
                    self._recFinish()
                    self._emergLearn = 2
                    self._setState(S_WAIT_ALCH, 'emerg 2/2: anda ao alquimista')
                    self._msg('EMERG 1/2 OK! ANDA ao ALQUIMISTA (a gravar)')
                    return
                self._recFinish()   # chegada -> GRAVAR a rota manual
                self._setState(S_OPEN_SHOP, 'player arrived')
                self._msg('Buying knives')

        elif self.state == S_OPEN_SHOP:
            # SAFETY: if a shop is somehow already open, skip to buy
            try:
                if shop.IsOpen():
                    _ub_log('[Energy] shop already open -> skip to BUY')
                    self._initBuyPhase()
                    return
            except:
                pass
            # SAFETY: if a dialog is showing (quest, etc), close it first
            try:
                dc = eXLib.GetDialogAnswerCount()
                if isinstance(dc, int) and dc >= 2:
                    _ub_log('[Energy] dialog open (cnt=%d) -> selecting shop' % dc)
                    answer = (dc - 2) if dc >= 4 else 1
                    try: event.SelectAnswer(1, answer)
                    except: pass
                    self._initBuyPhase()
                    return
            except:
                pass
            try:
                have = int(player.GetMoney())
            except:
                have = 0
            if have < KNIFE_PRICE + 5000:
                self._msg('Need %d+ yang to buy' % KNIFE_PRICE)
                return
            vid = OpenLib.GetInstanceByID(WEAPON_RACE)
            if vid < 0:
                return   # dealer not in sight yet
            _ub_log('[Energy] clicking weapon dealer vid=%d (dialog suprimido)' % vid)
            # ACTIVATE QUEST HOOK: blocks the dialog window from RENDERING.
            # The server still sends the dialog data, we just don't show it.
            # We answer blindly on the next tick -> shop opens directly.
            try:
                OpenLib.skipAnswers([], True)   # hook ON (hide dialog)
                self._questHooked = True
            except:
                self._questHooked = False
            net.SendOnClickPacket(vid)
            self._dialogWait = 0
            self._setState(S_WAIT_DIALOG)

        elif self.state == S_WAIT_DIALOG:
            # dialog is HOOKED (invisible): answer blindly as soon as data arrives
            cnt = -1
            try: cnt = eXLib.GetDialogAnswerCount()
            except: cnt = -1
            if isinstance(cnt, int) and cnt >= 2:
                answer = (cnt - 2) if cnt >= 4 else 1
                _ub_log('[Energy] dialog cnt=%d -> answer %d (blind, no popup)' % (cnt, answer))
                try: event.SelectAnswer(1, answer)
                except: pass
                self._initBuyPhase()
            else:
                self._dialogWait += 1
                # SAFETY: if the shop opened without us selecting (client auto)
                try:
                    if shop.IsOpen():
                        _ub_log('[Energy] shop opened during dialog wait -> BUY')
                        self._initBuyPhase()
                        return
                except:
                    pass
                if self._dialogWait > DIALOG_WAIT_MAX:
                    _ub_log('[Energy] dialog timeout (%s) -> answer 1, then CHECK' % cnt)
                    try: event.SelectAnswer(1, 1)
                    except: pass
                    # don't go to BUY immediately: wait to see if it worked
                    self._postDialogWait = 0
                    self._setState(S_POST_DIALOG, 'checking if shop opened')
                    return

        elif self.state == S_BUY:
            self._buyTick()

        elif self.state == S_WAIT_ALCH:
            # YOU walk. When the alchemist is actually IN SIGHT (exchange range)
            # start exchanging right away; if not, ask for one more step closer
            # -- never walk your character to a standing spot by itself.
            self._recTick()   # gravar a caminhada manual (multi-rota)
            vid = OpenLib.GetInstanceByID(ALCHEMIST_RACE)
            if vid >= 0:
                if self._emergLearn == 2:
                    # EMERG 2/2 gravada (alquimista) -> concluido
                    self._recFinish()
                    self._emergLearn = 0
                    _ub_log('[Energy] rotas EMERG gravadas (2/2) -- modo emergencia ON')
                    self._msg('EMERG 2/2 OK! Rotas de emergencia gravadas')
                    self._routesLabel()
                    self._stopBot()
                    try:
                        self.enableEnergyBot.SetOff()
                    except:
                        pass
                    self._msg('EMERG gravadas! Prime PLAY para farmar')
                    return
                _ub_log('[Energy] alchemist in sight -> exchanging from where you stand')
                self._recFinish()   # chegada -> GRAVAR a rota manual
                self._beginGivePhase()
            else:
                self._msg('aproxima mais do alquimista (%d)' % self._dist(npcs['alchemist']))

        elif self.state == S_GIVE:
            self._giveTick()

        elif self.state == S_WAIT_HAMMER:
            self._waitHammerTick()

        elif self.state == S_GOTO_ALCH:
            npcs2 = self._mapNpcs()
            if npcs2:
                self._gotoAlchTick(npcs2['alchemist'])

        elif self.state == S_POST_DIALOG:
            # wait 3s for the shop to actually open after our answer
            try:
                if shop.IsOpen():
                    _ub_log('[Energy] shop confirmed open after dialog -> BUY')
                    self._initBuyPhase()
                    return
            except:
                pass
            self._postDialogWait = getattr(self, '_postDialogWait', 0) + 1
            if self._postDialogWait > 8:   # ~3.2s
                _ub_log('[Energy] shop did NOT open after dialog -> retry click')
                self._shopTries += 1
                if self._shopTries > SHOP_RETRY_MAX:
                    _ub_log('[Energy] shop never opened after %d tries -> STOP' % self._shopTries)
                    self._stopBot()
                    try: self.enableEnergyBot.SetOff()
                    except: pass
                    return
                self._setState(S_OPEN_SHOP, 'retry after dialog fail')

        elif self.state == S_GOTO_WEAPON:
            npcs4 = self._mapNpcs()
            if npcs4:
                self._gotoWeaponTick(npcs4['weapon'])

        elif self.state == S_WANDER:
            self._wanderTick()

    # ------------------------------------------------------ buy phase ----
    def _initBuyPhase(self):
        self._shopTries = 0
        self._lastGivable = -1
        self._buyProgressAt = 0.0
        self._lastBuyAt = 0.0
        self._nextBuyDelay = self._rollDelay(BUY_DELAY_MIN, BUY_DELAY_MAX)
        self._setState(S_BUY)

    def _buyTick(self):
        if not shop.IsOpen():
            self._shopTries += 1
            if self._shopTries > SHOP_RETRY_MAX:
                self._shopTries = 0
                self._setState(S_OPEN_SHOP, 'shop never opened, re-click')
            return
        self._unhookQuest()

        now = OpenLib.GetTime()
        have = self._countGivable()

        if have > self._lastGivable:
            self._lastGivable = have
            self._buyProgressAt = now

        # QUEST DIALOG CLEANUP: the 3-button dialog may still be open.
        # Try BOTH: select answer AND use the quest hook to hide it.
        try:
            cnt2 = eXLib.GetDialogAnswerCount()
            if isinstance(cnt2, int) and cnt2 >= 2:
                try:
                    event.SelectAnswer(1, 0)
                except:
                    pass
                try:
                    OpenLib.skipAnswers([0], True)   # hook + auto-answer
                except:
                    pass
                _ub_log('[Energy] lingering dialog (cnt=%d) -> force-closed' % cnt2)
        except:
            pass

        # LEAVE ONE SLOT FREE -- ONLY in hammer mode (the hammer's drag gesture
        # needs a free cell). In the NORMAL alchemist mode we fill completely.
        try:
            import HammerBot as _HBchk
            if _HBchk.AUTO_AFTER_BUY[0] and self._freeCells() <= 1:
                _ub_log('[Energy] 1 slot left (hammer mode) -> stop buying')
                self._handleInventoryFull()
                return
        except:
            pass

        # PROACTIVE check: if inventory is full RIGHT NOW, stop buying
        # (was waiting 12s of stall = spam of "inventory full" messages)
        try:
            if self._freeCells() <= 0:
                self._handleInventoryFull()
                return
        except:
            pass

        if now - self._buyProgressAt > BUY_STALL:
            self._handleInventoryFull()
            return

        try:
            money = int(player.GetMoney())
        except:
            money = 0
        if money < KNIFE_PRICE + 5000:
            net.SendShopEndPacket()
            if have > 0:
                _ub_log('[Energy] out of yang -> exchange %d held' % have)
                self._setState(S_WAIT_ALCH, 'out of yang')
                self._msg('Out of yang - walk to the alchemist')
            else:
                self._msg('DINHEIRO ACABOU (%d ciclos)' % self._runsDone)
                _tel_log('=== FIM: $ ACABOU apos %d ciclos ===' % self._runsDone)
                _ub_log('[Energy] out of yang with 0 items -> stop')
                try:
                    OpenLib.AckIPC('energy', 'DINHEIRO ACABOU (%d ciclos)' % self._runsDone, True)
                except:
                    pass
                self._stopBot()
                try: self.enableEnergyBot.SetOff()
                except: pass
            return

        if now - self._lastBuyAt < self._nextBuyDelay:
            return   # humanized pacing

        self._lastBuyAt = now
        self._nextBuyDelay = self._rollNextBuyDelay()
        net.SendShopBuyPacket(BUY_SHOP_SLOT)
        free = self._freeCells()
        self._msg('Buying knives (%d)' % have)
        self._setEta(free * self._avgBuyDelay() + (have + free) * self._avgGiveDelay())

    def OnAllIn(self):
        # INF: 0 ciclos = corre para sempre (ate o yang acabar)
        try:
            self.edRuns.SetText('0')
            self._msg('INF: ciclos ilimitados')
            _ub_log('[Energy] INF: ciclos ilimitados (0)')
        except:
            pass

    def _runsTarget(self):
        # 0 = ilimitado (ate yang acabar)
        try:
            t = self.edRuns.GetText().strip()
            if t:
                v = int(t)
                if v >= 0:
                    return v
        except:
            pass
        return 0

    def _pauseEvery(self):
        # minutes between pauses; 0 = off
        try:
            t = self.edPause.GetText().strip()
            if t:
                v = int(t)
                if 0 <= v <= 600:
                    return v
        except:
            pass
        return 0

    def _pauseDurMin(self):
        try:
            t = self.edDur.GetText().strip()
            if t:
                v = int(t)
                if 1 <= v <= 120:
                    return v
        except:
            pass
        return 5

    def _pauseCheck(self):
        # called when the bot ARRIVES AT THE WEAPON DEALER (end of a cycle):
        # if it is time for a pause, enter it NOW (never mid-route)
        now = OpenLib.Monotonic()
        every = self._pauseEvery() * 60.0
        if every <= 0:
            return
        if self._nextPauseAt == 0.0:
            self._nextPauseAt = now + every * self._rollDelay(0.8, 1.2)
            return
        if self._pauseUntil > 0.0:
            return   # already pausing
        if now >= self._nextPauseAt:
            dur = self._pauseDurMin() * 60.0 * self._rollDelay(0.8, 1.2)
            self._pauseUntil = now + dur
            self._nextPauseAt = now + dur + every * self._rollDelay(0.8, 1.2)
            _ub_log('[Energy] PAUSA %.0fs no vendedor (anti-padrao, proxima em ~%d min)' % (
                dur, every / 60.0))
            try:
                self.PauseBoard.Show()
            except:
                pass

    def _pauseTick(self):
        # ACTIVE pause: blocks everything, updates the popup countdown,
        # hides it when done. Returns True while the pause lasts.
        now = OpenLib.Monotonic()
        self._updatePauseCd(now)
        if self._pauseUntil <= 0.0:
            return False
        if now < self._pauseUntil:
            left = int(self._pauseUntil - now)
            try:
                self.lPauseCountdown.SetText('Retoma em %dm %02ds' % (left // 60, left % 60))
            except:
                pass
            try:
                if not self.PauseBoard.IsShow():
                    self.PauseBoard.Show()   # popup SEMPRE visivel durante a pausa
            except:
                pass
            self._msg('PAUSA anti-padrao (%ds)' % left)
            return True
        # pause over
        self._pauseUntil = 0.0
        try:
            self.PauseBoard.Hide()
        except:
            pass
        _ub_log('[Energy] pausa terminada -> retomar')
        try:
            if self.state == S_STOP:
                self._resumeAfterPause()
        except:
            pass
        return False

    def _resumeAfterPause(self):
        # pausa terminada mas o bot estava em S_STOP ('starting in pause'):
        # sem isto ficava parado para sempre. Retoma sem reiniciar contadores.
        npcs = self._mapNpcs()
        if not npcs:
            self._msg('Left supported map - stopped')
            self._stopBot()
            try:
                self.enableEnergyBot.SetOff()
            except:
                pass
            return
        have = self._countGivable()
        if self.autoBuy and self._dist(npcs['weapon']) <= NPC_CLICK_DIST:
            self._setState(S_OPEN_SHOP, 'pos-pausa: no vendedor')
        elif self.autoBuy and self._dist(npcs['weapon']) <= NEAR_DIST:
            self._wpnTries = 0
            self._wpnStart = OpenLib.Monotonic()
            self._setState(S_GOTO_WEAPON, 'pos-pausa: caminho ao vendedor')
        elif have > 0:
            self._setState(S_WAIT_ALCH, 'pos-pausa: ir ao alquimista')
        elif self.autoBuy:
            self._setState(S_WAIT_WEAPON, 'pos-pausa: espera jogador')
        else:
            self._msg('Nada para trocar - compra primeiro')
            self._stopBot()
            try:
                self.enableEnergyBot.SetOff()
            except:
                pass
            return
        self._msg('Pausa terminada - a retomar o ciclo...')

    def _updatePauseCd(self, now):
        # live countdown in the main window: next pause / active pause / off
        try:
            if self._pauseUntil > 0.0:
                left = int(self._pauseUntil - now)
                self.lPauseCd.SetText('EM PAUSA: retoma em %dm %02ds' % (left // 60, left % 60))
            elif self._nextPauseAt > 0.0 and self._pauseEvery() > 0:
                left = int(self._nextPauseAt - now)
                if left > 0:
                    self.lPauseCd.SetText('proxima pausa em ~%dm' % (left // 60 + 1))
                else:
                    self.lPauseCd.SetText('proxima pausa: no proximo ciclo')
            else:
                self.lPauseCd.SetText('proxima pausa: desligado')
        except:
            pass

    def _dismissPause(self):
        # popup X button: just close the window (pause continues silently)
        try:
            self.PauseBoard.Hide()
        except:
            pass

    def _onPauseStop(self):
        # popup PARAR TUDO: break the cycle and stop the bot
        try:
            self.PauseBoard.Hide()
        except:
            pass
        self._pauseUntil = 0.0
        _ub_log('[Energy] PARAR TUDO clicado na pausa')
        self._msg('PARADO pelo jogador (pausa)')
        self._stopBot()
        try:
            self.enableEnergyBot.SetOff()
        except:
            pass

    

    def _keysRelease(self):
        try:
            if self._wasdHeld:
                player.OnKeyUp(self._wasdHeld)
        except:
            pass
        self._wasdHeld = 0

    def _walkStuckCheck(self, now):
        # PRESO? -> spam de WASD/setas (segurar 1 tecla por tick); se mesmo
        # assim nao sai -> funcao do ESC que solta a personagem (100% auto)
        if self._escActive:
            return True
        try:
            me = self._myPos()
            if me is None:
                return False
            if self._walkLastPos is not None:
                d = OpenLib.dist(me[0], me[1], self._walkLastPos[0], self._walkLastPos[1])
                if d < 50.0:
                    self._walkStuckN += 1
                else:
                    self._walkStuckN = 0
                    self._stuckRound = 0
                    self._escCount = 0   # voltou a andar: novo episodio tem orcamento novo de ESC
            self._walkLastPos = (me[0], me[1])

            if self._wasdHeld:
                # passou 1 tick com a tecla premida -> largar agora
                self._keysRelease()
                return True

            if self._walkStuckN >= STUCK_TICKS:
                self._walkStuckN = 0
                self._stuckRound += 1
                _tel['stuck'] += 1
                # fechar janelas modais (trade/pedidos de outros jogadores,
                # dialogs) -- bloqueiam o movimento e nem WASD nem /restart
                # resolvem enquanto estiverem abertas
                try:
                    player.OnKeyDown(1)   # ESC fecha a janela do topo
                    player.OnKeyUp(1)
                except:
                    pass
                try:
                    dc0 = eXLib.GetDialogAnswerCount()
                    if isinstance(dc0, int) and dc0 >= 2:
                        event.SelectAnswer(1, 0)
                except:
                    pass
                if self._stuckRound > WASD_ROUNDS:
                    _ub_log('[Energy] PRESO apos %d rondas WASD -> ESC LIVRE' % WASD_ROUNDS)
                    self._stuckRound = 0
                    self._escFreeStart('preso (WASD falhou)')
                    return True
                if self._stuckRound == 1:
                    try:
                        _ub_log('[Energy] PRESO info: pos=(%d,%d) dead=%s money=%d' % (
                            me[0], me[1],
                            eXLib.IsDead(player.GetMainCharacterIndex()),
                            int(player.GetMoney())))
                    except:
                        pass
                    self._dismount()   # nudge comprovado (Alt+G) na 1a ronda
                # 1) escapar por uma ROTA GRAVADA (corredor comprovado):
                #    waypoint mais proximo duma rota escolhida ao acaso
                if not self._routeEscapeStep(me):
                    # 2) sem rotas -> nudge REAL aleatorio curto
                    # ZONAS: o nudge tem de cair em area LIVRE/NAO MARCADA
                    try:
                        import math as _m
                        for _try in range(10):
                            ang = self._rollDelay(0.0, 2.0 * _m.pi)
                            nx = me[0] + 300 * _m.cos(ang)
                            ny = me[1] + 300 * _m.sin(ang)
                            if self._zoneOK(nx, ny):
                                chr.MoveToDestPosition(player.GetMainCharacterIndex(),
                                    int(nx), int(ny))
                                break
                    except:
                        pass
                # WASD sintetico (melhor esforco; excecoes ficam registadas)
                k = -1
                try:
                    k = _rnd_choice(WASD_KEYS)
                    player.OnKeyDown(k)
                    self._wasdHeld = k
                except Exception as _we:
                    try:
                        _ub_log('[Energy] WASD ERR ronda %d (DIK %d): %r' % (self._stuckRound, k, _we))
                    except:
                        pass
                _ub_log('[Energy] PRESO -> WASD ronda %d (DIK %d)' % (self._stuckRound, k))
                self._msg('PRESO -> WASD (%d/%d)' % (self._stuckRound, WASD_ROUNDS))
                return True
        except:
            pass
        return False

    def _dismount(self):
        try:
            _ub_log('[Energy] dismount escape (Alt+G)')
            player.OnKeyDown(DIK_LALT)
            player.OnKeyDown(DIK_G)
            player.OnKeyUp(DIK_G)
            player.OnKeyUp(DIK_LALT)
            import math as _m
            try:
                px, py, pz = player.GetMainCharacterPosition()
                # ZONAS: nudge so para area permitida (livre/nao marcada)
                for _try in range(10):
                    ang = self._rollDelay(0.0, 2.0 * _m.pi)
                    nx = px + 300 * _m.cos(ang)
                    ny = py + 300 * _m.sin(ang)
                    if self._zoneOK(nx, ny):
                        chr.MoveToDestPosition(player.GetMainCharacterIndex(),
                            int(nx), int(ny))
                        break
            except:
                pass
        except:
            pass

    def _escFreeStart(self, reason):
        # manda o mesmo comando que o botao do menu ESC "soltar a personagem";
        # testa os candidatos ate a posicao saltar (personagem libertada)
        if self._escActive:
            return
        self._escCount += 1
        if self._escCount > ESC_MAX_PER_SESSION:
            _ub_log('[Energy] ESC livre x%d sem sucesso -> PARAR (deadlock)' % self._escCount)
            self._msg('PRESO: nem WASD nem ESC livre')
            try:
                OpenLib.AckIPC('energy', 'PRESO para sempre (WASD + ESC falharam)', True)
            except:
                pass
            self._stopBot()
            try:
                self.enableEnergyBot.SetOff()
            except:
                pass
            return
        self._escActive = True
        self._escReason = reason
        self._escCmdIdx = 0
        self._escTickN = 0
        self._escPos = self._myPos()
        self._escHopAt = 0.0
        self._escHopOk = False
        self._keysRelease()
        self._msg('ESC LIVRE: a soltar a personagem...')
        _ub_log('[Energy] ESC LIVRE #%d (%s)' % (self._escCount, reason))
        _tel_log('ESC_LIVRE #%d (%s)' % (self._escCount, reason))

    def _escSuccess(self):
        # personagem libertada (teleporte OU relog por troca de canal):
        # retoma o ciclo sozinho a partir de onde estiver
        _ub_log('[Energy] ESC LIVRE: personagem solta -> retomar ciclo')
        _tel_log('ESC_LIVRE OK (cmd %d)' % self._escCmdIdx)
        self._escActive = False
        self._escPos = None
        self._escCount = 0   # sucesso: episodio fechado, budget limpo
        self._escHopAt = 0.0
        self._escHopOk = False
        self._playRoute = None
        self._recRoute = None
        self._walkStuckN = 0
        self._stuckRound = 0
        try:
            if shop.IsOpen():
                net.SendShopEndPacket()
        except:
            pass
        self._wpnTries = 0
        self._alchTries = 0
        self._wpnStart = OpenLib.Monotonic()
        self._setState(S_GOTO_WEAPON, 'esc livre: voltar ao vendedor')
        self._msg('SOLTO! A voltar ao vendedor...')

    def _escFreeTick(self):
        me = self._myPos()
        if me is None:
            return
        # sucesso por salto de posicao (teleporte / restart)
        if self._escPos is not None:
            if OpenLib.dist(me[0], me[1], self._escPos[0], self._escPos[1]) > ESC_TELEPORT_DIST:
                self._escSuccess()
                return
        self._escTickN += 1
        # fase 1: comandos de chat (o que o botao do menu ESC manda)
        if self._escCmdIdx < len(ESC_CMDS):
            if self._escTickN % ESC_CMD_TICKS == 0:
                cmd = ESC_CMDS[self._escCmdIdx]
                self._escCmdIdx += 1
                try:
                    net.SendChatPacket(cmd)
                    _ub_log('[Energy] ESC LIVRE: %s' % cmd)
                except:
                    pass
                self._escPos = self._myPos()
            self._msg('ESC LIVRE: a soltar (%d/%d)...' % (self._escCount, ESC_MAX_PER_SESSION))
            return
        # fase 2: comandos esgotados -> RELOG por troca de canal: recarrega o
        # mundo e re-sincroniza a posicao no servidor (soltar garantido)
        if self._escHopAt == 0.0:
            ok = False
            try:
                import ChannelSwitch as _CS
                ok = _CS.next()
            except Exception as _ce:
                try:
                    _ub_log('[Energy] canal ERR: %r' % _ce)
                except:
                    pass
            self._escHopAt = OpenLib.Monotonic()
            self._escHopOk = bool(ok)
            _ub_log('[Energy] ESC LIVRE: troca de canal (%s)' % ('emitida' if ok else 'indisponivel'))
            if ok:
                self._msg('RELOG: a trocar de canal...')
            return
        hopAge = OpenLib.Monotonic() - self._escHopAt
        if self._escHopOk:
            try:
                settled = OpenLib.WorldSettled()
            except:
                settled = True
            if settled and hopAge > 20.0:
                # mundo recarregado no outro canal -> personagem solta
                _ub_log('[Energy] ESC LIVRE: canal trocado (%.0fs) -> retomar' % hopAge)
                self._escSuccess()
                return
            if hopAge > 90.0:
                # a troca nao chegou -> nova ronda completa (chat + canal)
                self._escActive = False
                self._escFreeStart('ESC livre: nova tentativa')
        else:
            if hopAge > 20.0:   # espera o cooldown (15s) do ChannelSwitch passar
                self._escActive = False
                self._escFreeStart('ESC livre: sem canal, nova tentativa')
        self._msg('RELOG: a soltar (%d/%d)...' % (self._escCount, ESC_MAX_PER_SESSION))

    def _wanderAndFindNpc(self, npc_type, npc_pos):
        # Estado para andar aleatoriamente pelo mapa ate encontrar o NPC novamente
        # Ou ate pedir para o utilizador andar manualmente
        self._wanderState = getattr(self, '_wanderState', 0)
        self._wanderTicks = getattr(self, '_wanderTicks', 0)
        self._wanderTargetNpc = npc_type
        self._wanderTargetPos = npc_pos
        
        # Mudar para estado WANDER
        self._setState(S_WANDER, 'wandering to find %s' % npc_type)
        
        # Verificar se NPC esta visivel agora
        race = WEAPON_RACE if npc_type == 'weapon' else ALCHEMIST_RACE
        vid = OpenLib.GetInstanceByID(race)
        
        if vid >= 0:
            _ub_log('[Energy] NPC %s encontrado durante wander!' % npc_type)
            self._wanderState = 0
            self._wanderTicks = 0
            # Voltar ao estado appropriate
            if npc_type == 'weapon':
                self._setState(S_GOTO_WEAPON, 'found weapon NPC')
            else:
                self._setState(S_GOTO_ALCH, 'found alch NPC')
            return
        
        self._wanderTicks += 1
        
        # Apos 60 ticks (~24 segundos) sem encontrar NPC, tentar caminho aleatorio
        if self._wanderTicks % 60 == 0:
            me = self._myPos()
            if me:
                tgt = self._zoneRandomTarget(me, 500, 1500)
                if tgt:
                    _ub_log('[Energy] wander: a andar para (%d, %d)' % (tgt[0], tgt[1]))
                    Movement.GoToPositionAvoidingObjects(tgt[0], tgt[1], 300)
        
        # Apos muitas tentativas sem sucesso, pedir para o utilizador andar manualmente
        if self._wanderTicks > 180: # ~72 segundos
            _ub_log('[Energy] wander timeout -> pedir movimento manual')
            self._manualFallback(npc_type)
        else:
            self._msg('Procurando NPC... (%d)' % (180 - self._wanderTicks))
    
    def _manualFallback(self, npc_type):
        # 100% automatico: em vez de parar e pedir movimento manual, usa a
        # funcao do menu ESC que solta a personagem e retoma o ciclo sozinho
        _ub_log('[Energy] recuperacao automatica: ESC LIVRE (target %s)' % npc_type)
        self._wanderTicks = 0
        self._wanderState = 0
        self._escFreeStart('wander falhou (%s)' % npc_type)
    
    def _wanderTick(self):
        # REC MANUAL ligado -> esperar o jogador em vez de andar as voltas
        if self.recManual:
            npc_type = getattr(self, '_wanderTargetNpc', 'weapon')
            self._setState(S_WAIT_WEAPON if npc_type == 'weapon' else S_WAIT_ALCH,
                'rec-manual: espera o jogador andar')
            return
        # Tentar encontrar o NPC enquanto o jogador pode andar manualmente
        npc_type = getattr(self, '_wanderTargetNpc', None)
        npc_pos = getattr(self, '_wanderTargetPos', None)
        
        if not npc_type or not npc_pos:
            _ub_log('[Energy] wander sem target -> voltar')
            self._setState(S_WAIT_WEAPON)
            return
        
        race = WEAPON_RACE if npc_type == 'weapon' else ALCHEMIST_RACE
        vid = OpenLib.GetInstanceByID(race)
        
        if vid >= 0:
            _ub_log('[Energy] wander: NPC %s encontrado!' % npc_type)
            self._msg('NPC encontrado! A continuar...')
            # Voltar ao estado appropriate
            if npc_type == 'weapon':
                self._setState(S_GOTO_WEAPON)
            else:
                self._setState(S_GOTO_ALCH)
            return
        
        # Continuar a procurar
        self._wanderTicks = getattr(self, '_wanderTicks', 0) + 1
        
        # Tentar andar um pouco a cada 60 ticks
        if self._wanderTicks % 60 == 0:
            me = self._myPos()
            if me:
                tgt = self._zoneRandomTarget(me, 500, 2000)
                if tgt:
                    _ub_log('[Energy] wander: a andar para (%d, %d)' % (tgt[0], tgt[1]))
                    Movement.GoToPositionAvoidingObjects(tgt[0], tgt[1], 300)
                self._msg('Procurando NPC... (%d)' % self._wanderTicks)
        
        # Timeout: apos ~2 minutos de procura, pedir para o utilizador andar manualmente
        if self._wanderTicks > 240:
            _ub_log('[Energy] wander timeout -> pedir movimento manual')
            self._manualFallback(npc_type)
    
    def _zoneRandomTarget(self, me, dmin, dmax):
        # ZONAS: ponto aleatorio ao redor da posicao atual, mas SO em area
        # LIVRE/NAO MARCADA (nunca zona morta). Com zonas livres definidas,
        # as primeiras tentativas preferem-nas. None se nao conseguiu.
        import math as _m
        wantFree = self._zoneHasFree()
        for _try in range(12):
            ang = self._rollDelay(0.0, 2.0 * _m.pi)
            dist = self._rollDelay(dmin, dmax)
            tx = int(me[0] + _m.cos(ang) * dist)
            ty = int(me[1] + _m.sin(ang) * dist)
            if not self._zoneOK(tx, ty):
                continue
            if wantFree and not self._zoneFree(tx, ty) and _try < 8:
                continue
            return (tx, ty)
        return None

    def _distToVid(self, vid):
        try:
            mx, my, mz = player.GetMainCharacterPosition()
            x, y, z = eXLib.GetPixelPosition(vid)
            import math as _m
            return _m.sqrt((x - mx)**2 + (y - my)**2)
        except:
            return 99999.0

    def _gotoWeaponTick(self, wp):
        self._recTick()   # gravar SEMPRE -- inclui resgates manuais do jogador
        # REC MANUAL ligado a meio da caminhada -> esperar o jogador
        if self.recManual:
            self._playRoute = None
            self._setState(S_WAIT_WEAPON, 'rec-manual: espera o jogador andar')
            return
        # preso? -> WASD; pior caso -> ESC livre
        if self._walkStuckCheck(OpenLib.Monotonic()):
            return
        wvid = OpenLib.GetInstanceByID(WEAPON_RACE)
        if wvid >= 0:
            wd = self._distToVid(wvid)
            if wd > NPC_CLICK_DIST:
                # NPC visible but TOO FAR to click: keep walking to it
                try:
                    x, y, z = eXLib.GetPixelPosition(wvid)
                    self._walkSmart(OpenLib.Monotonic(), self._myPos(), x, y)
                except:
                    pass
                self._msg('a aproximar ao vendedor (%d)...' % int(wd))
                return
            _ub_log('[Energy] cheguei ao vendedor (%dpx) -> comprar' % int(wd))
            _tel['click_dist'] = int(wd)
            self._recFinish()   # rota concluida com chegada -> GRAVAR
            self._pauseCheck()
            if self._pauseUntil > 0.0:
                return
            self._setState(S_OPEN_SHOP, 'back at dealer')
            self._msg('A comprar (ciclo %d)' % (self._runsDone + 1))
            return
        now = OpenLib.Monotonic()
        if now - self._wpnStart > 480.0 or now < self._wpnStart:
            _ub_log('[Energy] 8min sem chegar ao vendedor -> ESC LIVRE')
            self._msg('PRESO no caminho -> ESC livre...')
            self._escFreeStart('timeout vendedor')
            return
        # 1) ROTA GRAVADA AO ACASO (com jitter)
        if self._playRoute:
            if not self._routeWalkTick():
                # rota acabou/foi trocada -> pegar OUTRA logo (pode vir do
                # outro pool: normal -> emergencia / emergencia -> normal)
                self._playRoute = self._routePick('to_weapon')
                self._playIdx = 0
            self._msg('a voltar ao vendedor (rota random)...')
            return
        # 2) LEARNED PATH if available
        if PathRunner is not None and PathRunner.hasLearnedPath():
            # LEARNED PATH available: use it (exact route, no pathfinding)
            try:
                pr = PathRunner.instance
                if not pr.isRunning():
                    pr._msg_cb = self._msg
                    pr.walkBack(self._onArrivedDealer)
                self._msg('a voltar ao vendedor (rota)...')
                return
            except:
                pass
        # 3) pathfinding (falhou 6x -> wander; wander falhar -> ESC livre)
        rc = Movement.GoToPositionAvoidingObjects(int(wp[0]), int(wp[1]), 300)
        if rc == Movement.NO_PATH_FOUND:
            self._wpnTries += 1
            if self._wpnTries > 6:
                _ub_log('[Energy] sem caminho -> wander / ESC livre')
                self._wpnTries = 0
                self._wanderAndFindNpc('weapon', wp)
                return
        self._msg('a voltar ao vendedor... (ciclo %d)' % (self._runsDone + 1))

    def _onArrivedAlch(self):
        _ub_log('[Energy] rota: chegada ao alquimista')
        self._recFinish()
        self._beginGivePhase()

    def _onArrivedDealer(self):
        _ub_log('[Energy] rota: chegada ao vendedor')
        self._recFinish()
        self._pauseCheck()
        if self._pauseUntil > 0.0:
            return
        self._setState(S_OPEN_SHOP, 'rota: at dealer')
        self._msg('A comprar (ciclo %d)' % (self._runsDone + 1))

    def _onYangGained(self, amount):
        try:
            _ub_log('[Energy] YANG: +%d' % amount)
        except:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBeep(0)
        except:
            pass
        try:
            OpenLib.AckIPC('energy', 'YANG +%d' % amount, True)
        except:
            pass
        try:
            if amount >= 100000:
                if amount >= 1000000:
                    txt = '[MT2Robs] +%.1fM yang' % (amount / 1000000.0)
                else:
                    txt = '[MT2Robs] +%dk yang' % (amount // 1000)
                net.SendChatPacket(txt)
        except:
            pass

    def _gotoAlchTick(self, alch):
        self._recTick()   # gravar SEMPRE -- inclui resgates manuais do jogador
        # REC MANUAL ligado a meio da caminhada -> esperar o jogador
        if self.recManual:
            self._playRoute = None
            self._setState(S_WAIT_ALCH, 'rec-manual: espera o jogador andar')
            return
        # preso? -> WASD; pior caso -> ESC livre
        if self._walkStuckCheck(OpenLib.Monotonic()):
            return
        avid = OpenLib.GetInstanceByID(ALCHEMIST_RACE)
        if avid >= 0:
            ad = self._distToVid(avid)
            if ad > ALCH_GIVE_TRY:
                # too far to exchange: walk to an OFFSET point near the NPC
                # (not directly AT it -- the NPC is solid, walking into it
                # makes the char orbit in circles)
                try:
                    x, y, z = eXLib.GetPixelPosition(avid)
                    me = self._myPos()
                    if me is not None:
                        import math as _m
                        dx = x - me[0]
                        dy = y - me[1]
                        n = _m.sqrt(dx*dx + dy*dy) or 1.0
                        # target: punto a 480-580px DO NPC (na nossa direcao)
                        # -- mais longe = menos trades/miscliques dos outros
                        stand = int(self._rollDelay(ALCH_STAND_MIN, ALCH_STAND_MAX))
                        tx = int(x - dx/n * stand)
                        ty = int(y - dy/n * stand)
                        self._walkSmart(OpenLib.Monotonic(), me, tx, ty)
                except:
                    pass
                self._msg('a aproximar ao alquimista (%d)...' % int(ad))
                return
            if ad < ALCH_STAND_MIN:
                # MUITO PERTO do alquimista: recuar para o anel 480-580px
                # antes de trocar (os outros nao andam a abrir trade)
                self._backoffN = getattr(self, '_backoffN', 0) + 1
                if self._backoffN <= 8:
                    try:
                        x, y, z = eXLib.GetPixelPosition(avid)
                        me = self._myPos()
                        if me is not None:
                            import math as _m
                            dx = x - me[0]
                            dy = y - me[1]
                            n = _m.sqrt(dx*dx + dy*dy) or 1.0
                            stand = int(self._rollDelay(ALCH_STAND_MIN, ALCH_STAND_MAX))
                            self._walkSmart(OpenLib.Monotonic(), me,
                                int(x - dx/n * stand), int(y - dy/n * stand))
                    except:
                        pass
                    self._msg('a afastar do alquimista (%d)...' % int(ad))
                    return
            self._backoffN = 0
            _ub_log('[Energy] alquimista ao alcance (%dpx) -> trocar' % int(ad))
            self._recFinish()   # rota concluida com chegada -> GRAVAR
            try:
                _tel_log('ALCH: %dpx, caminho %.0fs' % (int(ad), OpenLib.Monotonic() - _tel['walk_alch']))
            except:
                pass
            self._beginGivePhase()
            return
        # 2) give-up guards
        now = OpenLib.Monotonic()
        if now - self._alchStart > 480.0:
            _ub_log('[Energy] 8min sem chegar ao alquimista -> ESC LIVRE')
            self._msg('PRESO no caminho -> ESC livre...')
            self._escFreeStart('timeout alquimista')
            return
        # 3) walk: ROTA GRAVADA AO ACASO primeiro (com jitter)
        if self._playRoute:
            if not self._routeWalkTick():
                # rota acabou/foi trocada -> pegar OUTRA logo (pode vir do
                # outro pool: normal -> emergencia / emergencia -> normal)
                self._playRoute = self._routePick('to_alch')
                self._playIdx = 0
            self._msg('a andar para o alquimista (rota random)...')
            return
        if PathRunner is not None and PathRunner.hasLearnedPath():
            try:
                pr = PathRunner.instance
                if not pr.isRunning():
                    pr._msg_cb = self._msg
                    pr.walkTo('alchemist', self._onArrivedAlch)
                self._msg('a andar para o alquimista (rota)...')
                return
            except:
                pass
        rc = Movement.GoToPositionAvoidingObjects(int(alch[0]), int(alch[1]), 300)
        if rc == Movement.NO_PATH_FOUND:
            self._alchTries += 1
            if self._alchTries > 6:
                # wander; se falhar -> ESC livre (automatico)
                _ub_log('[Energy] sem caminho -> wander / ESC livre')
                self._alchTries = 0
                self._wanderAndFindNpc('alchemist', alch)
                return
        self._msg('a andar para o alquimista...')

    def _handleInventoryFull(self):
        have = self._countGivable()
        try:
            _tel['knives'] = have
        except:
            pass
        net.SendShopEndPacket()
        # HAMMER AFK LOOP: buy (minus one slot) -> hammer all -> buy again -> ...
        try:
            import HammerBot as _HB
            if _HB.AUTO_AFTER_BUY[0]:
                if have <= 0:
                    _ub_log('[Energy] inventory full but no knives (fragments?) -> loop stopped')
                    self._msg('Inventario cheio de fragmentos - esvazia')
                    try: OpenLib.AckIPC('energy', 'inventario cheio de fragmentos', True)
                    except: pass
                    self._stopBot()
                    try: self.enableEnergyBot.SetOff()
                    except: pass
                    return
                _ub_log('[Energy] hammer loop -> breaking %d knives here' % have)
                self._msg('MARTELO: a partir %d facas' % have)
                self.autoBuy = True   # keep the loop armed
                try: self.buyKnivesBtn.SetOn()
                except: pass
                _HB.instance.RunWith(list(ALL_GIVABLE_ITEMS))
                self._setState(S_WAIT_HAMMER, 'hammering')
                return
        except:
            pass
        # normal (alchemist) path
        if self.autoBuy:
            self.autoBuy = False
            try: self.buyKnivesBtn.SetOff()
            except: pass
            _ub_log('[Energy] inventory full (%d items) -> auto-knives OFF' % have)
            try: OpenLib.AckIPC('energy', 'inventario cheio (%d) - vai ao alquimista' % have, True)
            except: pass
        # AUTO-WALK to the alchemist (no more 'GO TO ALQUIMISTA' -- the bot
        # goes by itself; failure -> ack -> the panel beeps)
        self._alchTries = 0
        self._alchStart = OpenLib.Monotonic()
        self._msg('A IR ao alquimista (%d itens)...' % have)
        _ub_log('[Energy] a andar para o alquimista sozinho')
        try:
            OpenLib.AckIPC('energy', 'inventario cheio - a ir ao alquimista', True)
        except:
            pass
        self._setState(S_GOTO_ALCH, 'inventory full, walking')

    # ------------------------------------------------- position + give ----
    def _beginPositioning(self, alch):
        self._posTries = 0
        self._newSpot(alch)

    def _newSpot(self, alch):
        self._posTarget = self._rollSpotNear(alch)
        self._posTries += 1
        _ub_log('[Energy] random spot #%d: (%d,%d) dist=%d' % (
            self._posTries, self._posTarget[0], self._posTarget[1], self._dist(self._posTarget)))
        self._setState(S_POSITION, 'roll spot')

    def _positionTick(self, alch):
        t = self._posTarget
        if t is None:
            self._beginGivePhase()
            return
        if OpenLib.isPlayerCloseToPosition(t[0], t[1], POS_ARRIVE):
            _ub_log('[Energy] positioned at (%d,%d)' % (t[0], t[1]))
            Movement.StopMovement()
            self._beginGivePhase()
            return
        rc = Movement.GoToPositionAvoidingObjects(t[0], t[1])
        if rc == Movement.NO_PATH_FOUND:
            if self._posTries >= POS_MAX_TRIES:
                # no reachable spot rolled -> just exchange from where you stand
                _ub_log('[Energy] no path after %d tries -> exchange from current spot' % self._posTries)
                self._beginGivePhase()
            else:
                _ub_log('[Energy] no path to spot -> re-roll')
                self._newSpot(alch)

    def _beginGivePhase(self):
        # human-like: stand a moment before starting to exchange
        self._lastGiveAt = OpenLib.GetTime()
        self._nextGiveDelay = self._rollDelay(FIRST_DELAY_MIN, FIRST_DELAY_MAX)
        self._giveLastCount = 999
        self._giveStallN = 0
        self._giveLostN = 0
        self._giveStallCyc = 0
        self._setState(S_GIVE)
        self._msg('Exchanging')

    def _giveTick(self):
        try:
            cur_money = int(player.GetMoney())
            if not hasattr(self, '_prevMoney'):
                self._prevMoney = cur_money
            elif cur_money > self._prevMoney:
                gained = cur_money - self._prevMoney
                self._prevMoney = cur_money
                if gained > 1000:
                    self._onYangGained(gained)
            else:
                self._prevMoney = cur_money
        except:
            pass

        vid = OpenLib.GetInstanceByID(ALCHEMIST_RACE)
        if vid < 0:
            # alquimista fora de vista durante a troca (ex: fomos soltos /
            # teleportados) -> voltar a caminhar ate ele (modo 100% auto)
            self._giveLostN = getattr(self, '_giveLostN', 0) + 1
            if self._giveLostN > 15:
                self._giveLostN = 0
                _ub_log('[Energy] alquimista fora de vista no GIVE -> GOTO_ALCH')
                self._alchTries = 0
                self._alchStart = OpenLib.Monotonic()
                self._setState(S_GOTO_ALCH, 'give: alch fora de vista')
                return
            self._msg('aproxima mais do alquimista')
            return
        self._giveLostN = 0

        # STALL: ha facas mas o numero nao desce ha ~20s -> janela modal
        # (trade pedido por outro jogador / dialog) a bloquear as trocas
        # -> fechar e insistir (igual ao desencalhe das caminhadas)
        try:
            have_now = self._countGivable()
            if have_now > 0:
                if have_now < getattr(self, '_giveLastCount', 999):
                    self._giveLastCount = have_now
                    self._giveStallN = 0
                else:
                    self._giveStallN = getattr(self, '_giveStallN', 0) + 1
                    if self._giveStallN >= 50:   # ~20s sem trocar nada
                        self._giveStallN = 0
                        _ub_log('[Energy] GIVE travado (%d facas) -> fechar modais' % have_now)
                        try:
                            player.OnKeyDown(1)   # ESC fecha a janela do topo
                            player.OnKeyUp(1)
                        except:
                            pass
                        try:
                            dcg = eXLib.GetDialogAnswerCount()
                            if isinstance(dcg, int) and dcg >= 2:
                                event.SelectAnswer(1, 0)
                        except:
                            pass
                        try:
                            _ub_log('[Energy] GIVE stall info: dead=%s' % (
                                eXLib.IsDead(player.GetMainCharacterIndex()),))
                        except:
                            pass
                        # se o servidor recusou por DISTANCIA -> aproximar
                        # sozinho ao anel 480-580 e voltar a tentar
                        try:
                            av = OpenLib.GetInstanceByID(ALCHEMIST_RACE)
                            if av >= 0:
                                x, y, z = eXLib.GetPixelPosition(av)
                                me = self._myPos()
                                if me is not None:
                                    import math as _m
                                    dx = x - me[0]
                                    dy = y - me[1]
                                    nd = _m.sqrt(dx*dx + dy*dy) or 1.0
                                    stand = int(self._rollDelay(ALCH_STAND_MIN, ALCH_STAND_MAX))
                                    self._walkSmart(OpenLib.Monotonic(), me,
                                        int(x - dx/nd * stand), int(y - dy/nd * stand))
                                    _ub_log('[Energy] GIVE stall: a aproximar ao anel (%dpx)' % int(nd))
                        except:
                            pass
                        # sem progresso ha muitos ciclos -> caminhar de novo
                        # ate ao alquimista (com desencalhe completo)
                        self._giveStallCyc = getattr(self, '_giveStallCyc', 0) + 1
                        if self._giveStallCyc >= 6:
                            self._giveStallCyc = 0
                            _ub_log('[Energy] GIVE parado 6 ciclos -> GOTO_ALCH')
                            self._alchTries = 0
                            self._alchStart = OpenLib.Monotonic()
                            self._setState(S_GOTO_ALCH, 'give: aproximar de novo')
                            return
            else:
                self._giveStallN = 0
        except:
            pass
        # the give packet works from ~600px: if we can SEE the NPC we can
        # probably exchange (the server validates the real range)
        now = OpenLib.GetTime()
        if now - self._lastGiveAt < self._nextGiveDelay:
            return   # humanized pacing
        slot = self._nextGivableSlot()
        if slot < 0:
            self._clearEta()
            self._runsDone += 1
            tgt = self._runsTarget()
            if tgt == 0 or self._runsDone < tgt:
                # LOOP: back to the dealer for another round
                _ub_log('[Energy] ciclo %d completo -> repetir (modo %s)' % (
                    self._runsDone, 'ate $ acabar' if tgt == 0 else '%d/%d' % (self._runsDone, tgt)))
                _tel_summary(self._runsDone)
                # GC RESET: 27 cycles of dialog/shop open-close churn corrupts
                # the Python heap (0xc0000005 after ~8 cycles). Force a full
                # collect between cycles to clear the dangling refs.
                try:
                    import gc
                    gc.collect()
                except:
                    pass
                self.autoBuy = True
                try:
                    self.buyKnivesBtn.SetOn()
                except:
                    pass
                self._wpnTries = 0
                self._wpnStart = OpenLib.Monotonic()
                npcs3 = self._mapNpcs()
                if npcs3 and self._dist(npcs3['weapon']) <= NEAR_DIST:
                    self._pauseCheck()   # pausa so comeca AQUI (fim de ciclo no vendedor)
                    if self._pauseUntil > 0.0:
                        return   # entering pause now: do not start buying yet
                    self._setState(S_OPEN_SHOP, 'loop: buy again')
                    self._msg('A comprar (ciclo %d)' % (self._runsDone + 1))
                else:
                    self._setState(S_GOTO_WEAPON, 'loop: walking back')
                    self._msg('A VOLTAR ao vendedor (ciclo %d)...' % (self._runsDone + 1))
                return
            self._msg('Done (%d ciclos)' % self._runsDone)
            _ub_log('[Energy] run complete (%d ciclos)' % self._runsDone)
            self._stopBot()
            try: self.enableEnergyBot.SetOff()
            except: pass
            return
        self._lastGiveAt = now
        self._nextGiveDelay = self._rollNextGiveDelay()
        left = len(self._givableSlots())
        self._msg('Exchanging (%d left)' % left)
        self._setEta(left * self._avgGiveDelay())
        net.SendGiveItemPacket(vid, player.SLOT_TYPE_INVENTORY, slot, player.GetItemCount(slot))
        OpenLib.skipAnswers([0, 0], True)   # confirm the give (client-side dialog answer)
        self._questHooked = True

    def _waitHammerTick(self):
        # AFK hammer loop: while HammerBot runs -> show progress; when it stops
        # with knives still around -> re-arm it; when all knives are gone ->
        # buy again (at the dealer) or wait for you to walk back to the dealer
        try:
            import HammerBot as _HB
            hb = getattr(_HB, 'instance', None)
            have = self._countGivable()
            if hb is not None and hb.running:
                self._msg('Martelo a partir (%d facas)' % have)
                return
            if have > 0:
                # hammer stopped but knives remain -> nudge it again
                _ub_log('[Energy] hammer stalled with %d knives -> restarting' % have)
                _HB.instance.RunWith(list(ALL_GIVABLE_ITEMS))
                return
            npcs = self._mapNpcs()
            if npcs and self._dist(npcs['weapon']) <= NEAR_DIST:
                _ub_log('[Energy] hammer done -> buying again (AFK loop)')
                self._setState(S_OPEN_SHOP, 'hammer done, buying again')
                self._msg('A comprar de novo')
            else:
                self._setState(S_WAIT_WEAPON, 'hammer done, walk to dealer')
                self._msg('Vai ao vendedor para recomecar')
        except:
            pass

    def _rebuildWindow(self):
        wasShown = False
        try: wasShown = self.Board.IsShow()
        except: pass
        try: self.Board.Hide()
        except: pass
        for a in ('Board', 'lInfo', 'lEta', 'buyKnivesBtn', 'enableEnergyBot'):
            try: setattr(self, a, None)
            except: pass
        self.BuildWindow()
        if wasShown:
            try: self.Board.Show()
            except: pass


# reload-safe: on RELOAD the singleton still exists -> just rebind its class
try:
    instance
    instance.__class__ = EnergyBot
except NameError:
    instance = EnergyBot()






