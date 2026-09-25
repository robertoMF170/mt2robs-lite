
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
    if HasArguments(module, ['SetCameraMaxDistance']):app = module
    if HasArguments(module, ['GetCurrentMapName']):background = module
    if HasArguments(module, ['ScriptWindow']):ui = module

from MT2Robs.Modules.OpenLog import DebugPrint
import eXLib
import OpenLib, OpenLog, Data

"""
Module of Movement.
Allows the character to walk to a position using pathfinding (same map only).
"""

STATE_FINISH = 1
STATE_MOVING = 2
STATE_STOPPED = 0

NO_PATH_FOUND = 0
DESTINATION_REACHED = 1
MOVING = 1

TIME_STOPPED_ALLOWED = 3

#Time after each loop
TIME_WAIT = 0.2

class MovementDialog(ui.ScriptWindow):
    def __init__(self):
        ui.ScriptWindow.__init__(self)
        self.Show()
        self.path = list()
        self.currDestinationX = 0
        self.currDestinationY = 0
        self.state = STATE_STOPPED
        Data.time_Movement_stoppedTimer = OpenLib.GetTime()
        self.lastPlayerPos = (0,0)
        self.maxDistanceToDest = 50
        Data.time_Movement_generalTimer = 0

    def Stop(self):
        self.state = STATE_STOPPED
        self.currDestinationX = 0
        self.currDestinationY = 0

    #Move to a specific position using pathfinding
    #maxDist is the maximum distance where the algorithm stop
    #callback is an optional function that will be called when arrive to the target
    def GoToPositionAvoidingObjects(self,x,y,maxDist=250,callback=None):
        self.maxDistanceToDest = maxDist
        self.callback = callback
        if(round(x) != round(self.currDestinationX) or round(y) != round(self.currDestinationY)):
            my_x,my_y,z = player.GetMainCharacterPosition()
            OpenLog.DebugPrint("[MOVEMENT] Finding Path from ("+str(my_x)+","+str(my_y)+") to " + "("+str(x)+","+str(y)+")")
            self.path = eXLib.FindPath(my_x,my_y,x,y)
            OpenLog.DebugPrint("[MOVEMENT] Path Found with "+str(len(self.path)) +" points")
            if(len(self.path)>0):
                self.currDestinationX = x
                self.currDestinationY = y
                self.state = STATE_MOVING
                Data.time_Movement_stoppedTimer = OpenLib.GetTime()
                return MOVING
            else:
                self.state = STATE_STOPPED
                self.currDestinationX = 0
                self.currDestinationY = 0
                return NO_PATH_FOUND
        else:
            if(self.state == STATE_FINISH):
                self.state = STATE_STOPPED
                return DESTINATION_REACHED
            elif(self.state == STATE_MOVING):
                return MOVING
            else:
                return self.GoToPositionAvoidingObjects(x+1,y-1,maxDist,callback)


    def GoStraightToPoint(self,x,y):
        OpenLib.RotateMainCharacter(x,y)
        chr.MoveToDestPosition(player.GetMainCharacterIndex(),x, y)

    def OnUpdate(self):
        val, Data.time_Movement_generalTimer = OpenLib.timeSleep(Data.time_Movement_generalTimer,TIME_WAIT)
        if not val or not OpenLib.IsInGamePhase():
            return

        if not (self.state == STATE_MOVING) or len(self.path) == 0:
            return

        next_x,next_y = self.path[0]
        my_x,my_y,my_z = player.GetMainCharacterPosition()
        maxdst = 40
        if(len(self.path) == 1):
            maxdst = self.maxDistanceToDest
        if OpenLib.dist(next_x,next_y,my_x,my_y) < maxdst:
            self.path.pop(0)
            if(len(self.path) == 0):
                #Destination Reached
                self.state = STATE_FINISH
                if(self.callback!=None):
                    self.callback()
                    self.callback = None
                self.currDestinationX = 0
                self.currDestinationY = 0
                return
            else:
                next_x,next_y = self.path[0]

        if self.lastPlayerPos == (my_x,my_y):
            val, Data.time_Movement_stoppedTimer = OpenLib.timeSleep(Data.time_Movement_stoppedTimer,TIME_STOPPED_ALLOWED)
            if val:
                #If is stuck
                self.path = eXLib.FindPath(my_x,my_y,self.currDestinationX,self.currDestinationY)

        self.lastPlayerPos = (my_x,my_y)
        self.GoStraightToPoint(next_x,next_y)

    def __del__(self):
        ui.ScriptWindow.__del__(self)


def GoToPositionAvoidingObjects(x,y,maxDist=250,callback=None,mapName=None,mapLinks=[]):
    """
    Move to a specific position using pathfinding (current map only;
    mapName/mapLinks are accepted for compatibility and ignored).

    Args:
        x ([float]): Destenation X.
        y ([float]):  Destanation Y.
        maxDist (int, optional): Distance to turn points to be considered a reached point. Defaults to 250.
        callback ([function], optional): Function callback called after reach destination. Defaults to None.

    Returns:
        [object]: Returns NO_PATH_FOUND or MOVING / DESTINATION_REACHED.
    """
    return Movement.GoToPositionAvoidingObjects(x,y,maxDist,callback)


def GoToPosition(x,y):
    """
    Move to (x,y) position without using pathfinding.
    Args:
        x ([float]): x
        y ([float]): y
    """
    Movement.GoStraightToPoint(x,y)

def StopMovement():
    """
    Stop Moving Action.
    """
    Movement.Stop()

Movement = MovementDialog()
