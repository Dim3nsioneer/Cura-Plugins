#Name: Extruder Idle
#Info: Switches unused extruder off if idle for longer than specified time
#Depend: GCode
#Type: postprocess
#Param: MinIdleTime(float:120) Minimum Idle Time (typical 120s)
#Param: IdleTemp0(float:0) Temperature First Extruder during Idle Time
#Param: IdleTemp1(float:0) Temperature Second Extruder during Idle Time


version = "1.0.1"

import re
import math

#####--------------------------------------------------------
#standard code-grabber and searcher, not plugin specific
def getValue(line, key, default = None):
	if not key in line or (';' in line and line.find(key) > line.find(';')):
		return default
	subPart = line[line.find(key) + 1:]
	m = re.search('^[+-]?[0-9]+\.?[0-9]*', subPart)
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
velo = 1
tot_time = 0
ext_time = 0
ext_time_list =[]
pos_type = 0 #Type of positioning: 0=absolute, 1=relative
pres_ext = 0 #Starts with extruder 0
prev_ext = 0
lasttemp = [0,0]
IdleTemp = [IdleTemp0,IdleTemp1]
i=0


#####--------------------------------------------------------
#function for time calculation of single line
def linetime(skip_list = 0):
        global line, x, y, z, e, pres_ext, xl, yl, zl, el, prev_ext, pos_type, velo, lasttemp, ext_time, ext_time_list, i
        xl = x
        yl = y
        zl = z
        el = e
        prev_ext = pres_ext
        if getValue(line,'G',None) == 90: #look for G90 command (absolute positioning)
                pos_type = 0
                print 'absolute positioning activated'
        if getValue(line,'G',None) == 91: #look for G91 command (relative positioning)
                pos_type = 1
                print 'relative positioning activated'
        if getValue(line,'G',None) == 28 or getValue(line,'G',None) == 92: #look for G28 or G92 command
                x = xl = getValue(line,'X',x)
                y = yl = getValue(line,'Y',y)
                z = zl = getValue(line,'Z',z)
                e = el = getValue(line,'E',e)
        if getValue(line,'G',None) == 0 or getValue(line,'G',None) == 1: #look for G0 or G1 command
                x = pos_type * x + getValue(line,'X',(1-pos_type)*x)
                y = pos_type * y + getValue(line,'Y',(1-pos_type)*y)
                z = pos_type * z + getValue(line,'Z',(1-pos_type)*z)
                e = pos_type * e + getValue(line,'E',(1-pos_type)*e)
                velo = getValue(line,'F',velo)
        if getValue(line,'M',None) == 104 or getValue(line,'M',None) == 109: #checks for heating command
                if getValue(line,'T',2) < 2: #extruder specified
                        lasttemp[int(getValue(line,'T',2))] = getValue(line,'S',0)
                else:
                        lasttemp[pres_ext] = getValue(line,'S',0)
                print 'temperatures: ' + repr(lasttemp)
        if getValue(line,'T',None) is not None and getValue(line,'M',None) is None: #look for extruder change
                pres_ext = int(getValue(line,'T',None))
        dx=x-xl
        dy=y-yl
        dz=z-zl
        de=e-el
        if pres_ext != prev_ext: # a extruder change happened
                print 'extruder time no. ' + repr(int(i)) + ': ' + repr(ext_time) + ', ex. ' + repr(prev_ext) + '->' + repr(pres_ext)
                if skip_list<1:
                        ext_time_list.append(ext_time)
                ext_time = 0
                i+=1
        distance_step = math.sqrt(dx*dx+dy*dy+dz*dz) #calculates the distance to the previous point
        if distance_step == 0 and math.fabs(de) > 0: #only filament movement, may be retract
                time_step = math.fabs(de) / (float(velo) / 60.0)
        else:
                time_step = distance_step / (float(velo) / 60.0) #calculates the time for the step
        return time_step
        
#####--------------------------------------------------------


#Grab the Gcode line-s one by one into the object lines
with open(filename, "r") as f: #r for read
	lines = f.readlines()
for line in lines: #Steps through the entire Gcode
                time_step = linetime(0) #produce list with times
                ext_time += time_step
ext_time_list.append(0)

#define position variables
x = xl = 0
y = yl = 0
z = zl = 0
e = el = 0
velo = 1
tot_time = 0
ext_time = 0
###ext_time_list =[] #the time list has to stay as it is
pos_type = 0 #Type of positioning: 0=absolute, 1=relative
pres_ext = 0 #Starts with extruder 0
prev_ext = 0
lasttemp = [0,0]
i=0
fired = 1

#Re-Running the time extraction and Writing the modified GCode
with open(filename, "w") as f:
	f.write("; This Gcode file has been analysed with ExtruderIdle version %s\n" % (version)) #tag the file
        for line in lines:
                time_step = linetime(1) #skip the list with times
                ext_time += time_step
                if prev_ext != pres_ext:
                        f.write(";Extruder time: %1.1f\n" % ext_time_list[i])
                        if ext_time_list[i] >= MinIdleTime or i+1==len(ext_time_list): #deactivation if extruder time big enough or last extruder change
                                fired = 0 #reset the flag for re-activation
                                print 'De-Activation ext. no. ' + repr(int(prev_ext)) + ' (' + repr(IdleTemp[int(prev_ext)]) + 'C), i=' + repr(int(i)) + ', ext_time_list[i]=' + repr(ext_time_list[i])
                                f.write("M104 T%1d S%1.1f ;extruder de-activation added by ExtruderIdle V%s\n" % (int(prev_ext),float(IdleTemp[int(prev_ext)]),version)) #de-activates extruder
                if i>0:
                        if ext_time + MinIdleTime > ext_time_list[i] and ext_time_list[i] >= MinIdleTime and fired == 0:
                                fired = 1
                                print 'Re-activation ext. no. ' + repr(int(1-pres_ext)) + ' at ' + repr(ext_time_list[i]-ext_time) + 's to go, z=' + repr(z) + ', i=' + repr(int(i)) + ', ext_time_list[i]=' + repr(ext_time_list[i])
                                print 'time_step=' + repr(time_step)
                                f.write("M104 T%1d S%1.1f ;extruder re-activation added by ExtruderIdle V%s\n" % (int(1-pres_ext),float(lasttemp[int(1-pres_ext)]),version)) #re-activates extruder
                f.write(line)

print 'Len(list): ' + repr(len(ext_time_list))


print '------- End of debug run ------'



