#Name: Tweak At Z 3.99-RC1
#Info: Change printing parameters at a given height
#Help: TweakAtZ
#Depend: GCode
#Type: postprocess
#Param: targetZ(float:5.0) Z height to tweak at (mm)
#Param: targetL(int:) (ALT) Layer no. to tweak at
#Param: twLayers(int:1) No. of layers used for change
#Param: behavior(list:Tweak value and keep it for the rest,Tweak value for single layer only) Tweak behavior
#Param: speed(int:) New TOTAL Speed (%)
#Param: printspeed(int:) New PRINT Speed (%)
#Param: flowrate(int:) New General Flow Rate (%)
#Param: flowrateOne(int:) New Flow Rate Extruder 1 (%)
#Param: flowrateTwo(int:) New Flow Rate Extruder 2 (%)
#Param: platformTemp(int:) New Bed Temp (deg C)
#Param: extruderOne(int:) New Extruder 1 Temp (deg C)
#Param: extruderTwo(int:) New Extruder 2 Temp (deg C)
#Param: fanSpeed(int:) New Fan Speed (0-255 PWM)

## Written by Steven Morlock, smorloc@gmail.com
## Modified by Ricardo Gomez, ricardoga@otulook.com, to add Bed Temperature and make it work with Cura_13.06.04+
## Modified by Stefan Heule, Dim3nsioneer@gmx.ch, to add Flow Rate, restoration of initial values when returning to low Z, extended stage numbers, direct stage manipulation by GCODE-comments, UltiGCode regocnition, addition of fan speed, alternative selection by layer no., disabling extruder three, addition of flow rate for specific extruder
## This script is licensed under the Creative Commons - Attribution - Share Alike (CC BY-SA) terms

# Uses -
# M220 S<factor in percent> - set speed factor override percentage
# M221 S<factor in percent> - set flow factor override percentage
# M221 S<factor in percent> T<0-#toolheads> - set flow factor override percentage for single extruder
# M104 S<temp> T<0-#toolheads> - set extruder <T> to target temperature <S>
# M140 S<temp> - set bed target temperature
# M106 S<PWM> - set fan speed to target speed <S>

#history / changelog:
#V3.0.1: TweakAtZ-state default 1 (i.e. the plugin works without any TweakAtZ comment)
#V3.1:   Recognizes UltiGCode and deactivates value reset, fan speed added, alternatively layer no. to tweak at, extruder three temperature disabled by '#Ex3'
#V3.1.1: Bugfix reset flow rate
#V3.1.2: Bugfix disable TweakAtZ on Cool Head Lift
#V3.2:   Flow rate for specific extruder added (only for 2 extruders), bugfix parser, added speed reset at the end of the print
#V3.3:   Progress bar, tweaking over multiple layers, M605&M606 implemented, reset after one layer option, extruder three code removed, tweaking print speed

version = '3.99-RC1'

import re
import wx
import time
from wx.lib.pubsub import Publisher

def getValue(line, key, default = None):
	if not key in line or (';' in line and line.find(key) > line.find(';') and not ";TweakAtZ" in key and not ";LAYER:" in key):
		return default
	subPart = line[line.find(key) + len(key):] #allows for string lengths larger than 1
	if ";TweakAtZ" in key:
			m = re.search('^[0-3]', subPart)
	elif ";LAYER:" in key:
			m = re.search('^[+-]?[0-9]*', subPart)
	else:
			m = re.search('^[-]?[0-9]+\.?[0-9]*', subPart) #the minus at the beginning allows for negative values, e.g. for delta printers
	if m == None:
		return default
	try:
		return float(m.group(0))
	except:
		return default

with open(filename, "r") as f:
	lines = f.readlines()
TweakProp = {'speed': speed is not None and speed != '',
			 'flowrate': flowrate is not None and flowrate != '',
			 'flowrateOne': flowrateOne is not None and flowrateOne != '',
			 'flowrateTwo': flowrateTwo is not None and flowrateTwo != '',
			 'platformTemp': platformTemp is not None and platformTemp != '',
			 'extruderOne': extruderOne is not None and extruderOne != '',
			 'extruderTwo': extruderTwo is not None and extruderTwo != '',
			 'fanSpeed': fanSpeed is not None and fanSpeed != ''}
TweakPrintSpeed = printspeed is not None and printspeed != ''
TweakStrings = {'speed': "M220 S%f\n",
				'flowrate': "M221 S%f\n",
				'flowrateOne': "M221 T0 S%f\n",
				'flowrateTwo': "M221 T1 S%f\n",
				'platformTemp': "M140 S%f\n",
				'extruderOne': "M104 S%f T0\n",
				'extruderTwo': "M104 S%f T1\n",
				'fanSpeed': "M106 S%d\n"}
target_values = {}
for key in TweakProp:
	target_values[key]=eval(key)
old = {'speed': 100, 'flowrate': 100, 'flowrateOne': 100, 'flowrateTwo': 100, 'platformTemp': -1, 'extruderOne': -1, 'extruderTwo': -1, 'fanSpeed': 0, 'state': -1}
try:
	twLayers = max(int(twLayers),1) #for the case someone entered something as 'funny' as -1
except:
	twLayers = 1
pres_ext = 0
done_layers = 0
z = 0
x = None
y = None
layer = -100000 #layer no. may be negative (raft) but never that low
state = 1 #state 0: deactivated, state 1: activated, state 2: active, but below z, state 3: active and partially executed (multi layer), state 4: active and passed z
SetOnMachine = False #Used for reset of values (ok for Marlin/Sprinter), has to be set to 1 for UltiGCode (work-around for missing default values)
lastpercentage = 0
i = 0
l = len(lines)


try:
	targetL_i = int(targetL)
	targetZ = 100000
except:
	targetL_i = -100000

if targetL_i > -100000:
	wx.CallAfter(Publisher().sendMessage, "pluginupdate", "OpenPluginProgressWindow;TweakAtZ;Tweak At Z plugin is executed at layer " + str(targetL_i))
else:
	wx.CallAfter(Publisher().sendMessage, "pluginupdate", "OpenPluginProgressWindow;TweakAtZ;Tweak At Z plugin is executed at height " + str(targetZ)+"mm")
with open(filename, "w") as file:
	for line in lines:
		if int(i*100/l) > lastpercentage: #progressbar
			lastpercentage = int(i*100/l)
			wx.CallAfter(Publisher().sendMessage, "pluginupdate", "Progress;" + str(lastpercentage))
		if not ('M84' in line or 'M25' in line or ('G1' in line and TweakPrintSpeed and state==3)):
			file.write(line)
		SetOnMachine = ('FLAVOR:UltiGCode' in line) or SetOnMachine #Flavor is UltiGCode! No reset of values
		if ';TweakAtZ-state' in line: #checks for state change comment
				state = getValue(line, ';TweakAtZ-state', state)
		if ';Small layer' in line: #checks for begin of Cool Head Lift
				old['state'] = state
				state = 0
		if ('G4' in line) and old['state'] > -1:
				old['state'] = -1
		if ';LAYER:' in line: #new layer no. found
			layer = getValue(line, ';LAYER:', layer)
			if targetL_i > -100000: #target selected by layer no.
				if state == 2 and layer >= targetL_i: #determine targetZ from layer no.
					targetZ = z + 0.001
		if (getValue(line, 'T', None) is not None) and (getValue(line, 'M', None) is None): #looking for single T-command
				pres_ext = getValue(line, 'T', pres_ext)
		if 'M190' in line or 'M140' in line and state < 3: #looking for bed temp, stops after target z is passed
				old['platformTemp'] = getValue(line, 'S', old['platformTemp'])
		if 'M109' in line or 'M104' in line and state < 3: #looking for extruder temp, stops after target z is passed
			if getValue(line, 'T', pres_ext) == 0:
				old['extruderOne'] = getValue(line, 'S', old['extruderOne'])
			elif getValue(line, 'T', pres_ext) == 1:
				old['extruderTwo'] = getValue(line, 'S', old['extruderTwo'])
		if 'M107' in line: #fan is stopped; is always updated in order not to miss switch off for next object
				old['fanSpeed'] = 0
		if 'M106' in line and state < 3: #looking for fan speed
				old['fanSpeed'] = getValue(line, 'S', old['fanSpeed'])
		if 'M221' in line and state < 3: #looking for flow rate
			tmp_extruder = getValue(line,'T',None)
			if tmp_extruder == None: #check if extruder is specified
				old['flowrate'] = getValue(line, 'S', old['flowrate'])
			elif tmp_extruder == 0: #first extruder
				old['flowrateOne'] = getValue(line, 'S', old['flowrateOne'])
			elif tmp_extruder == 1: #second extruder
				old['flowrateOne'] = getValue(line, 'S', old['flowrateOne'])
		if ('M84' in line or 'M25' in line):
			if state>0 and speed is not None and speed != '': #'finish' commands for UM Original and UM2
				file.write("M220 S100 ; speed reset to 100% at the end of print\n")
				file.write("M117                     \n")
			file.write(line)
		if 'G1' in line or 'G0' in line:
			newZ = getValue(line, 'Z', z)
			x = getValue(line, 'X', None)
			y = getValue(line, 'Y', None)
			e = getValue(line, 'E', None)
			f = getValue(line, 'F', None)
			if TweakPrintSpeed and state==3:
				if 'G1' in line and x != None and y != None and f != None and e != None and newZ==z: #check for pure print movement in target range
					file.write("G1 F%d X%1.3f Y%1.3f E%1.5f\n" % (int(f/100.0*float(printspeed)),getValue(line,'X'),getValue(line,'Y'),getValue(line,'E')))
			else: #G1 command but not a print movement
				file.write(line)
			if (newZ != z) and (x is not None) and (y is not None): #no tweaking on retraction hops which have no x and y coordinate
				z = newZ
				if z < targetZ and state == 1:
					state = 2
				if z >= targetZ and state == 2:
					state = 3
					done_layers = 0
					if SetOnMachine: #Parameters have to be stored in the printer (UltiGCode) and the tweaking has to happen within one layer
						file.write("M605 ;stores parameters before tweaking\n")
						twLayers = 1
					elif behavior == 1: #single layer tweak only and then reset
						twLayers = 1
					else:
						for key in TweakProp:
							if TweakProp[key] and target_values[key] == -1: #if present value is not known, tweak it in one layer
								twLayers = 1
				if z >= targetZ and state == 3:
					if TweakPrintSpeed and behavior == 0:
						twLayers = done_layers + 1
					if twLayers-done_layers>0: #still layers to go?
						if targetL_i > -100000:
							file.write(";TweakAtZ V%s: executed at Layer %d\n" % (version,layer))
							file.write("M117 Printing... tw@L%4d\n" % layer)
						else:
							file.write(";TweakAtZ V%s: executed at %1.2f mm\n" % (version,z))
							file.write("M117 Printing... tw@%5.1f\n" % z)
						for key in TweakProp:
							if TweakProp[key]:
								file.write(TweakStrings[key] % float(old[key]+(float(target_values[key])-float(old[key]))/float(twLayers)*float(done_layers+1)))
						done_layers += 1
					else:
						state = 4
						if behavior == 1: #reset values after one layer
							if targetL_i > -100000:
								file.write(";TweakAtZ V%s: reset on Layer %d\n" % (version,layer))
							else:
								file.write(";TweakAtZ V%s: reset at %1.2f mm\n" % (version,z))
							if not SetOnMachine: #executes only for UM Original and UM2 with RepRap flavor
								for key in TweakProp:
									if TweakProp[key]:
										file.write(TweakStrings[key] % float(old[key]))
							else:
								file.write("M606 ;recalls saved settings\n")
				if z < targetZ and state >= 3: #re-activates the plugin if executed by pre-print G-command, resets settings
					state = 2
					done_layers = 0
					if targetL_i > -100000:
						file.write(";TweakAtZ V%s: reset below Layer %d\n" % (version,targetL_i))
					else:
						file.write(";TweakAtZ V%s: reset below %1.2f mm\n" % (version,targetZ))
					if not SetOnMachine: #executes only for UM Original and UM2 with RepRap flavor
						for key in TweakProp:
							if TweakProp[key]:
								file.write(TweakStrings[key] % float(old[key]))
					else:
						file.write("M606 ;recalls saved settings\n")
		i+=1
wx.CallAfter(Publisher().sendMessage, "pluginupdate", "Progress;100")
time.sleep(1)
wx.CallAfter(Publisher().sendMessage, "pluginupdate", "ClosePluginProgressWindow")
