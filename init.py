# init.py -- MT2Robs LITE bootstrap + loader (eXLib runs this file TWICE).
# LITE = Energy farm (dealer -> alchemist, YOU walk, the bot acts).
# Toggle with "+" / INSERT (or the "+" chat),
# hide everything with the DOWN arrow.
import sys
if not getattr(sys, '_ubot_init_phase2', False):
    sys._ubot_init_phase2 = True
    # ===================== BOOTSTRAP =====================
    import ui, sys, os
    import eXLib
    import chr,app

    def HasArguments(module, attrlist):
        for attr in attrlist:
            if hasattr(module, attr):
                return True
        return False

    b = sys.modules.keys()
    playerm = netm = None
    for i in range(len(b)):
        h = b[i]
        a = dir(__import__(b[i]))
        for y in range(len(a)):
            if a[y] == 'GetMainCharacterIndex' or a[y] == 'INVENTORY_PAGE_SIZE' or a[y] == 'INVENTORY_SLOT_COUNT':
                playerm = b[i]
            if a[y] == 'SendShopEndPacket':
                netm = b[i]
    exec ('import ' + playerm + ' as _player')
    exec ('import ' + netm + ' as _net')

    # key bridge (eXLib's C++ calls BOTH -- if either is missing the whole
    # key pipeline dies)
    def SetSingleDIKKeyState(key, state):
        if state == 1:
            _player.OnKeyDown(key)
        else:
            _player.OnKeyUp(key)

    def SetAttackKeyState(state):
        _dik = getattr(app, 'DIK_SPACE', 57)
        if state == 1:
            _player.OnKeyDown(_dik)
        else:
            _player.OnKeyUp(_dik)

    setattr(chr, 'GetPixelPosition', eXLib.GetPixelPosition)
    setattr(chr, 'MoveToDestPosition', eXLib.MoveToDestPosition)
    setattr(_player, 'SetSingleDIKKeyState', SetSingleDIKKeyState)
    setattr(_player, 'SetAttackKeyState', SetAttackKeyState)

    # first GameWindow capture (for the navigator key forwarding)
    try:
        sys._ubot_gw = 0
        _orig_sgw = getattr(_player, 'SetGameWindow', None)
        if _orig_sgw is not None:
            def _ub_sgw(*a, **kw):
                try:
                    if a and a[0]:
                        sys._ubot_gw = a[0]
                except:
                    pass
                return _orig_sgw(*a, **kw)
            _player.SetGameWindow = _ub_sgw
    except:
        pass

    # paths
    sys.path.append(os.path.join(eXLib.PATH))
    sys.path.append(os.path.join(eXLib.PATH, 'MT2Robs'))
    sys.path.append(os.path.join(eXLib.PATH, 'MT2Robs', 'lib'))
    sys.path.append(os.path.join(eXLib.PATH, 'MT2Robs', 'Modules'))

else:
    # ===================== LOADER =====================
    import sys
    import __builtin__ as buildin
    import eXLib
    import time as _ubtime
    from MT2Robs.Modules import UIComponents, EnergyBot
    try:
        import PathRunner
    except:
        PathRunner = None

    # ---- Ctrl+V paste + Price Memory ----
    _ub_clip = {'lastEdit': None}
    _ub_ctrlDown = [False]

    def _ub_getClipboard():
        try:
            import ctypes
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            if not u32.OpenClipboard(0):
                return ''
            try:
                h = u32.GetClipboardData(13)
                if not h:
                    h = u32.GetClipboardData(1)
                if not h:
                    return ''
                ptr = k32.GlobalLock(h)
                if not ptr:
                    return ''
                try:
                    text = ctypes.wstring_at(ptr)
                except:
                    try:
                        text = ctypes.c_char_p(ptr).value.decode('latin-1', 'replace')
                    except:
                        text = ''
                k32.GlobalUnlock(h)
                return text or ''
            finally:
                u32.CloseClipboard()
        except:
            return ''

    def _ub_charToDIK(ch):
        o = ord(ch)
        if 48 <= o <= 57:
            digit = o - 48
            return 11 if digit == 0 else digit + 1
        if 65 <= o <= 90:  return o - 65 + 30
        if 97 <= o <= 122: return o - 97 + 30
        if ch == ' ':  return 57
        if ch == '.':  return 52
        if ch == ',':  return 51
        if ch == '-':  return 12
        if ch == '/':  return 53
        return 0

    def _ub_typePrice(txt):
        try:
            gw = getattr(sys, '_ubot_gw', 0)
            for ch in str(txt).strip():
                dik = _ub_charToDIK(ch)
                if dik:
                    try:
                        player.OnKeyDown(dik)
                        player.OnKeyUp(dik)
                    except:
                        pass
                    try:
                        if gw and hasattr(gw, 'OnKeyDown'):
                            gw.OnKeyDown(dik)
                            gw.OnKeyUp(dik)
                    except:
                        pass
            _ub_log('[Price] typed %s' % txt)
        except:
            pass

    _ub_prices = {'list': [], 'file': eXLib.PATH + 'MT2Robs/Saves/prices.txt'}

    def _ub_loadPrices():
        try:
            txt = open(_ub_prices['file'], 'r').read().strip()
            _ub_prices['list'] = [x.strip() for x in txt.split('\n') if x.strip()][:5]
        except:
            _ub_prices['list'] = []

    def _ub_savePrices():
        try:
            f = open(_ub_prices['file'], 'w')
            f.write('\n'.join(_ub_prices['list'][:5]))
            f.close()
        except:
            pass

    _ub_loadPrices()

    _UB_TOGGLE_KEYS = (13, 78, 26, 41, 210, 46)   # + / numpad+ / PT key41 / INSERT / DEL
    _UB_STEALTH_KEYS = (208,)                  # DOWN arrow: hide everything
    _ubot_wrapref = [None]

    def _ub_log(text):
        try:
            from datetime import datetime
            stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f = open(eXLib.PATH + 'mt2robs.txt', 'a')
            f.write('[%s] %s\n' % (stamp, text))
            f.close()
        except:
            pass

    # ---- key forwarding (our windows never eat M/I/N) ----
    def _ub_fwdDown(*args):
        try:
            gw = getattr(sys, '_ubot_gw', 0)
            if gw and hasattr(gw, 'OnKeyDown'):
                gw.OnKeyDown(args[0] if args else 0)
        except:
            pass

    def _ub_fwdUp(*args):
        try:
            gw = getattr(sys, '_ubot_gw', 0)
            if gw and hasattr(gw, 'OnKeyUp'):
                gw.OnKeyUp(args[0] if args else 0)
        except:
            pass

    def _ub_fwd_tree(root, depth=0, seen=None):
        if seen is None:
            seen = []
        try:
            if root is None or depth > 6 or id(root) in seen:
                return
            if buildin.isinstance(root, (list, tuple)):
                for v in root:
                    _ub_fwd_tree(v, depth + 1, seen)
                return
            seen.append(id(root))
            if hasattr(root, 'SetMax') and hasattr(root, 'SetFocus'):
                return   # EditLine: keep keyboard input inside
            if hasattr(root, 'SetParent') and hasattr(root, 'Show'):
                try:
                    root.OnKeyDown = _ub_fwdDown
                except:
                    pass
                try:
                    root.OnKeyUp = _ub_fwdUp
                except:
                    pass
            try:
                sub = root.__dict__.values()
            except:
                sub = []
            for v in sub:
                _ub_fwd_tree(v, depth + 1, seen)
        except:
            pass

    def _ub_fwd_install():
        try:
            _ub_fwd_tree(EnergyBot.instance.Board)
        except:
            pass

    # ---- the mini bar: 2 buttons ----
    class uBotBar(ui.ScriptWindow):
        comp = UIComponents.Component()

        def __init__(self):
            try:
                _ub_log('[UI] A iniciar uBotBar...')
                ui.ScriptWindow.__init__(self)
                self.Show()
                self.allShown = False
                self._lastTg = -10.0
                self._lastWatch = 0.0
                self._needRearm = True
                _ub_log('[UI] Variaveis init ok')

                self.Board = ui.ThinBoard(layer="TOP_MOST")
                self.Board.SetPosition(0, 100)
                self.Board.SetSize(51, 123)
                self.Board.AddFlag("float")
                self.Board.AddFlag("movable")
                self.Board.Hide()
                _ub_log('[UI] Board criado')

                base = eXLib.PATH + 'MT2Robs/Images/'
                self.EnergyButton = self.comp.Button(self.Board, '', 'Farm de energias', 9, 10,
                    EnergyBot.instance.switch_state,
                    base + 'Hackbar/energy_0.tga', base + 'Hackbar/energy_1.tga', base + 'Hackbar/energy_0.tga')
                _ub_log('[UI] EnergyButton criado com sucesso')
            except Exception as e:
                import traceback
                _ub_log('[UI] ERRO: ' + str(e))
                _ub_log('[UI] Trace: ' + traceback.format_exc())
            
            _ub_log('[UI] uBotBar.__init__ completo')

        def _now(self):
            try:
                return app.GetTime()
            except:
                return 0.0

        def ToggleAll(self, src=''):
            try:
                n = self._now()
                if n - self._lastTg < 0.35:
                    return
                self._lastTg = n
            except:
                pass
            self.allShown = not self.allShown
            _ub_log('[Bar] toggle(%s) -> %s' % (src or '?', 'OPEN' if self.allShown else 'CLOSED'))
            if self.allShown:
                _ub_log('[Bar] A mostrar barra...')
                self.Board.Show()
                _ub_log('[Bar] Board.Show() chamado')
                try: 
                    EnergyBot.instance.Board.Show()
                    _ub_log('[Bar] EnergyBot.instance.Board.Show() OK')
                except Exception as e:
                    _ub_log('[Bar] ERRO EnergyBot Board: ' + str(e))
                # Tentar MT2RobsCompass apenas se existir
                try:
                    import MT2RobsCompass
                    if hasattr(MT2RobsCompass, 'instance') and MT2RobsCompass.instance is not None:
                        MT2RobsCompass.instance.Board.Show()
                        _ub_log('[Bar] MT2RobsCompass Board.Show() OK')
                except Exception as e:
                    _ub_log('[Bar] MT2RobsCompass skip: ' + str(e))
            else:
                self._hideAll()

        def Stealth(self, src=''):
            self._hideAll()

        def OnUpdate(self):
            try:
                n = _ubtime.time()
                if n - self._lastWatch > 5.0:
                    self._lastWatch = n
                    _ub_install_keywrap()
                    _ub_fwd_install()
                    if getattr(self, '_needRearm', False) and self.allShown:
                        self._needRearm = False
                        try:
                            self.Board.Show()
                            EnergyBot.instance.Board.Show()
                            MT2RobsCompass.instance.Board.Show()
                            _ub_log('[Rearm] boards restored')
                        except:
                            pass
            except:
                pass

        def _hideAll(self):
            self.allShown = False
            try:
                self.Board.Hide()
            except: pass
            try: 
                EnergyBot.instance.Board.Hide()
            except: pass
            try:
                import MT2RobsCompass
                if hasattr(MT2RobsCompass, 'instance') and MT2RobsCompass.instance is not None:
                    MT2RobsCompass.instance.Board.Hide()
            except: pass
            

    # ---- Price Memory window ----
    try:
        class PriceMemWin(ui.ScriptWindow):
            comp = UIComponents.Component()

            def __init__(self):
                ui.ScriptWindow.__init__(self)
                self.Show()
                self.BuildWindow()
                self.Refresh()

            def BuildWindow(self):
                self.Board = ui.BoardWithTitleBar()
                self.Board.SetSize(180, 145)
                self.Board.SetPosition(520, 40)
                self.Board.AddFlag('movable')
                self.Board.AddFlag('float')
                self.Board.SetTitleName('Precos')
                self.Board.SetCloseEvent(self.Hide)
                self.Board.Hide()

                self.edPrice = ui.EditLine()
                self.edPrice.SetParent(self.Board)
                self.edPrice.SetSize(80, 18)
                self.edPrice.SetPosition(15, 35)
                self.edPrice.SetMax(10)
                self.edPrice.SetText('')
                self.edPrice.SetNumberMode()
                self.edPrice.Show()

                self.typeBtn = self.comp.Button(self.Board, 'Digitar', 'Digitar o preco no campo activo', 105, 33,
                    self.OnType,
                    'd:/ymir work/ui/public/small_button_01.sub', 'd:/ymir work/ui/public/small_button_02.sub', 'd:/ymir work/ui/public/small_button_03.sub')

                self.lblHist = self.comp.TextLine(self.Board, 'ultimos:', 15, 62, self.comp.RGB(200, 200, 200))
                self.histBtns = []
                for i in range(3):
                    y = 78 + i * 22
                    b = self.comp.Button(self.Board, '-', '', 15, y, self._mkHist(i),
                        'd:/ymir work/ui/public/small_button_01.sub', 'd:/ymir work/ui/public/small_button_02.sub', 'd:/ymir work/ui/public/small_button_03.sub')
                    self.histBtns.append(b)

            def _mkHist(self, idx):
                def _go():
                    try:
                        lst = _ub_prices.get('list', [])
                        if idx < len(lst) and lst[idx]:
                            self.edPrice.SetText(lst[idx])
                            self.OnType()
                    except:
                        pass
                return _go

            def OnType(self):
                try:
                    txt = self.edPrice.GetText().strip()
                    if txt:
                        _ub_typePrice(txt)
                        lst = _ub_prices['list']
                        if txt in lst:
                            lst.remove(txt)
                        lst.insert(0, txt)
                        lst = lst[:5]
                        _ub_prices['list'] = lst
                        _ub_savePrices()
                        self.Refresh()
                except:
                    pass

            def Refresh(self):
                try:
                    lst = _ub_prices.get('list', [])
                    for i, b in enumerate(self.histBtns):
                        if i < len(lst) and lst[i]:
                            b.SetText(lst[i])
                        else:
                            b.SetText('-')
                except:
                    pass

            def Hide(self):
                try:
                    self.Board.Hide()
                except:
                    pass

            def switch_state(self):
                if self.Board.IsShow():
                    self.Board.Hide()
                else:
                    self.Refresh()
                    self.Board.Show()

        app.uBotPrices = PriceMemWin()
    except Exception as _pe:
        _ub_log('[Prices] ERR: ' + str(_pe))

    def _ub_togglePrices():
        try:
            app.uBotPrices.switch_state()
        except:
            pass

    # ---- key hotkeys wrap ----
    def _ub_install_keywrap():
        try:
            cur = getattr(player, 'OnKeyDown', None)
            if cur is None:
                return
            if _ubot_wrapref[0] is not None and cur is _ubot_wrapref[0]:
                return

            def _ubotOnKeyDown(key, _orig=cur):
                try:
                    if key == 29:
                        _ub_ctrlDown[0] = True
                    if _ub_ctrlDown[0] and key == 47:
                        txt = _ub_getClipboard()
                        if txt:
                            _ub_log('[Paste] %d chars' % len(txt))
                            _ub_typePrice(txt)
                        _ub_ctrlDown[0] = False
                        return
                    if key == 65 and PathRunner:   # F7: PathRunner
                        PathRunner.switch_state()
                    if key == 66:   # F8
                        _ub_togglePrices()
                    t = getattr(app, 'uBot', None)
                    if t is not None:
                        if key in _UB_TOGGLE_KEYS:
                            t.ToggleAll('key%d' % key)
                        elif key in _UB_STEALTH_KEYS:
                            t.Stealth('key%d' % key)
                except:
                    pass
                return _orig(key)

            setattr(player, 'OnKeyDown', _ubotOnKeyDown)
            _ubot_wrapref[0] = _ubotOnKeyDown
        except:
            pass

    # player module scan (loader side)
    def HasArguments2(module, attrlist):
        for attr in attrlist:
            if buildin.hasattr(module, attr):
                return True
        return False
    for modulename, module in iter(sys.modules.items()):
        if HasArguments2(module, ['GetPlayTime']):
            player = module
            break

    app.uBot = uBotBar()
    _ub_install_keywrap()
    _ub_fwd_install()

    # re-arm on every world load (map change / teleport / relog)
    try:
        from MT2Robs.Modules.Hooks import registerPhaseCallback as _ub_rpc

        def _ub_rearm(phase, arg):
            if phase != 5:
                return
            try:
                t = getattr(app, 'uBot', None)
                if t is not None:
                    t.Show()
                    t._needRearm = True
                EnergyBot.instance.Show()
            except:
                pass
        _ub_rpc('ubot_rearm', _ub_rearm)
    except:
        pass

    _ub_log('[MT2Robs LITE] ready - +/INSERT abre, SETA-BAIXO esconde')
