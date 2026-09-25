
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
    if HasArguments(module, ['GetCurrentMapName']):background = module

"""Persistant Data Exchange between modules"""

# Persistant Vars
# Updated Once Per Game Phase.

mainVID = 0             # Own unique ID
empireID = 0            # Own selected Empire
mainSkillGroup = 0      # Character Skill group
mainRace = 0            # Character gender and type (ninja, warrior, shaman , sura, lycan)
serverInfo = 0          # Server Info with Server IDs, IPs, Ports and other data

########
# Timers used in Bot
# Naming: "time_[Bot-Module]_[varName]"

time_BotBase_generalTimers   = {}
time_Movement_generalTimer  = 0
time_Movement_stoppedTimer  = 0

import Hooks

def resetTimers():
    import Data
    for key in Data.time_BotBase_generalTimers.keys():
        Data.time_BotBase_generalTimers[key] = 5
    Data.time_Movement_generalTimer = 5
    Data.time_Movement_stoppedTimer = 5

# After Phase switch
def _afterLoadPhase(phase,phaseWnd):
    import OpenLib, Data
    if phase == OpenLib.PHASE_GAME:
        Data.mainRace = net.GetMainActorRace()
        Data.mainSkillGroup = net.GetMainActorSkillGroup()
        Data.mainVID = player.GetMainCharacterIndex()
        Data.empireID = net.GetEmpireID()
        Data.serverInfo = net.GetServerInfo()
        resetTimers()

Hooks.registerPhaseCallback("DataPhaseCallback",_afterLoadPhase)
