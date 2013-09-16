#Name: Flow Thermostat 1.1
#Info: Adjusts the heater temperature to match the reduced flow when using the built in Cool feature. This allows for faster an more high quality prints. Later versions vill extract known data for the fields below from the Gcode.
#Depend: GCode
#Type: postprocess
#Param: firstLayerTemp(float:230.0) First layers printing temperature (C)
#Param: thermostatSlope(float:3.75) Thermostat slope setting (typical 3.75)
#Param: printSpeed(float:100) Print Speed (Copy from Print config-tab!)
#Param: layerHeight(float:0.2) Individual layer height (Copy) 
#Param: nozzleDiameter(float:0.4) Extruder nozzle diameter (Copy)
#Param: minTemp(float:195.0) Minimum allowed temperature (C)

version = 1.1


#or get it from C:\Users\Jaknil\Documents\printer\Cura-master\Cura\util\profile.py loadGlobalProfileFromString(options):

# slowSpeed(float:50.0) Good slow printing speed (mm/s)
# slowTemp(float:205.0) Good slow printing temp (C)
# fastSpeed(float:110.0) Good fast printing speed (mm/s)
# fastTemp(float:225.0) Good fast printing temperature (C)
# mintemp(float:205.0) Minimum allowed temperature (C)




import re

#standard code-grabber and searcher, not plugin specific
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

#end of standard code-grabber and searcher, not plugin specific

#initial test to see if we can work this at all.
print '------- Debug run --------------'

#Grab the Gcode line-s one by one into the object lines
tempFull = 0
s = 0
with open(filename, "r") as f: #r for read
	lines = f.readlines()
#####Check for M109, max temperature is Full temperature, store that for later use
        for line in lines: #Steps through the entire Gcode
                if getValue(line, 'M', None) == 109: #yes if value after M is 109
                        s = getValue(line, 'S', s)
                        if s > (tempFull):
                                tempFull = s
                                print 'tempFull is'
                                print tempFull


                                

# the meat

feedFull = printSpeed*60 # converts the print speed mm/s to Gcode F
print 'feedFull is'
print feedFull


# Check how flow(feed) in this print #figure out the flow-temp curve temp(F)from the indata


# cheating it for now 
flowFull = printSpeed * layerHeight * nozzleDiameter
print 'flowFull is'
print flowFull
# finding theoretical melt point
meltTemp = (tempFull - (flowFull * thermostatSlope))
print 'meltTemp is'
print meltTemp

#Explanation:
# thermostatSlope is the linear relation between increasing flow and increasing print temp to achive the same print result at different print speeds. Calculated as
#thermostatSlope (Delta temp ) / ( Delta flow ) # this is done beforhand and the relation is assumed to be simmilar with all PLA colors.                      
#Feed is lineary proportional to flow since nozzle and layer height is constant.
# In short plaintext, if you know one good temp and speed combo you can calculate them all, for all thicknesses and speeds :)

#This means that
#flowCurrent = flowFull * (feedCurrent / feedFull)
#tempAdjusted = flowCurrent * thermostatSlope + meltTemp
#I will use this to calculate the proper temps for all feed speeds in the file.

def getTemp(feedCurrent):
        flowCurrent = flowFull * (feedCurrent / feedFull)
        tempAdjusted = flowCurrent * thermostatSlope + meltTemp
        if tempAdjusted < (minTemp):
                tempAdjusted = minTemp
        #print 'tempAdjusted is ' + repr(tempAdjusted)
        return tempAdjusted

print 'did it work = 205'
print (getTemp(50*60))
print '-----'
#kill?
z = 0
e = 0
f = 0
idx = 0
pastStart = 0
currentZ = 0
feedCurrent = 0
lastFeedCurrent = 1 # to get things rolling




with open(filename, "w") as f:
	f.write("; This Gcode file has been temperature adjusted with FlowThermostat version %f\n" % (version)) #tag the file
        #print 'test'
	f.write("M109 S%f\n" % (firstLayerTemp)) #Inject first layer temp
	for line in lines:
		if getValue(line, 'M', None) == 109: #do this for all individual lines with M109 in them to find and change the initial temp setting.
			#print line
			line = "M104 S%f\n" % (firstLayerTemp)
			#print "Changed to"
			#print line
			#Make this less crappy.

###Save the file with M104 temperature settings per speedchange # mod to avoid transports. Ramps are ok since temp change takes time.
			#only accept lines with G1 and F and E values on them.
##
##
		if getValue(line, 'G', None) == 0: #do this for all individual lines with G0 in them as Cura writes z positions only into G0 commands
                        if getValue(line,'Z',0) > 0: #check if there is a z position in the G0 line
                                currentZ = getValue(line, 'Z', z) 
                                #print 'CurrentZ is ' + repr(currentZ)

		if getValue(line, 'G', None) == 1: #do this for all individual lines with G1 in them
                        #print 'Line found'
                        if pastStart == 0:
                                if currentZ > (layerHeight * 3) and currentZ < (2): #ugly fix for now to avoid false positives
                                        print 'past start'
                                        pastStart = 1
                        else: #if we are past start
                                feedCurrent = getValue(line, 'F', lastFeedCurrent) #nest this better under E so that it works faster and less wrong
                                #print feedCurrent
                                if getValue(line, 'E', 0) > 0 and feedCurrent != lastFeedCurrent: #if we are on an extruding line with changed feed speed

##                                        print 'lastFeedCurrent'
##                                        print lastFeedCurrent
##                                        print 'feedCurrent'
##                                        print feedCurrent
                                       # print 'diff' 
                                        #print (feedCurrent - lastFeedCurrent)
                                        lastFeedCurrent = feedCurrent

                                        #print (feedCurrent / 60)
                                        f.write("M104 S%f\n" % (getTemp(feedCurrent)))
                                        #print getTemp(feedCurrent)
		f.write(line)
        f.write("M104 S0\n") #THIS IT KILLS THE HEAT after all is done!



print '------- End of debug run ------'



