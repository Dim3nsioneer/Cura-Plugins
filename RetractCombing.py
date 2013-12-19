#Name: Retract while combing V13.12-test
#Info: Retracts at specified height during combing
#Depend: GCode
#Type: postprocess
#Param: minZ(float:4.99) starting Z (mm)
#Param: maxZ(float:5.01) ending Z (mm)
#Param: minDist(float:2.0) minimum distance for retract (mm)
#Param: speed(float:30) Retract Speed (mm/s)
#Param: retractdistance(float:4.5) Retract Distance (mm)
#Param: lift(float:0.0) Lift head during Retract (mm)

## Written by Stefan Heule, Dim3nsioneer@gmx.ch
## This script is licensed under the Creative Commons - Attribution - Share Alike (CC BY-SA) terms


import re
import math

def getValue(line, key, default = None):
	if not key in line or (';' in line and line.find(key) > line.find(';')):
		return default
	subPart = line[line.find(key) + 1:]
	m = re.search('^[0-9]+\.?[0-9]*', subPart)
	if m == None:
		return default
	try:
		return float(m.group(0))
	except:
		return default

with open(filename, "r") as f:
	lines = f.readlines()

x = oldx = 0
y = oldy = 0
z = oldz = 0
e = olde = 0
gtype = None
combing_active = 0
in_range = 0
pos_type = 0 #Type of positioning: 0=absolute, 1=relative
buffered_gcode = []
total_length = 0
g1speed = 0

with open(filename, "w") as f:
        f.write(";This GCODE was altered by RetractCombing\n")
	for line in lines:
                oldx = x
                oldy = y
                oldz = z
                olde = e
                gtype = getValue(line,'G',None)
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
                                g1speed = getValue(line,'F',g1speed) #saves the last G1 speed
                if z >= minZ and z <= maxZ: #check if z is in range
                        in_range = 1
                        if combing_active == 0 and gtype == 0: #activate flag for combing
                                combing_active = 1
                        if combing_active == 1 and gtype == 1: #deactivate flag for combing
                                combing_active = 0
                                if total_length >= minDist:
                                        f.write("G1 F%d E%1.5f; added by RectractCombing\n" % (int(speed*60),(1-pos_type)*olde-retractdistance)) #retract
                                        if lift != 0:
                                                f.write("G0 Z%1.2f; added by RetractCombing\n" % float((1-pos_type)*z+lift)) #lift head
                                        for buffer_line in buffered_gcode: #writes the buffer
                                                f.write(buffer_line)
                                        buffered_gcode = [] #clears the buffer
                                        if lift != 0:
                                                f.write("G0 Z%1.2f; added by RetractCombing\n" % float((1-pos_type)*z)) #lower head
                                        f.write("G1 F%d E%1.5f; added by RectractCombing\n" % (int(speed*60),(1-pos_type)*olde)) #re-retract
                                        f.write("G1 F%d; added by RetractCombing\n" % int(g1speed))
                                else:
                                        for buffer_line in buffered_gcode: #writes the buffer
                                                f.write(buffer_line)
                                        buffered_gcode = [] #clears the buffer
                                total_length = 0 #resets the length check
                else:
                        in_range = 0
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
