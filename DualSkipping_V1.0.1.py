#Name: Dual Skipping 1.0.1
#Info: Skips unnecessary extruder swaps and the second drawing of the ooze shield
#Depend: GCode
#Type: postprocess
#Param: SkipSecondSkirt(int:1) Skip second Ooze Shield Line
#Param: SkipUnused(int:1) Skip unused Extruder Swap

## Written by Stefan Heule, Dim3nsioneer@gmx.ch
## This script is licensed under the Creative Commons - Attribution - Non-commercial - Share Alike (CC BY-NC-SA) terms

version = '1.0.1'

#History:
#V1.0:   based on the plugin CleanExtruderChange V1.5
#V1.0.1: flags for skirt skipping and hot end swap skipping

import re
import math

#####--------------------------------------------------------
#standard code-grabber and searcher, not plugin specific
def getValue(line, key, default = None):
	if not key in line or (';' in line and line.find(key) > line.find(';') and not ';LAYER:' in key):
		return default
	subPart = line[line.find(key) + len(key):] #allows for string lengths larger than 1
        if ';LAYER:' in key:
                m = re.search('^[+-]?[0-9]*', subPart)
        else:
                m = re.search('^[0-9]+\.?[0-9]*', subPart)
	if m == None:
		return default
	try:
		return float(m.group(0))
	except:
		return default
#end of standard code-grabber and searcher, not plugin specific
#####--------------------------------------------------------

#define variables
x = xl = 0
y = yl = 0
z = zl = 0
e = el = 0
de = 0
retract_length = 4.5
velo = 1
tot_time = 0
ext_time = 0
distance_step = 0
ext_time_list =[]
ext0_used=[]
ext1_used=[]
first_ext=[]
skirt_ct0=[]
skirt_ct1=[]
pos_type = 0 #Type of positioning: 0=absolute, 1=relative
pres_ext = 0 #Starts with extruder 0
prev_ext = 0
lasttemp = [0,0]
i=0
VeloFactor = 60
LayerNo = -1
fwretract_dist = 4.5
fwretract_velo = 30
fan = 0
active = 0
skirt_found = 0
retracted = False



#####--------------------------------------------------------
#function for time calculation of single line
def linetime(skip_list = 0):
        global line, x, y, z, e, pres_ext, xl, yl, zl, el, de, prev_ext, pos_type, velo, lasttemp, ext_time, ext_time_list, i, LayerNo, fwretract_dist, fwretract_velo, fan, distance_step, extrusion_length, active, skirt_found, retracted
        xl = x
        yl = y
        zl = z
        el = e
        prev_ext = pres_ext
        if ';DS-activation' in line:
                active = 1
        if ';LAYER:' in line:
                LayerNo = int(getValue(line,';LAYER:',LayerNo))
                if LayerNo >= 0:
                        skirt_found = 0
                if skip_list < 1:
                        first_ext.append(pres_ext) #present extruder is the one first used on new layer
                        ext0_used.append(0) #assume no usage of extruder 0 on new layer
                        ext1_used.append(0) #assume no usage of extruder 1 on new layer
                        skirt_ct0.append(0)
                        skirt_ct1.append(0)
        #if ';TYPE:WALL-OUTER' in line: #this means the present extruder is actually used
        if ';TYPE:WALL-OUTER' in line or ';TYPE:SUPPORT' in line: #this means the present extruder is actually used (Support requires special type 'WIPETOWER'!)
                if skip_list < 1:
                        if pres_ext == 0:
                                ext0_used[len(ext0_used)-1] = 1
                        else:
                                ext1_used[len(ext1_used)-1] = 1
        if ';TYPE:SKIRT' in line:
                skirt_found = skirt_found + 1
                if skip_list < 1:
                        if pres_ext == 0:
                                skirt_ct0[len(skirt_ct0)-1] = skirt_ct0[len(skirt_ct0)-1] + 1
                        else:
                                skirt_ct1[len(skirt_ct1)-1] = skirt_ct1[len(skirt_ct1)-1] + 1
        if 'G90' in line: #look for G90 command (absolute positioning)
                pos_type = 0
                #print 'absolute positioning activated'
        if 'G91' in line: #look for G91 command (relative positioning)
                pos_type = 1
                #print 'relative positioning activated'
        if ('G28' in line or 'G92' in line): #look for G28 or G92 command
                x = xl = getValue(line,'X',x)
                y = yl = getValue(line,'Y',y)
                z = zl = getValue(line,'Z',z)
                e = el = getValue(line,'E',e)
        if ('G0' in line or 'G1 ' in line): #look for G0 or G1 command (space after G1 is important!)
                x = pos_type * x + getValue(line,'X',(1-pos_type)*x)
                y = pos_type * y + getValue(line,'Y',(1-pos_type)*y)
                z = pos_type * z + getValue(line,'Z',(1-pos_type)*z)
                e = pos_type * e + getValue(line,'E',(1-pos_type)*e)
                velo = getValue(line,'F',velo)
        if ('M104' in line or 'M109' in line): #checks for heating command
                if getValue(line,'T',2) < 2: #extruder specified
                        lasttemp[int(getValue(line,'T',2))] = getValue(line,'S',0)
                else:
                        lasttemp[pres_ext] = getValue(line,'S',0)
                #print 'temperatures: ' + repr(lasttemp)
        if ('T0' in line or 'T1' in line) and not 'M' in line: #look for extruder change
                pres_ext = int(getValue(line,'T',None))
        if 'G10' in line or 'G11' in line: #fw-retract or priming
                velo = fwretract_velo*VeloFactor
                retracted = ('G10' in line)
        dx=x-xl
        dy=y-yl
        dz=z-zl
        de=e-el
        if pres_ext != prev_ext or getValue(line,'M',None) == 84: # a extruder change happened or release stepper (end of file)
                #print 'extruder time no. ' + repr(int(i)) + ': ' + repr(ext_time) + ', ex. ' + repr(prev_ext) + '->' + repr(pres_ext)
                if skip_list<1:
                        ext_time_list.append(ext_time)
                ext_time = 0
                i+=1
        distance_step = math.sqrt(dx*dx+dy*dy+dz*dz) #calculates the distance to the previous point
        if 'G10' in line or 'G11' in line: #retract
                time_step = fwretract_dist / (float(velo) / float(VeloFactor))
        else:
                #print 'line: ' + repr(line)
                #print 'velo: ' + repr(velo)
                #print 'VeloFactor: ' + repr(VeloFactor)
                time_step = float(distance_step) / (float(velo) / float(VeloFactor)) #calculates the time for the step
        return time_step
        
#####--------------------------------------------------------


#Grab the Gcode line-s one by one into the object lines
with open(filename, "r") as f: #r for read
	lines = f.readlines()
for line in lines: #Steps through the entire Gcode
                time_step = linetime(0) #produce list with times
                ext_time += time_step
ext_time_list.append(0)
ext0_used.append(0)
ext1_used.append(0)

eliminate_extswap = [0]*(len(first_ext)+1) #one more false so index -1 gets false
for i in range(len(first_ext)):
        if not eliminate_extswap[i]:
                if first_ext[i] == 0: #extruder 0 is first used extruder, so extruder 1 is used next
                        eliminate_extswap[i] = not (ext1_used[i] or ext1_used[i+1]) #ext1 is not used on present and on next layer: eliminate extruder swap
                else: #the other way round
                        eliminate_extswap[i] = not (ext0_used[i] or ext0_used[i+1]) #ext0 is not used on present and on next layer: eliminate extruder swap
                if i < len(first_ext)-1:
                        eliminate_extswap[i+1] = eliminate_extswap[i] #don't forget that the next swap should be the same

                
#print "ext0_used: " + repr(ext0_used)
#print "ext1_used: " + repr(ext1_used)
#print "first_ext: " + repr(first_ext)
#print "eliminate_extswap: " + repr(eliminate_extswap)
#print "skirt_ct0: " + repr(skirt_ct0)
#print "skirt_ct1: " + repr(skirt_ct1)

#define position variables
x = xl = 0
y = yl = 0
z = zl = 0
e = el = 0
de = 0
velo = 1
tot_time = 0
ext_time = 0
###ext_time_list =[] #the time list has to stay as it is
pos_type = 0 #Type of positioning: 0=absolute, 1=relative
pres_ext = 0 #Starts with extruder 0
prev_ext = 0
lasttemp = [0,0]
i=0
SuppressOutput = 0
LayerNo = -1
active = 0
SavedG0Line = ""
minHeight = 0
maxHeight = 0
skirt_found = 0
retracted_save = False

#Re-Running the time extraction and Writing the modified GCode
with open(filename, "w") as f:
	f.write("; This Gcode file has been analysed with DualSkipping version %s\n" % (version)) #tag the file
        for line in lines:
                time_step = linetime(1) #skip the list with times
                ext_time += time_step
                if SuppressOutput == 0 and 'G10 S1' in line and active == 1 and eliminate_extswap[LayerNo] and int(SkipUnused) == 1: #found swap retraction and  necessity to eliminate extruder swap
                        #print "SO=2, LayerNo: " + repr(LayerNo) + ", eliminate: " + repr(eliminate_extswap[LayerNo])
                        SuppressOutput = 2
                        f.write(";Extruder swap suppressed by DualSkipping V%s\n" % version)
                        f.write("G10\n")
                print "SkipSecondSkirt: " + repr(SkipSecondSkirt)
                if SuppressOutput == 0 and skirt_found == 2 and LayerNo >= 0 and int(SkipSecondSkirt) == 1:
                        SuppressOutput = 3
                        retracted_save = retracted
                        minHeight = 0
                if SuppressOutput == 0:
                        f.write(line)
                if SuppressOutput == 2:
                        if ('G1 Z' in line) or ('G92 E0' in line) or ('G0' in line) or (';TYPE:SUPPORT' in line) or ('G11' in line): #don't suppress these commands 
                                f.write(line)
                                if 'G11' in line:
                                        SuppressOutput = 0
                if SuppressOutput == 3: #elimination of second ooze shield line
                        if (';TYPE:SKIRT' in line):
                                f.write(";TYPE:SKIRT suppressed by DualSkipping V%s\n" % version)
                        if 'Z' in line: #saves eventual zHop height
                                minHeight = z
                        if 'G0' in line or ';LAYER:' in line: #if the skirt is ended by a G0
                                f.write(line)
                                f.write("G92 E%1.5f; adjust extrusion by DualSkipping V%s\n" % (e,version))
                                if minHeight > 0:
                                        f.write("G1 Z%1.2f\n" % minHeight)
                                if not retracted and retracted_save: #priming was suppressed
                                        f.write("G11\n")
                                SuppressOutput = 0
                                skirt_found = 0
                #print "SuppressOutput: " + repr(SuppressOutput)


print '------- End of debug run ------'



