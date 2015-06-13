#Name: Retract while combing V15.06.1
#Info: Retracts at specified height during combing
#Help: RetractWhileCombing
#Depend: GCode
#Type: postprocess
#Param: minZ(float:4.99) Starting Z (mm)
#Param: maxZ(float:5.01) Ending Z (mm)
#Param: minL(int:) (ALT) Starting Layer no.
#Param: maxL(int:) (ALT) Ending Layer no.
#Param: FirstLast(bool:false) First and Last layer only (override)
#Param: minDist(float:2.0) Minimum Distance for Retract (mm)
#Param: speed(float:30) Retract Speed (mm/s)
#Param: retractdistance(float:4.5) Retract Distance (mm)
#Param: lift(float:0.0) Lift Head during Retract (mm)

## Written by Stefan Heule, Dim3nsioneer@gmx.ch
## This script is licensed under the Creative Commons - Attribution - Non-commercial - Share Alike (CC BY-NC-SA) terms

## Changelog:
## V14.01:   initial version
## V14.07:   including flavor 'RepRap volumetric'
## V15.02:   bugfix for dunking into priming heap at start, progress bar included, First-and-last-layer-option
## V15.06:   uses Cura progress bar instead of its own
## V15.06.1: bugfix for failure on cold head lift together with first/last option and small last layer

version = '15.06.1'

import re
import math
import wx
import time

try:
	#MacOS release currently lacks some wx components, like the Publisher.
	from wx.lib.pubsub import Publisher
except:
	Publisher = None

def getValue(line, key, default = None):
	if not key in line or (';' in line and line.find(key) > line.find(';') and not ("LAYER:" in key or 'Layer count:'in key)):
		return default
	subPart = line[line.find(key) + len(key):] #allows for string lengths larger than 1
	if ";LAYER:" in key or ";Layer count:" in key:
		m = re.search('^[+-]?[0-9]*', subPart)
	else:
		m = re.search('^[0-9]+\.?[0-9]*', subPart)
	if m == None:
		return default
	try:
		return float(m.group(0))
	except:
		return default

layer = -100000 #layer no. may be negative (raft) but never that low
try:
	minL_i = int(minL)
except:
	minL_i = -100000
try:
	maxL_i = int(maxL)
except:
	maxL_i = -100000
if minL_i > -100000 and maxL_i == -100000: #if only starting layer is specified
	maxL_i = minL_i

if minL_i > -100000:
	minZ = maxZ = 100000

with open(filename, "r") as f:
	lines = f.readlines()

lastpercentage = 0
i = 0
l = len(lines)

x = oldx = 0
y = oldy = 0
z = oldz = 0
e = olde = 0
gtype = None
combing_active = 0
in_range = 0
pos_type = 0 #Type of positioning: 0=absolute, 1=relative
G1MovesCtr = 0
buffered_gcode = []
total_length = 0
g1speed = 0
flavor = 0 #0:RepRap GCode, 1:UltiGCode, 2: RepRap volumetric
NoOfLayers = 1

with open(filename, "w") as f:
	for line in lines:
		if 'FLAVOR:UltiGCode' in line: #Flavor is UltiGCode! Use G10 and G11 instead of G1 Ex
			flavor = 1
		if ('G10' in line or 'G11' in line) and flavor == 0: #Flavor is volumetric RepRap
			flavor = 2
	for line in lines:
		if int(i*100/l) > lastpercentage and (Publisher is not None): #progressbar
			lastpercentage = int(i*100/l)
			if minL_i > -100000:
				wx.CallAfter(Publisher().sendMessage, "pluginupdate", ("RetractWC Layer %d" % minL_i) + ";" + str(lastpercentage))
			else:
				wx.CallAfter(Publisher().sendMessage, "pluginupdate", ("RetractWC %1.2f" % minZ) + "mm;" + str(lastpercentage))
		oldx = x
		oldy = y
		oldz = z
		olde = e
		gtype = getValue(line,'G',None)
		if 'Layer count:' in line: #no. of layers found
			NoOfLayers = getValue(line, 'Layer count: ', NoOfLayers)
		if 'LAYER:' in line: #new layer no. found
			layer = getValue(line, 'LAYER:', layer)
			if minL_i > -100000: #target selected by layer no.
				if in_range == 0 and layer >= minL_i and layer <= maxL_i: #determine minZ from layer no.
					minZ = z + 0.001
				if in_range == 1 and layer > maxL_i: #determine maxZ from layer no.
					maxZ = z
		if gtype == 90: #look for G90 command (absolute positioning)
			pos_type = 0
		if gtype == 91: #look for G91 command (relative positioning)
			pos_type = 1
		if gtype == 28 or gtype == 92: #look for G28 or G92 command
			x = oldx = getValue(line,'X',x)
			y = oldy = getValue(line,'Y',y)
			z = oldz = getValue(line,'Z',z)
			e = olde = getValue(line,'E',e)
		if gtype == 1 or gtype == 0: #check for movement
			x = pos_type * x + getValue(line,'X',(1-pos_type)*x)
			y = pos_type * y + getValue(line,'Y',(1-pos_type)*y)
			z = pos_type * z + getValue(line,'Z',(1-pos_type)*z)
			e = pos_type * e + getValue(line,'E',(1-pos_type)*e)
			if gtype == 1:
				G1MovesCtr += 1
				g1speed = getValue(line,'F',g1speed) #saves the last G1 speed
		if FirstLast == 1:
			if layer == 0 or layer == NoOfLayers-1:
				in_range = 1
			else:
				in_range = 0
		else: #FirstLast option not activated
			if z >= minZ and z <= maxZ: #check if z is in range
				in_range = 1
			else:
				in_range = 0
		if in_range == 1:
                        if ';Small layer' in line: #de-activate plugin during cold head lift
                                combing_active = -1
                        if combing_active == -1 and gtype == 4: #reactivate plugin after cold head lift
                                combing_active = 0
			if combing_active == 0 and gtype == 0: #activate flag for combing
				combing_active = 1
			if combing_active == 1 and gtype == 1: #deactivate flag for combing
				combing_active = 0
				if total_length >= minDist:
					if flavor == 0: #RepRap
						f.write("G1 F%d E%1.5f; added by RetractWhileCombing V%s\n" % (int(speed*60),(1-pos_type)*olde-retractdistance,version)) #retract
					else: #UltiGCode or volumetric RepRap
						f.write("G10; added by RetractWhileCombing V%s\n" % version) #retract
					if lift != 0 and G1MovesCtr != 1: #no lift at first G1 moves to avoid dunking into priming heap
						f.write("G0 Z%1.2f; added by RetractWhileCombing V%s\n" % (float((1-pos_type)*z+lift),version)) #lift head
					for buffer_line in buffered_gcode: #writes the buffer
						f.write(buffer_line)
					buffered_gcode = [] #clears the buffer
					if lift != 0:
						f.write("G0 Z%1.2f; added by RetractWhileCombing V%s\n" % (float((1-pos_type)*z),version)) #lower head
					if flavor == 0: #RepRap
						f.write("G1 F%d E%1.5f; added by RetractWhileCombing V%s\n" % (int(speed*60),(1-pos_type)*olde,version)) #priming
						f.write("G1 F%d; added by RetractWhileCombing V%s\n" % (int(g1speed),version))
					else: #UltiGCode or volumetric RepRap
						f.write("G11; added by RetractWhileCombing V%s\n" % version) #priming
				else:
					for buffer_line in buffered_gcode: #writes the buffer
						f.write(buffer_line)
					buffered_gcode = [] #clears the buffer
				total_length = 0 #resets the length check
		else:
			if combing_active == 1: #unfinished business: no retract
				combing_active = 0
				for buffer_line in buffered_gcode: #writes the buffer
					f.write(buffer_line)
				buffered_gcode = [] #clears the buffer
		if combing_active == 1:
			buffered_gcode.append(line)
			total_length += math.sqrt((x-oldx)*(x-oldx)+(y-oldy)*(y-oldy)) #calculates distance
		else:
			f.write(line)
		i+=1
