
import eXLib

"""
Module resposible for handling file load operations.
"""

CONFIG_BOSSES_ID = eXLib.PATH + 'MT2Robs/Saves/boss_ids.txt'
CONFIG_METINS_ID = eXLib.PATH + 'MT2Robs/Saves/metin_ids.txt'


#For parsing
def boolean(val):
	"""Transforms the string into a boolean value.

	Args:
		val ([str]): Input string.

	Returns:
		[bool]: Output boolean value.
	"""
	if val == "True" or val == "1":
		return True
	else:
		return False

#Load every setting from a file in dictionary format
def LoadDictFile(file,dict_,cast_type):
	"""Loads every setting from a file in dictionary format.

	Args:
		file ([str]): File path containing the settings.
		dict_ ([dict]): A dictionary, that will be used to appending the settings names as keys and settings values as values.
		cast_type ([object]): A cast to be applied to every single value before appending to the dictionary.
	"""
	with open(file,'r') as f:
		for line in f:
			line = line.rstrip()
			if not line or line.startswith('#') or line.lstrip().startswith('#') or '=' not in line:
				continue
			lst = line.split('=')
			if len(lst) < 2 or not lst[1]:
				continue
			dict_[cast_type(lst[1])] = lst[0]

#Load a vnum file supporting an optional level suffix: 'Name=VNUM' or 'Name=VNUM:LEVEL'.
#Fills names_dict {vnum: name} and levels_dict {vnum: level|None}.
def LoadDictFileWithLevels(file,names_dict,levels_dict,cast_type):
	"""Loads a vnum table with optional per-vnum levels.

	Args:
		file ([str]): File path containing the table (Name=VNUM[:LEVEL] per line).
		names_dict ([dict]): Filled as {vnum: name}.
		levels_dict ([dict]): Filled as {vnum: level} (level None when not given).
		cast_type ([object]): Cast applied to the vnum.
	"""
	with open(file,'r') as f:
		for line in f:
			line = line.rstrip()
			if not line or line.startswith('#') or line.lstrip().startswith('#') or '=' not in line:
				continue
			lst = line.split('=')
			if len(lst) < 2 or not lst[1]:
				continue
			value = lst[1]
			level = None
			if ':' in value:
				value, lv = value.split(':', 1)
				try:
					level = int(lv)
				except:
					level = None
			if not value:
				continue
			vnum = cast_type(value)
			names_dict[vnum] = lst[0]
			levels_dict[vnum] = level
