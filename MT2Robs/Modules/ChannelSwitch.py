import sys
import __builtin__ as buildin

def HasArguments(module, attrlist):
    for attr in attrlist:
        if not buildin.hasattr(module, attr):
            return False
    return True

for modulename, module in iter(sys.modules.items()):
    if HasArguments(module, ['GetPlayTime']):player = module
    if HasArguments(module, ['DirectEnter']):net = module
    if HasArguments(module, ['SetCameraMaxDistance']):app = module
    if HasArguments(module, ['ScriptWindow']):ui = module

import eXLib, OpenLib
from MT2Robs.Modules.Hooks import registerPhaseCallback

try:
    import time as _wt   # wall clock for cooldowns/verifies (game-time timers
except:                  # proved unreliable -- they fired instantly)
    _wt = None


def _now():
    return OpenLib.Monotonic()


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
# ChannelSwitch -- channel hopping, 100% client-side.
#
# PRIMARY: this GF client exposes its OWN channel API on the net module
# (found via the log dump):
#     net.GetChannelCount()   -> number of channels (6)
#     net.GetChannelNumber()  -> channel we are on right now
#     net.GetChannelName(n)   -> display name
#     net.MoveChannelGame(n)  -> the OFFICIAL channel switch (same code path
#                                the client's own system menu uses)
# FALLBACK (non-GF clients): replay the captured Connect/DirectEnter calls
# (bootstrap hooks in init.py store them on sys._ubot_netcap).
# =============================================================================

CHANNELS_FILE = eXLib.PATH + 'MT2Robs/Saves/channels.txt'

CHANNELS = {}          # {channel_number: (ip, port)} -- fallback mode only
NATIVE = [False]       # True -> using net.MoveChannelGame
CUR_CHANNEL = [None]   # channel number we are on now
_pending = [None]      # fallback mode pending switch
_pending_native = [None]  # native mode: {'n': target, 't': last attempt, 't0': start, 'tries': k}
_busy = [False]
_lastSwitch = [0.0]
_NATIVE_RETRY = 25.0   # wall seconds per attempt (minimized clients tick very
                       # slowly -- 4s caused a full unwanted ch1->...->ch6 tour)


def _nativeChannels():
    # only channels that actually have a name (count 7 included an unnamed one,
    # probably CHANNEL_99/battle-royale; the server has 6 real channels)
    cnt = _nativeCount()
    lst = []
    for i in range(1, cnt + 1):
        try:
            if net.GetChannelName(i):
                lst.append(i)
        except:
            pass
    return lst if lst else list(range(1, cnt + 1))


def _nativeCur():
    try:
        c = net.GetChannelNumber()
        if c:
            return int(c)
    except:
        pass
    return None


def _nativeCount():
    try:
        c = net.GetChannelCount()
        if c:
            return int(c)
    except:
        pass
    return 0


def _tryNative(n, m=0):
    # The logs confirm the official API uses the 1-based channel number.
    # Never send alternative formats: concurrent requests leave the client BUSY.
    try:
        arg = int(n)
        net.MoveChannelGame(arg)
        _ub_log('[ChSw] MoveChannelGame(%d) sent' % arg)
        return True
    except Exception as e:
        _ub_log('[ChSw] MoveChannelGame ERR: %s' % e)
        return False


def _verifyNative():
    p = _pending_native[0]
    if p is None:
        return
    cur = _nativeCur()
    if cur == p.get('target', p.get('n')):
        _busy[0] = False
        CUR_CHANNEL[0] = cur
        _pending_native[0] = None
        _ub_log('[ChSw] channel switch OK -> ch%d' % cur)
        return
    _ub_log('[ChSw] switch not confirmed for ch%s (cur=%s)' % (p.get('target', p.get('n')), cur))
    _pending_native[0] = None
    _busy[0] = False


class _Ticker(ui.ScriptWindow):
    # Own ticking window: deferred callbacks proved unreliable on this client,
    # and the OnUpdate of a shown ScriptWindow demonstrably ticks through
    # world reloads. Drives the whole native-switch state machine from here.
    def __init__(self):
        ui.ScriptWindow.__init__(self)
        self.Show()

    def OnUpdate(self):
        try:
            _tick()
        except:
            pass


def _tick():
    p = _pending_native[0]
    if p is None:
        return
    now = _now()
    tgt = p['target']
    if p.get('phase') == 'trick':
        # manual recipe: land on ANOTHER channel first, then hop back to the
        # target while the client is still loading (works even when busy)
        if now >= p['back_at']:
            _ub_log('[ChSw] trick: back to ch%d while loading' % tgt)
            p['phase'] = 'wait'
            p['t'] = now
            _tryNative(tgt, 0)
        return
    cur = _nativeCur()
    if cur == tgt:
        _busy[0] = False
        CUR_CHANNEL[0] = cur
        _pending_native[0] = None
        _ub_log('[ChSw] switch OK -> ch%d' % cur)
        return
    if now - p['t'] < _NATIVE_RETRY:
        return   # still waiting for this attempt to land
    p['tries'] += 1
    if p['tries'] >= 3:
        _busy[0] = False
        _pending_native[0] = None
        _ub_log('[ChSw] gave up after %d attempts -- use the manual trick (outro server -> teu server)' % p['tries'])
        return
    if p['tries'] == 1:
        # first retry: emulate the manual recipe -- pass via another channel
        nums = [c for c in _nativeChannels() if c != tgt and c != cur]
        other = nums[0] if nums else tgt
        _ub_log('[ChSw] ch%d not landing -> trick: pass via ch%d, back in 2s' % (tgt, other))
        p['phase'] = 'trick'
        p['back_at'] = now + 2.0
        _tryNative(other, 0)
        return
    _ub_log('[ChSw] ch%d not landing -> direct retry' % tgt)
    p['t'] = now
    _tryNative(tgt, 0)


def _loadFile():
    data = {}
    try:
        with open(CHANNELS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                try:
                    n = int(k.strip())
                    ip, port = v.strip().split(':')
                    data[n] = (ip, int(port))
                except:
                    continue
    except:
        pass
    return data


def _looksLikeIp(s):
    if not buildin.isinstance(s, str):
        return False
    parts = s.split('.')
    return len(parts) == 4 and all(p.isdigit() for p in parts)


def _discoverFromModule(mod, modname):
    # non-GF fallback: harvest channel dicts from the client's serverInfo
    found = {}
    try:
        items = vars(mod).items()
    except:
        return found
    for name, val in items:
        cand = {}
        try:
            if buildin.isinstance(val, dict):
                for k, v in val.items():
                    if not buildin.isinstance(k, int):
                        continue
                    ip = port = None
                    if buildin.isinstance(v, dict):
                        ip = v.get('ip')
                        port = v.get('tcp_port', v.get('port'))
                    elif buildin.isinstance(v, (tuple, list)):
                        for e in v:
                            if _looksLikeIp(e):
                                ip = e
                            elif buildin.isinstance(e, int) and 1000 <= e <= 65535 and ip is not None:
                                port = e
                    if ip and port:
                        cand[k] = (ip, int(port))
        except:
            continue
        if len(cand) >= 2:
            keys = sorted(cand)
            if keys[0] >= 1 and keys[0] <= 3 and keys == list(range(keys[0], keys[0] + len(keys))) and keys[-1] <= 20:
                _ub_log('[ChSw] %s.%s -> %d channels: %s' % (
                    modname, name, len(cand), sorted(cand.items())))
                found.update(cand)
    return found


def _writeFile(table):
    try:
        with open(CHANNELS_FILE, 'w') as f:
            f.write('# Channels for the Finder switcher (fallback mode). Format: N=ip:port\n')
            for n in sorted(table):
                f.write('%d=%s:%d\n' % (n, table[n][0], table[n][1]))
        _ub_log('[ChSw] wrote channels.txt (%d channels)' % len(table))
    except Exception as e:
        _ub_log('[ChSw] write channels.txt ERR: ' + str(e))


def _initChannels():
    global CHANNELS
    cap = getattr(sys, '_ubot_netcap', None) or {}
    n = _nativeCount()
    if n >= 1 and buildin.hasattr(net, 'MoveChannelGame'):
        NATIVE[0] = True
        CUR_CHANNEL[0] = _nativeCur()
        _ub_log('[ChSw] NATIVE mode: %d channels (MoveChannelGame), current=%s' % (n, CUR_CHANNEL[0]))
        # dump names so the arg semantics can be confirmed from the log
        try:
            names = []
            for i in range(1, n + 1):
                try:
                    names.append('%d=%r' % (i, net.GetChannelName(i)))
                except:
                    names.append('%d=?' % i)
            _ub_log('[ChSw] channel names: %s' % ', '.join(names))
        except:
            pass
        return
    # fallback mode: ip/port table
    CHANNELS = _loadFile()
    if CHANNELS:
        _ub_log('[ChSw] channels.txt loaded: %d channels' % len(CHANNELS))
    else:
        srv = None
        for modulename, module in iter(sys.modules.items()):
            if HasArguments(module, ['MARKADDR_DICT']):
                srv = module
                break
        if srv is not None:
            CHANNELS = _discoverFromModule(srv, modulename)
        if CHANNELS:
            _writeFile(CHANNELS)
        else:
            _ub_log('[ChSw] no channel table found (serverInfo scan empty)')
            if cap.get('ip') and cap.get('port'):
                try:
                    with open(CHANNELS_FILE, 'w') as f:
                        f.write('# Channels for the Finder switcher. Format: N=ip:port\n')
                        f.write('# Only ch1 (current connection) is known -- add 2..6 the same way.\n')
                        f.write('1=%s:%d\n' % (cap['ip'], cap['port']))
                    CHANNELS[1] = (cap['ip'], int(cap['port']))
                    _ub_log('[ChSw] template written with current server as ch1 -- fill 2..6 by hand')
                except:
                    pass
    if cap.get('port'):
        for k, (ip, port) in CHANNELS.items():
            if int(cap['port']) == int(port):
                CUR_CHANNEL[0] = k
                break
    _ub_log('[ChSw] ready (fallback): %d channels, current=%s, creds=%s, direct_args=%s' % (
        len(CHANNELS), CUR_CHANNEL[0],
        'yes' if cap.get('id') else 'NO', 'yes' if cap.get('direct_args') else 'NO'))


def channelNumbers():
    if NATIVE[0]:
        return _nativeChannels()
    return sorted(CHANNELS.keys())


def channelName(n):
    if NATIVE[0]:
        try:
            nm = net.GetChannelName(n)
            if nm:
                return str(nm)
        except:
            pass
    return str(n)


def hasTable():
    if NATIVE[0]:
        return _nativeCount() >= 2
    return len(CHANNELS) >= 2


def _fireEnter():
    # fallback mode: replay the EXACT DirectEnter the client sent at login
    p = _pending[0]
    if p is None or p['fired']:
        return
    cap = getattr(sys, '_ubot_netcap', None) or {}
    args = cap.get('direct_args')
    try:
        if args:
            args = list(args)
            if len(args) >= 4 and buildin.isinstance(args[2], str):
                args[2] = p['ip']
                args[3] = p['port']
            net.DirectEnter(*args)
            _ub_log('[ChSw] DirectEnter replayed (%d args)' % len(args))
        elif cap.get('id'):
            try:
                net.SetLoginInfo(cap['id'], cap['pwd'])
            except:
                pass
            net.DirectEnter(cap['id'], cap['pwd'], cap.get('slot', 0))
            _ub_log('[ChSw] DirectEnter replayed (from SetLoginInfo capture)')
        else:
            _ub_log('[ChSw] cannot enter: no captured credentials')
            return
        p['fired'] = True
    except Exception as e:
        _ub_log('[ChSw] DirectEnter ERR: ' + str(e))


def switchTo(n):
    # switch to channel n. Returns True if the switch was issued.
    if NATIVE[0]:
        nums = _nativeChannels()
        if int(n) not in nums:
            _ub_log('[ChSw] unknown channel %r (real channels: %s)' % (n, nums))
            return False
        now = _now()
        # stale-busy guard: a previous attempt whose verify never fired
        if _busy[0] and now - _lastSwitch[0] > 90.0:
            _busy[0] = False
            _pending_native[0] = None
            _ub_log('[ChSw] cleared stale busy state')
        if _busy[0] or now - _lastSwitch[0] < 15.0:
            _ub_log('[ChSw] switch blocked (busy / cooldown)')
            return False
        _lastSwitch[0] = now
        _busy[0] = True
        _pending_native[0] = {'target': int(n), 't': now, 'tries': 0, 'phase': 'wait'}
        _ub_log('[ChSw] native switch ch%s -> ch%d (MoveChannelGame)' % (CUR_CHANNEL[0], n))
        if _tryNative(int(n), 0):
            return True
        _busy[0] = False
        _pending_native[0] = None
        return False
    # fallback mode
    if n not in CHANNELS:
        _ub_log('[ChSw] unknown channel %r (table has %s)' % (n, channelNumbers()))
        return False
    cap = getattr(sys, '_ubot_netcap', None) or {}
    if not cap.get('direct_args') and not cap.get('id'):
        _ub_log('[ChSw] no credentials captured -- cannot switch')
        return False
    now = OpenLib.GetTime()
    if _busy[0] or now - _lastSwitch[0] < 30.0:
        _ub_log('[ChSw] switch blocked (busy / cooldown)')
        return False
    ip, port = CHANNELS[n]
    _ub_log('[ChSw] switching ch%s -> ch%s (%s:%d)' % (CUR_CHANNEL[0], n, ip, port))
    _lastSwitch[0] = now
    _busy[0] = True
    _pending[0] = {'n': n, 'ip': ip, 'port': port, 'fired': False, 't': now}
    try:
        net.Disconnect()
    except Exception as e:
        _ub_log('[ChSw] Disconnect ERR: ' + str(e))
    try:
        net.Connect(ip, port)
    except Exception as e:
        _ub_log('[ChSw] Connect ERR: ' + str(e))
        _busy[0] = False
        return False
    _fireEnter()
    return True


def next():
    # round-robin to the next channel
    nums = channelNumbers()
    if not nums:
        _ub_log('[ChSw] next(): no channel table')
        return False
    if NATIVE[0]:
        cur = _nativeCur() or CUR_CHANNEL[0] or nums[0]
        if cur in nums:
            i = nums.index(cur)
        else:
            i = -1
        return switchTo(nums[(i + 1) % len(nums)])
    if CUR_CHANNEL[0] in nums:
        i = nums.index(CUR_CHANNEL[0])
    else:
        i = -1
    return switchTo(nums[(i + 1) % len(nums)])


def _onPhase(phase, arg):
    p = _pending[0]
    if NATIVE[0]:
        if phase == OpenLib.PHASE_GAME and _busy[0]:
            # a world reload happened -- confirm it landed on the target channel
            _verifyNative()
        return
    if p is None:
        return
    if phase == OpenLib.PHASE_GAME:
        if _busy[0]:
            _busy[0] = False
            CUR_CHANNEL[0] = p['n']
            _pending[0] = None
            _ub_log('[ChSw] in game on ch%d' % CUR_CHANNEL[0])
    elif phase == OpenLib.PHASE_LOGIN and not p['fired'] and OpenLib.GetTime() - p['t'] > 2.0:
        _fireEnter()
    elif not p['fired'] and OpenLib.GetTime() - p['t'] > 15.0:
        _ub_log('[ChSw] switch to ch%d timed out (manual relog may be needed)' % p['n'])
        _pending[0] = None
        _busy[0] = False


_initChannels()
registerPhaseCallback('ubot_chsw', _onPhase)
# the ticking window that drives the native-switch state machine
try:
    _ticker
    _ticker.__class__ = _Ticker
except NameError:
    _ticker = _Ticker()
