
import sys
_chr = chr

import time as _walltime   # REAL wall clock -- survives game-time freezes/minimize

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
    if HasArguments(module, ['GetCurrentMapName']):background = module
    if HasArguments(module, ['GetItemName', 'SelectItem']):item = module
    if HasArguments(module, ['SelectAnswer']):event = module
    if HasArguments(module, ['GetGradeByVID']):nonplayer = module
    if HasArguments(module, ['ScriptWindow']):ui = module
    if HasArguments(module, ['factorial']):math = module

from MT2Robs.Modules.Hooks import Hook, questHook
import Hooks, Data, eXLib
import FileManager, OpenLog

#Types -- metin=2, ore/object=1, monster=0, player=6.
NONE_TYPE = -99
OBJECT_TYPE = 1
METIN_TYPE = 2
MONSTER_TYPE = 0
PLAYER_TYPE = 6
BOSS_TYPE = -1
ORE_TYPE = -2

BOSS_IDS = dict()
BOSS_LEVELS = dict()   # vnum -> level (int) or None; filled from Saves files
METIN_IDS = dict()     # vnum -> name
METIN_LEVELS = dict()  # vnum -> level (int) or None

# Mob level lookup chain: the client's nonplayer/chr module (live data, no files
# needed) first, then the Saves tables by vnum. Resolved once, on first use.
_level_fn = [None]
_level_fn_checked = [False]

def _ub_log(text):
	try:
		from datetime import datetime
		stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		f = open(eXLib.PATH + 'syserr_ub.txt', 'a')
		f.write('[%s] %s\n' % (stamp, text))
		f.close()
	except:
		pass

def GetLevelByVID(vid):
	"""Mob level for a live instance, straight from the client when it exposes it.

	Args:
		vid ([int]): Instance VID.

	Returns:
		[int or None]: The mob level, or None when the client gives none.
	"""
	if not _level_fn_checked[0]:
		_level_fn_checked[0] = True
		fn = None
		src = ''
		try:
			if buildin.hasattr(nonplayer, 'GetLevelByVID'):
				fn = nonplayer.GetLevelByVID
				src = 'nonplayer.GetLevelByVID'
			elif buildin.hasattr(chr, 'GetLevelByVID'):
				fn = chr.GetLevelByVID
				src = 'chr.GetLevelByVID'
		except:
			fn = None
		_level_fn[0] = fn
		_ub_log('[Compass] level source: ' + (src if src else 'Saves files only (client has no level API)'))
	fn = _level_fn[0]
	if fn is not None:
		try:
			lv = fn(vid)
			if lv:
				return int(lv)
		except:
			pass
	return None

#Possible game phases
PHASE_LOGIN = 1
PHASE_SELECT = 2
PHASE_GAME = 5

#Minumum number of empty slots for the inventory to be considered full
INV_FULL_MIN_EMPTY = 0
MAX_INVENTORY_SIZE = 90

#Skip python select answers
def skipAnswers(event_answers, hook=False):
	"""
	Selects the event to be answers.
	if hook=True will avoid quest answers from showing on screen, the caller is then resposible for removing the hook afterwards by calling showAnswers.

	Args:
		event_answers ([list]): A list containing the index of the answers.
		hook ([boolean]): If true will hook quest answers, in order to not show it on screen.
	"""
	if hook:
		questHook.HookFunction()
	for index,answer in enumerate(event_answers,start=1):
		event.SelectAnswer(index,answer)

def showAnswers():
	"""
	Removes the quest hook, in order for quest answers to be displayed.
	"""
	Hooks.questHook.UnhookFunction()

def GetCurrentPhase():
	"""
	Returns the current phase of the game.

	Returns:
		[int]: Return the current phase of the game.
	"""
	return Hooks.GetCurrentPhase()

def IsInGamePhase():
	"""
	Check if is in game phase.

	Returns:
		[bool]: Returns True if is in game phase or False otherwise.
	"""
	return GetCurrentPhase() == PHASE_GAME

#Checks the number of free inventory slots on the base pages
def GetNumberOfFreeSlots():
	global player
	numItems = MAX_INVENTORY_SIZE
	for i in range(0,MAX_INVENTORY_SIZE):
		curr_id = player.GetItemIndex(i)
		if curr_id != 0:
			item.SelectItem(curr_id)
			s = item.GetItemSize()
			numItems-=s[0]*s[1]

	if numItems <= INV_FULL_MIN_EMPTY:
		return 0
	else:
		return numItems - INV_FULL_MIN_EMPTY

#Return the angle needed to rotate from x0,y0 to x1,y1
def GetRotation(x0,y0,x1,y1):
	"""
	Calculate the rotation for (x0,y0) be pointing to (x1,y1), in the game context.

	Args:
		x0 ([float]): X of point a.
		y0 ([float]): Y of point a.
		x1 ([float]): X of point b.
		y1 ([float]): Y of point b.

	Returns:
		[float]: Returns the rotation needed in the game context.
	"""
	x1_relative = x1-x0
	y1_relative = y1-y0
	try:
		rada = 180 * (math.acos(y1_relative/math.sqrt((x1_relative)**2 + (y1_relative)**2))) / math.pi + 180
		if x0 >= x1:
			rada = 360 - rada
	except:
		rada = 0
	return rada

#Rotate Main Character to  x,y
def RotateMainCharacter(x,y):
	"""
	Rotate main character to (x,y)

	Args:
		x ([float]): X coordinate of destination.
		y ([float]): Y coordinate of destination.
	"""
	my_x,my_y,my_z = player.GetMainCharacterPosition()
	chr.SelectInstance(player.GetMainCharacterIndex())
	rot = GetRotation(my_x,my_y,x,y)
	chr.SetRotation(rot)

def isPlayerCloseToPosition(position_x, position_y, max_dist=150):
	player_x, player_y, player_z = player.GetMainCharacterPosition()
	distance = dist(position_x, position_y, player_x, player_y)

	if distance < max_dist:
		return True

	return False

def GetInstanceByID(_id):
	for vid in eXLib.InstancesList:
		if not chr.HasInstance(int(vid)):
			continue
		if eXLib.IsDead(int(vid)):
			continue
		chr.SelectInstance(int(vid))
		if chr.GetRace() == _id:
			return int(vid)
	return -1

#Get current time in seconds
def GetTime():
	"""
	Return the time.

	Returns:
		[float]: Return the time.
	"""
	return app.GetTime()

# Monotonic game-time: app.GetTime() flows smoothly BUT resets to ~0 on every
# world load; the machine's wall clock (time.time) proved broken -- it freezes
# and jumps in 128-second blocks, so every wall-clock timer only fired at the
# jumps. This clock runs at game speed and stitches the resets together.
_monot_last = [0.0]
_monot_offset = [0.0]

def Monotonic():
	t = app.GetTime()
	if t < _monot_last[0]:
		_monot_offset[0] += _monot_last[0] - t   # world reload reset -> keep continuity
	_monot_last[0] = t
	return t + _monot_offset[0]

# True when the world is REALLY loaded and safe to touch UI/instances:
# calling Show()/churning widgets during the load sequence corrupts the heap
# (0xc0000374 crashes, see the Windows Application event log).
def WorldSettled():
	try:
		if not background.GetCurrentMapName():
			return False
		mVID = player.GetMainCharacterIndex()
		if not mVID:
			return False
		x, y, z = eXLib.GetPixelPosition(mVID)
		if buildin.abs(x) < 1.0 and buildin.abs(y) < 1.0:
			return False
	except:
		return False
	return True

# Total NPC sell value of the inventory, read from the client's own item
# data (the same prices the shop UI shows). Cached ~30s. Price getter is
# probed once -- clients expose it under different names.
_invValCache = [0.0, 0]      # (Monotonic, value)
_invValFn = [None]           # resolved attr name

def InventoryNpcValue():
	"""(total_yang, item_count) of the whole inventory at NPC prices."""
	now = Monotonic()
	if now - _invValCache[0] < 30.0:
		return _invValCache[1]
	if _invValFn[0] is None:
		for cand in ('GetSellPrice', 'GetItemValue', 'GetPrice', 'GetValue'):
			if buildin.hasattr(item, cand):
				_invValFn[0] = cand
				break
		if _invValFn[0] is None:
			_invValFn[0] = ''
	fn = getattr(item, _invValFn[0], None)
	total = 0
	count = 0
	if fn is not None:
		try:
			for i in range(MAX_INVENTORY_SIZE):
				v = player.GetItemIndex(i)
				if not v:
					continue
				item.SelectItem(v)
				price = fn(0)
				if price is None:
					continue
				try:
					c = player.GetItemCount(i) or 1
				except:
					c = 1
				total += int(price) * int(c)
				count += 1
		except:
			pass
	_invValCache[0] = now
	_invValCache[1] = (total, count)
	return _invValCache[1]

# Ack file for the EXTERNAL control panel (execution receipts, death reports).
# Timestamps are REAL wall time: the panel compares them with its own
# time.time() on the same machine (same clock source, quantized but consistent).
def AckIPC(key, arg, ok=True):
	try:
		line = '%d|%s|%s|%s\n' % (int(_walltime.time()), key, str(arg), 'ok' if ok else 'fail')
		p = eXLib.PATH + 'MT2Robs/IPC/ack.txt'
		data = ''
		try:
			data = open(p, 'r').read()
		except:
			pass
		data += line
		if len(data) > 16000:
			data = data[-8000:]
		f = open(p, 'w')
		f.write(data)
		f.close()
	except:
		pass

#Return a tupple, the first value is true or false according if the timer has been reached, and the second value is the current timer
#if first value is true or the old timer if false
def timeSleep(last_time,sleepTime):
	"""
	Helper function to simlate a timer.

	Args:
		last_time ([float]): The last time slept (seconds).
		sleepTime ([float]): The amount of sleep time (seconds).

	Returns:
		[(bool,float)]: Returns a bool that is true or false according if the timer has been reached, and a time containing the last time it slept.
	"""
	timer = GetTime()
	if(last_time<timer-sleepTime):
		return(True,timer)
	return(False,last_time)

def dist(x1,y1,x2,y2):
	"""
	Return distance between 2 points.

	Returns:
		[float]: Returns distance between points.
	"""
	return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# ===== MANUAL-INTERVENTION-STOPS-MOVEMENT (driven by TimeFunctionHandler.OnUpdate) =====
# While the shared Movement singleton is actively pathing a bot (Movement.state == STATE_MOVING), watch
# the player's motion. If the character moves AGAINST the direction the bot last commanded (toward the
# next path point) for MANUAL_STOP_TICKS consecutive ~0.18s ticks, treat it as the user grabbing control
# -> stop pathing (StopMovement + cancel the in-flight move) and stop the bot drivers that would re-issue
# moves (EnergyBot).
_ms_last = None
_ms_away = 0
_ms_t = 0.0
MANUAL_STOP_MOVE_EPS = 30.0
MANUAL_STOP_TICKS = 2

def _manualStopCheck():
	global _ms_last, _ms_away, _ms_t
	import Movement as _MV
	mv = buildin.getattr(_MV, 'Movement', None)
	if mv is None or buildin.getattr(mv, 'state', 0) != _MV.STATE_MOVING:
		_ms_last = None; _ms_away = 0
		return
	_now = GetTime()
	_dt = _now - _ms_t
	if 0.0 <= _dt < 0.18:
		return
	_ms_t = _now
	path = buildin.getattr(mv, 'path', None)
	if not path:
		_ms_last = None; _ms_away = 0
		return
	try:
		px, py, pz = player.GetMainCharacterPosition()
	except:
		return
	tx, ty = path[0]
	if _ms_last is None:
		_ms_last = (px, py); _ms_away = 0
		return
	lx, ly = _ms_last
	_ms_last = (px, py)
	mvx = px - lx; mvy = py - ly
	moved = (mvx*mvx + mvy*mvy) ** 0.5
	if moved < MANUAL_STOP_MOVE_EPS:
		_ms_away = 0
		return
	cvx = tx - lx; cvy = ty - ly
	dot = mvx*cvx + mvy*cvy
	if dot < 0.0:
		_ms_away = _ms_away + 1
	else:
		_ms_away = 0
	if _ms_away >= MANUAL_STOP_TICKS:
		_ms_away = 0
		_manualStopTrigger()

def _manualStopTrigger():
	try:
		import Movement as _MV
		_MV.StopMovement()
		try:
			px, py, pz = player.GetMainCharacterPosition()
			chr.MoveToDestPosition(player.GetMainCharacterIndex(), int(px), int(py))
		except: pass
	except: pass
	try:
		import EnergyBot as _EB
		eb = buildin.getattr(_EB, 'instance', None)
		if eb is not None and buildin.hasattr(eb, '_stopBot'):
			_st = buildin.getattr(_EB, 'S_STOP', None)
			if _st is None or buildin.getattr(eb, 'state', None) != _st:
				eb._stopBot()
	except: pass

class TimeFunctionHandler(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.function_list = []

	def RegisterOnEventExit(self,time,function):
		self.function_list.append({"time":GetTime()+time,"function":function})

	def OnUpdate(self):
		try: _manualStopCheck()
		except: pass
		curTime = GetTime()
		to_del = []
		for i,func in enumerate(self.function_list):
			if curTime >= func["time"]:
				func["function"]()
				to_del.append(i)

		for i in to_del:
			del self.function_list[i]


class WallScheduler(ui.ScriptWindow):
	# Wall-clock delayed calls. The old TimeFunctionHandler schedules with
	# app.GetTime(); the log proved those timers fire instantly in some states
	# (all +8s checks stamped the same second), which broke the channel-switch
	# retries and the guild-donate handshake. This one uses time.time().
	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.queue = []
		self.Show()

	def Schedule(self, delay, function):
		self.queue.append((Monotonic() + delay, function))

	def CancelAll(self):
		self.queue = []

	def OnUpdate(self):
		if not self.queue:
			return
		now = Monotonic()
		due = [fn for t, fn in self.queue if t <= now]
		self.queue = [(t, fn) for t, fn in self.queue if t > now]
		for fn in due:
			try:
				fn()
			except:
				pass


# boss/metin vnums + optional levels used by StoneCompass (boss & metin finder)
# File format: Name=VNUM  or  Name=VNUM:LEVEL   (one per line)
try:
	FileManager.LoadDictFileWithLevels(FileManager.CONFIG_BOSSES_ID, BOSS_IDS, BOSS_LEVELS, int)
except Exception as _e:
	_ub_log('[Compass] boss table load ERR: ' + str(_e))
try:
	FileManager.LoadDictFileWithLevels(FileManager.CONFIG_METINS_ID, METIN_IDS, METIN_LEVELS, int)
except Exception as _e:
	_ub_log('[Compass] metin table load ERR: ' + str(_e))
# first load -> build+show the timer window; on reload reuse it (rebind its class).
try:
    function_handler
    function_handler.__class__ = TimeFunctionHandler
except NameError:
    function_handler = TimeFunctionHandler()
    function_handler.Show()
# wall-clock scheduler (see WallScheduler docstring) + one-shot clock diagnostic
try:
    ubScheduler
    ubScheduler.__class__ = WallScheduler
except NameError:
    ubScheduler = WallScheduler()
try:
    _ub_log('[Sched] app.GetTime=%.1f wall=%.1f' % (app.GetTime(), _walltime.time()))
except:
    pass
# one-shot dump: look for focus/minimize-related switches (the client pauses
# its loop when minimized -> all OnUpdate bots stop; maybe app exposes a flag)
try:
    _appattrs = dir(app)
    _ub_log('[App] focus/minim attrs: %s' % ', '.join(
        a for a in _appattrs if any(s in a.lower() for s in ('focus', 'minim', 'frame', 'skip', 'activ', 'icon', 'visib', 'background', 'idle', 'sleep'))))
    try:
        f = open(eXLib.PATH + 'syserr_ub_appdump.txt', 'w')
        f.write(', '.join(_appattrs))
        f.close()
    except:
        pass
except:
    pass
import Movement
