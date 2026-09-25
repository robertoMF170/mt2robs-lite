# -*- coding: utf-8 -*-
import sys

# ============================================================
# DEBUG: PathRunner initialization start
# ============================================================

# Define early log (before eXLib is available)
def _ub_log(text):
    try:
        from datetime import datetime
        stamp = datetime.now().strftime('%H:%M:%S')
        # Try to use eXLib.PATH if available, otherwise use sys.path[0]
        try:
            log_path = eXLib.PATH + 'syserr_ub.txt'
        except:
            log_path = sys.path[0] + '\\syserr_ub.txt' if sys.path else 'syserr_ub.txt'
        f = open(log_path, 'a')
        f.write('[%s] %s\n' % (stamp, text))
        f.close()
    except:
        pass

_ub_log('[PathRunner] DEBUG: init start')

# Import builtins safely (Python 2/3 compat)
try:
    import builtins as __builtin__
    _ub_log('[PathRunner] DEBUG: builtins imported OK')
except Exception as e:
    _ub_log('[PathRunner] DEBUG ERR: builtins import failed: %s' % e)
    import __builtin__

# JSON import
try:
    import json
    _ub_log('[PathRunner] DEBUG: json imported OK')
except ImportError:
    try:
        import simplejson as json
        _ub_log('[PathRunner] DEBUG: simplejson imported OK')
    except ImportError:
        class DummyJson:
            def loads(self, s): return {}
            def dumps(self, o): return "{}"
        json = DummyJson()
        _ub_log('[PathRunner] DEBUG: Using DummyJson (no json module)')

import __builtin__ as buildin

# Force global recognition
try:
    sys.modules['PathRunner'] = sys.modules[__name__]
    _ub_log('[PathRunner] DEBUG: sys.modules["PathRunner"] = %s' % sys.modules['PathRunner'])
except Exception as e:
    _ub_log('[PathRunner] DEBUG ERR: sys.modules["PathRunner"] failed: %s' % e)

try:
    __builtin__.PathRunner = sys.modules[__name__]
    _ub_log('[PathRunner] DEBUG: __builtin__.PathRunner set OK')
except Exception as e:
    _ub_log('[PathRunner] DEBUG ERR: __builtin__.PathRunner failed: %s' % e)

PathRunner = sys.modules[__name__]
_ub_log('[PathRunner] DEBUG: PathRunner = %s' % PathRunner)


def HasArguments(module, attrlist):
    for attr in attrlist:
        if not buildin.hasattr(module, attr):
            return False
    return True

_ub_log('[PathRunner] DEBUG: scanning sys.modules for game modules...')
for modulename, module in iter(sys.modules.items()):
    if HasArguments(module, ['GetPlayTime']):
        player = module
        _ub_log('[PathRunner] DEBUG: found player module: %s' % modulename)
    if HasArguments(module, ['GetNameByVID']):
        chr = module
        _ub_log('[PathRunner] DEBUG: found chr module: %s' % modulename)
    if HasArguments(module, ['DirectEnter']):
        net = module
        _ub_log('[PathRunner] DEBUG: found net module: %s' % modulename)
    if HasArguments(module, ['SetCameraMaxDistance']):
        app = module
        _ub_log('[PathRunner] DEBUG: found app module: %s' % modulename)
    if HasArguments(module, ['GetCurrentMapName']):
        background = module
        _ub_log('[PathRunner] DEBUG: found background module: %s' % modulename)
    if HasArguments(module, ['SelectAnswer']):
        event = module
        _ub_log('[PathRunner] DEBUG: found event module: %s' % modulename)
    if HasArguments(module, ['ScriptWindow']):
        ui = module
        _ub_log('[PathRunner] DEBUG: found ui module: %s' % modulename)

try:
    import eXLib, UIComponents, OpenLib
    _ub_log('[PathRunner] DEBUG: eXLib, UIComponents, OpenLib imported OK')
except Exception as e:
    eXLib = None
    UIComponents = None
    OpenLib = None
    _ub_log('[PathRunner] DEBUG ERR: eXLib/UIComponents/OpenLib import failed: %s' % e)

try:
    import ZoneGuard
    _ub_log('[PathRunner] DEBUG: ZoneGuard imported OK')
except Exception as e:
    ZoneGuard = None
    _ub_log('[PathRunner] DEBUG: ZoneGuard import failed: %s' % e)

try:
    import random
except:
    pass

try:
    PATH_FILE = eXLib.PATH + 'MT2Robs/Saves/learned_path_%s.txt'
    _ub_log('[PathRunner] DEBUG: PATH_FILE = %s' % PATH_FILE)
except:
    PATH_FILE = 'MT2Robs/Saves/learned_path_%s.txt'
    _ub_log('[PathRunner] DEBUG: eXLib.PATH not available, using relative PATH_FILE')

WEAPON_RACE = 9001
ALCHEMIST_RACE = 20001
WAYPOINT_EVERY = 1.0
WAYPOINT_MIN_DIST = 150
NPC_DETECT_RANGE = 1000
BUY_SHOP_SLOT = 4
try:
    DIK_SPACE = getattr(app, 'DIK_SPACE', 57)
except:
    DIK_SPACE = 57


# ZONAS: helpers (True = pode andar/gravar ai; zona morta -> False)
def _zoneOK(x, y):
    try:
        if ZoneGuard is None:
            return True
        return ZoneGuard.Allowed(x, y, str(background.GetCurrentMapName()))
    except:
        return True


def _zoneSegOK(fx, fy, x, y):
    try:
        if ZoneGuard is None:
            return True
        return ZoneGuard.SafeWaypoint(fx, fy, x, y, str(background.GetCurrentMapName()))
    except:
        return True

_ub_log('[PathRunner] DEBUG: constants defined, init complete')
_ub_log('[PathRunner] DEBUG: PathRunner in sys.modules = %s' % ('PathRunner' in sys.modules))
_ub_log('[PathRunner] DEBUG: __builtin__.PathRunner = %s' % getattr(__builtin__, 'PathRunner', 'NOT_SET'))


def _loadPath(mapname):
    if json is None:
        _ub_log('[Path] ERROR: No json module found!')
        return None
    try:
        return json.loads(open(PATH_FILE % mapname, 'r').read())
    except:
        return None


def _savePathFile(mapname, data):
    if json is None:
        _ub_log('[Path] ERROR: No json module found!')
        return
    try:
        f = open(PATH_FILE % mapname, 'w')
        f.write(json.dumps(data))
        f.close()
        _ub_log('[Path] saved %s' % mapname)
    except:
        pass


def hasLearnedPath():
    try:
        return _loadPath(str(background.GetCurrentMapName())) is not None
    except:
        return False


class PathWizard(ui.ScriptWindow):
    """Guided route learner - popup window tells you WHERE to walk.
    The bot does buying and enchanting automatically during the learn."""

    def __init__(self):
        ui.ScriptWindow.__init__(self)
        self.Show()
        self.step = 'idle'
        self._wps = []
        self._lastWpAt = 0.0
        self._lastWpPos = None
        self._learned = {}
        self._replayIdx = 0
        self._replayPath = []
        self._replayCb = None
        self._autoMode = False
        self._cycleCount = 0
        self._lastTick = 0.0
        self._lastPos = None
        self._stuckN = 0
        self._dismountCd = 0
        self._lastBuyAt = 0.0
        self._lastGiveAt = 0.0
        self._giveSlot = -1
        self._built = False

    def _ensureMods(self):
        """Resolve game modules lazily. Returns True if all available."""
        try:
            if eXLib is None:
                import importlib as _il
                globals()['_eXLib'] = _il.import_module('eXLib')
                globals()['UIComponents'] = _il.import_module('UIComponents')
                globals()['OpenLib'] = _il.import_module('OpenLib')
            return True
        except:
            return False

    def BuildWindow(self):
        _ub_log("[Wizard] BuildWindow called")
        comp = UIComponents.Component()
        self.Board = ui.BoardWithTitleBar()
        self.Board.SetSize(320, 200)
        self.Board.SetCenterPosition()
        self.Board.AddFlag('movable')
        self.Board.AddFlag('float')
        self.Board.SetTitleName('MT2Robs - Aprender Rota')
        self.Board.SetCloseEvent(self.Close)
        self.Board.Hide()

        _btn = ('d:/ymir work/ui/public/large_button_01.sub',
                'd:/ymir work/ui/public/large_button_02.sub',
                'd:/ymir work/ui/public/large_button_03.sub')

        self.lStep = comp.TextLine(self.Board, 'START para aprender a rota', 20, 35, comp.RGB(255, 255, 0))
        self.lDots = comp.TextLine(self.Board, '[.] ANDAR [.] COMPRAR [.] ANDAR [.] TROCAR', 20, 58, comp.RGB(150, 150, 150))
        self.lDetail = comp.TextLine(self.Board, '', 20, 80, comp.RGB(200, 200, 200))

        self.startBtn = comp.Button(self.Board, 'START', 'Comecar aprendizado', 20, 105, self.OnStart, *_btn)
        self.saveBtn = comp.Button(self.Board, 'SAVE', 'Gravar a rota', 110, 105, self.OnSave, *_btn)
        self.autoBtn = comp.Button(self.Board, 'AUTO NOW', 'Gravar e auto', 200, 105, self.OnAutoNow, *_btn)
        self.stopBtn = comp.Button(self.Board, 'STOP', 'Parar tudo', 20, 140, self.OnStop, *_btn)
        self.closeBtn = comp.Button(self.Board, 'FECHAR', 'Fechar janela', 110, 140, self.Close, *_btn)
        self.retryBtn = comp.Button(self.Board, 'RETRY', 'Recomecar aprendizado', 200, 140, self.OnRetry, *_btn)

        self.lRoute = comp.TextLine(self.Board, '', 20, 170, comp.RGB(150, 200, 255))
        self.RefreshRoute()

    def Close(self):
        try:
            self.Board.Hide()
        except:
            pass

    def switch_state(self):
        _ub_log("[Wizard] switch_state called")
        # LAZY BUILD: create the window on FIRST use (game must be ready)
        if not self._built:
            try:
                self.BuildWindow()
                self._built = True
                _ub_log('[Wizard] UI built (lazy)')
            except Exception as _e:
                _ub_log('[Wizard] build ERR: %r' % _e)
                return
        try:
            showing = self.Board.IsShow()
        except:
            showing = False
        if showing:
            self.Board.Hide()
        else:
            self.RefreshRoute()
            self.Board.Show()
            self.Board.Show()   # double Show: some clients need it for float windows

    def RefreshRoute(self):
        try:
            learned = hasLearnedPath()
            if learned:
                self.lRoute.SetText('Rota: APRENDIDA (podes usar AUTO NOW)')
                self.lRoute.SetFontColor(0, 255 * 255, 0)
            else:
                self.lRoute.SetText('Rota: NAO aprendida neste mapa')
                self.lRoute.SetFontColor(255 * 255, 255 * 255, 0)
        except:
            pass

    def _msg(self, s):
        _ub_log('[Wizard] %s' % s)
        try:
            self.lStep.SetText(s)
        except:
            pass

    def _mapName(self):
        try:
            return str(background.GetCurrentMapName())
        except:
            return ''

    def _myPos(self):
        try:
            x, y, z = player.GetMainCharacterPosition()
            return (x, y)
        except:
            return None

    def _npcNear(self, race, rng=NPC_DETECT_RANGE):
        try:
            for vid in list(eXLib.InstancesList):
                vid = int(vid)
                if not chr.HasInstance(vid):
                    continue
                chr.SelectInstance(vid)
                if chr.GetRace(vid) == race:
                    x, y, z = eXLib.GetPixelPosition(vid)
                    return (vid, int(x), int(y))
        except:
            pass
        return None

    def OnStart(self):
        mapname = self._mapName()
        if not mapname:
            self._msg('Mapa desconhecido!')
            return
        self._wps = []
        self._learned = {}
        self._lastWpAt = 0.0
        self._lastWpPos = None
        self.step = 'to_dealer'
        self._msg('WALK TO WEAPON SELLER')
        self.lDetail.SetText('Anda ate ao vendedor de armas')

    def OnSave(self):
        if self._learned:
            _savePathFile(self._mapName(), self._learned)
            self._msg('Rota gravada! SAVE OK.')
            _ub_log('[Path] SAVE confirmado: rota guardada para %s' % self._mapName())
            # CONFIRMAR: a rota fica mesmo guardada
            try:
                loaded = _loadPath(self._mapName())
                if loaded is not None:
                    _ub_log('[Path] SAVE VERIFICADO: rota carregada com sucesso')
                    self._msg('SAVE VERIFICADO!')
                else:
                    _ub_log('[Path] SAVE VERIFICADO: rota NAO carregada!')
                    self._msg('SAVE FALHOU!')
            except Exception as e:
                _ub_log('[Path] SAVE verificacao ERR: %s' % e)
            self.RefreshRoute()
        else:
            self._msg('Aprende primeiro (START)')

    def OnAutoNow(self):
        if not self._learned and not hasLearnedPath():
            self._msg('Aprende primeiro (START)')
            return
        if self._learned:
            _savePathFile(self._mapName(), self._learned)
            _ub_log('[Path] AUTO NOW: rota guardada antes de iniciar')
        self.RefreshRoute()
        self._autoMode = True
        self._cycleCount = 0
        # INICIAR AUTO E ABRIR ENERGY BOT
        _ub_log('[Path] AUTO NOW: a iniciar ciclo automatico + EnergyBot')
        try:
            import EnergyBot
            EnergyBot.instance.autoBuy = True
            EnergyBot.instance._startBot()
            _ub_log('[Path] AUTO NOW: EnergyBot iniciado com sucesso')
        except Exception as e:
            _ub_log('[Path] AUTO NOW: EnergyBot inicio ERR: %s' % e)
        self._startAutoCycle()

    def OnStop(self):
        self.step = 'idle'
        self._autoMode = False
        self._replayPath = []
        self._msg('Parado')

    def OnRetry(self):
        self.OnStop()
        self.OnStart()

    def Hide(self):
        try:
            self.Board.Hide()
        except:
            pass

    def _startBuying(self):
        self.step = 'buying'
        self._msg('BUYING KNIVES...')
        self.lDetail.SetText('O bot esta a comprar facas (EnergyBot integrado)')
        self._lastBuyAt = 0.0
        # INTEGRAR ENERGYBOT: abrir menu do EnergyBot quando comprar
        try:
            import EnergyBot
            if EnergyBot.instance is not None:
                EnergyBot.instance.autoBuy = True
                EnergyBot.instance._startBot()
                _ub_log('[Path] EnergyBot AUTO BUY iniciado')
            else:
                _ub_log('[Path] EnergyBot instance is None')
        except Exception as e:
            _ub_log('[Path] EnergyBot init ERR: %s' % e)

    def _startGiving(self):
        self.step = 'giving'
        self._msg('ENCHANTING / ALQUIMISTA...')
        self.lDetail.SetText('O bot esta a trocar com alquimista (EnergyBot integrado)')
        self._giveSlot = -1
        self._lastGiveAt = 0.0
        # INTEGRAR ENERGYBOT: confirmar troca com alquimista
        try:
            import EnergyBot
            if EnergyBot.instance is not None:
                EnergyBot.instance.autoGive = True
                _ub_log('[Path] EnergyBot AUTO GIVE iniciado')
        except Exception as e:
            _ub_log('[Path] EnergyBot give ERR: %s' % e)

    def _cycleLearned(self):
        self.step = 'done'
        self._msg('CYCLE COMPLETE!')
        self.lDetail.SetText('SAVE para gravar ou AUTO NOW para automatico')

    def _startAutoCycle(self):
        data = _loadPath(self._mapName())
        if not data:
            self._msg('Sem rota gravada!')
            return
        self._cycleCount += 1
        self._msg('AUTO ciclo %d: a andar ao vendedor...' % self._cycleCount)
        self._replayPath = data.get('wps_to_dealer', [])
        self._replayIdx = 0
        self._replayCb = self._autoAtDealer
        self.step = 'replay'

    def _autoAtDealer(self):
        self._msg('AUTO: a comprar...')
        self._lastBuyAt = 0.0
        self.step = 'buying'

    def _autoBuyDone(self):
        self._msg('AUTO: a andar ao alquimista...')
        data = _loadPath(self._mapName())
        if data:
            self._replayPath = data.get('wps_to_alch', [])
            self._replayIdx = 0
            self._replayCb = self._autoAtAlch
            self.step = 'replay'

    def _autoAtAlch(self):
        self._msg('AUTO: a trocar...')
        self._giveSlot = -1
        self._lastGiveAt = 0.0
        self.step = 'giving'

    def _autoGiveDone(self):
        self._msg('AUTO: ciclo %d completo! Voltando...' % self._cycleCount)
        data = _loadPath(self._mapName())
        if data:
            self._replayPath = data.get('wps_back', [])
            self._replayIdx = 0
            self._replayCb = self._autoAtDealer
            self.step = 'replay'

    def OnUpdate(self):
        try:
            now = OpenLib.Monotonic()
            if now - self._lastTick < 0.5:
                return
            self._lastTick = now
            me = self._myPos()
            if me is None:
                return

            # ===== LEARN: to_dealer =====
            if self.step == 'to_dealer':
                if now - self._lastWpAt >= WAYPOINT_EVERY:
                    if self._lastWpPos is None:
                        self._wps.append((int(me[0]), int(me[1])))
                        self._lastWpPos = me
                        self._lastWpAt = now
                    else:
                        import math as _m
                        d = _m.sqrt((me[0] - self._lastWpPos[0])**2 + (me[1] - self._lastWpPos[1])**2)
                        # ZONAS: so gravar em area LIVRE/NAO MARCADA e sem
                        # zona MORTA no troco
                        if d >= WAYPOINT_MIN_DIST and _zoneSegOK(
                                self._lastWpPos[0], self._lastWpPos[1], me[0], me[1]):
                            self._wps.append((int(me[0]), int(me[1])))
                            self._lastWpPos = me
                            self._lastWpAt = now
                npc = self._npcNear(WEAPON_RACE, 400)
                if npc:
                    vid, x, y = npc
                    self._learned['dealer'] = (x, y)
                    self._learned['wps_to_dealer'] = list(self._wps)
                    self._msg('Vendedor encontrado! A comprar...')
                    # CONFIRMAR COMPRA REAL quando perto do NPC
                    try:
                        import EnergyBot
                        if EnergyBot.instance is not None:
                            EnergyBot.instance.autoBuy = True
                            EnergyBot.instance._startBot()
                            _ub_log('[Path] Compra REAL iniciada via EnergyBot (NPC %d)' % vid)
                        else:
                            _ub_log('[Path] EnergyBot.instance is None')
                    except Exception as e:
                        _ub_log('[Path] Compra REAL ERRO: %s' % e)
                    self._startBuying()
                return

            # ===== BUYING (learn + auto) =====
            if self.step == 'buying':
                _ub_log('[PathRunner] SIMULATING BUY (skip packet)')
                if self._autoMode:
                    self._autoBuyDone()
                else:
                    self._wps = []
                    self._lastWpAt = 0.0
                    self._lastWpPos = None
                    self.step = 'to_alch'
                    self._msg('WALK TO ALCHEMIST')
                    self.lDetail.SetText('SIMULADO: Anda ao alquimista')
                return

            # ===== GIVING (learn + auto) =====
            if self.step == 'giving':
                _ub_log('[PathRunner] SIMULATING EXCHANGE (skip packet)')
                if self._autoMode:
                    self._autoGiveDone()
                else:
                    self._cycleLearned()
                return

            # ===== REPLAY (auto mode) =====
            if self.step == 'replay' and self._replayPath:
                if self._replayIdx >= len(self._replayPath):
                    cb = self._replayCb
                    self._replayPath = []
                    self._replayCb = None
                    if cb:
                        cb()
                    return
                tx, ty = self._replayPath[self._replayIdx]
                # ZONAS: waypoint em zona MORTA -> saltar
                if not _zoneOK(tx, ty):
                    _ub_log('[Wizard] zona: replay wp %d MORTO -> skip' % (self._replayIdx + 1))
                    self._replayIdx += 1
                    return
                import math as _m
                d = _m.sqrt((tx - me[0])**2 + (ty - me[1])**2)
                if d < 200:
                    self._replayIdx += 1
                    self._lastPos = me
                    self._stuckN = 0
                    return
                try:
                    chr.MoveToDestPosition(player.GetMainCharacterIndex(), int(tx), int(ty))
                except:
                    pass
                # stuck detection
                if self._dismountCd > 0:
                    self._dismountCd -= 1
                    self._lastPos = me
                    return
                if self._lastPos is not None:
                    moved = _m.sqrt((me[0] - self._lastPos[0])**2 + (me[1] - self._lastPos[1])**2)
                    if moved > 50:
                        self._lastPos = me
                        self._stuckN = 0
                    else:
                        self._stuckN += 1
                        if self._stuckN >= 5:
                            self._stuckN = 0
                            self._dismountCd = 120
                            try:
                                eXLib.SyncPlayerPosition()
                            except:
                                pass
                            self._msg('PRESO -> unstick')
                else:
                    self._lastPos = me
        except:
            pass


# singleton
_REG = getattr(sys, '_ubot_reg', None)
if _REG is None:
    _REG = {}
    sys._ubot_reg = _REG

inst = _REG.get('pathwizard')
if inst is None:
    inst = PathWizard()
    _REG['pathwizard'] = inst
else:
    try:
        inst.__class__ = PathWizard
    except:
        pass
instance = inst


def switch_state():
    instance.switch_state()
