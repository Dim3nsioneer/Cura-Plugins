#Name: Wood V1.1
#Info: Vary the print temperature troughout the print to create wood rings with the LayWood printing material (v. 2013-02-11 12:14)
#Depend: GCode
#Type: postprocess
#Param: minTemp(float:180) Min print temperature (c)
#Param: maxTemp(float:230) Max print temperature (c)
#Param: grainSize(float:3.0) Average Grain Size (mm)

import re
import random
import math

__author__ = 'Jeremie Francois (jeremie.francois@gmail.com)'
__date__ = '$Date: 2013/02/12 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

############ BEGIN CURA PLUGIN STAND-ALONIFICATION ############
# This part is an "adapter" to Daid's version of my original Cura/Skeinforge plugin that
# he upgraded to the lastest & simpler Cura plugin system. It enables commmand-line
# postprocessing of a gcode file, so as to insert the temperature commands at each layer.
#
# Note that it should still be viewed by Cura as a regular plugin by the way!
#
# To run it you need Python, then simply run it like
#   wood_standalone.py --min minTemp --max maxTemp --grain grainSize --file gcodeFile
# It will "patch" your gcode file with the appropriate M104 temperature change.
#
import inspect
import sys
import getopt

def plugin_standalone_usage(myName):
	print "Usage:"
	print "  "+myName+" --file gcodeFile (--min minTemp) (--max maxTemp) (--grain grainSize)"
	print "  "+myName+" -f gcodeFile (-i minTemp) (-a maxTemp) (-g grainSize)"
	print "Licensed under CC-BY-NC from Jeremie.Francois@gmail.com (betterprinter.blogspot.com)"
	sys.exit()

try:
	filename
except NameError:
	# Then we are called from the command line (not from cura)
	# trying len(inspect.stack()) > 2 would be less secure btw
	opts, extraparams = getopt.getopt(sys.argv[1:],'i:a:g:f:h',['min=','max=','grain=','file=','help']) 
	minTemp=190
	maxTemp=240
	grainSize=3
	filename=""
	for o,p in opts:
		if o in ['-i','--min']:
			minTemp = float(p)
		elif o in ['-a','--max']:
			maxTemp = float(p)
		elif o in ['-g','--grain']:
			grainSize = float(p)
		elif o in ['-f','--file']:
			filename = p
	if not filename:
		plugin_standalone_usage(inspect.stack()[0][1])
#
############ END CURA PLUGIN STAND-ALONIFICATION ############


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

class Perlin:
	# Perlin noise: http://mrl.nyu.edu/~perlin/noise/

	def __init__(self, tiledim=256):
		self.tiledim= tiledim
		self.perm = [None]*2*tiledim

		permutation = []
		for value in xrange(tiledim): permutation.append(value)
		random.shuffle(permutation)

		for i in xrange(tiledim):
			self.perm[i] = permutation[i]
			self.perm[tiledim+i] = self.perm[i]

	def fade(self, t):
		return t * t * t * (t * (t * 6 - 15) + 10)

	def lerp(self, t, a, b):
		return a + t * (b - a)

	def grad(self, hash, x, y, z):
		#CONVERT LO 4 BITS OF HASH CODE INTO 12 GRADIENT DIRECTIONS.
		h = hash & 15
		if h < 8: u = x
		else:     u = y
		if h < 4: v = y
		else:
			if h == 12 or h == 14: v = x
			else:                  v = z
		if h&1 == 0: first = u
		else:        first = -u
		if h&2 == 0: second = v
		else:        second = -v
		return first + second

	def noise(self, x,y,z):
		#FIND UNIT CUBE THAT CONTAINS POINT.
		X = int(x)&(self.tiledim-1)
		Y = int(y)&(self.tiledim-1)
		Z = int(z)&(self.tiledim-1)
		#FIND RELATIVE X,Y,Z OF POINT IN CUBE.
		x -= int(x)
		y -= int(y)
		z -= int(z)
		#COMPUTE FADE CURVES FOR EACH OF X,Y,Z.
		u = self.fade(x)
		v = self.fade(y)
		w = self.fade(z)
		#HASH COORDINATES OF THE 8 CUBE CORNERS
		A = self.perm[X  ]+Y; AA = self.perm[A]+Z; AB = self.perm[A+1]+Z
		B = self.perm[X+1]+Y; BA = self.perm[B]+Z; BB = self.perm[B+1]+Z
		#AND ADD BLENDED RESULTS FROM 8 CORNERS OF CUBE
		return self.lerp(w,self.lerp(v,
				self.lerp(u,self.grad(self.perm[AA  ],x  ,y  ,z  ), self.grad(self.perm[BA  ],x-1,y  ,z  )),
				self.lerp(u,self.grad(self.perm[AB  ],x  ,y-1,z  ), self.grad(self.perm[BB  ],x-1,y-1,z  ))),
			self.lerp(v,
				self.lerp(u,self.grad(self.perm[AA+1],x  ,y  ,z-1), self.grad(self.perm[BA+1],x-1,y  ,z-1)),
				self.lerp(u,self.grad(self.perm[AB+1],x  ,y-1,z-1), self.grad(self.perm[BB+1],x-1,y-1,z-1))))

	def fractal(self, octaves, persistence, x,y,z, frequency=1):
		value = 0.0
		amplitude = 1.0
		totalAmplitude= 0.0
		for octave in xrange(octaves):
			n= self.noise(x*frequency,y*frequency,z*frequency)
			value += amplitude * n
			totalAmplitude += amplitude
			amplitude *= persistence
			frequency *= 2
		return value / totalAmplitude


with open(filename, "r") as f:
	lines = f.readlines()

#Find the total height of the object
maxZ = 0
z = 0
for line in lines:
	if getValue(line, 'G', None) == 1 or getValue(line, 'G', None) == 0: #added G0-command for Cura 13.x
		z = getValue(line, 'Z', z)
		if maxZ < z:
			maxZ = z

"First pass generates the noise curve, that we normalize it afterwards because the user expects to reach the min & max temperatures"
perlin = Perlin()
noises = []
banding = 5
octaves = 3
persistence = 0.5
z = 0
lastNoiseToAppend = -1
for line in lines:
	if getValue(line, 'G', None) == 1 or getValue(line, 'G', None) == 0: #added G0-movement used by Cura for z-change in Version 1.1
		# We have a new movement, check if there is an attached Z value
		newZ = getValue(line, 'Z', z)
		if newZ != z:
			# we postponed last temp until now so the "finishing" M104 commands are not patched (eg. we want to keep the "off" M104 S0 at the end)
			if lastNoiseToAppend != -1:
				noises.append(lastNoiseToAppend)
			z = newZ
			lastNoiseToAppend = banding * perlin.fractal(octaves, persistence, 0,0,z/(grainSize*2));
			lastNoiseToAppend = (lastNoiseToAppend - math.floor(lastNoiseToAppend))
temps = []
maxNoises = max(noises)
minNoises = min(noises)
for n in noises:
	nn = ( n - minNoises ) / ( maxNoises - minNoises )
	temps.append(minTemp + (maxTemp - minTemp) * nn)

#Save the file with M104 temperature settings per layer
z = 0
idx = 0
fout= open(filename, "w")
with fout as f:
	
	# Add a rough temperature graph at the start of the file (Daid)
	#	f.write(";WoodGraph: Wood temperature graph:\n")
	#	for n in xrange(15, 0, -1):
	#		str = ";WoodGraph: %3i | " % (minTemp + (maxTemp - minTemp) * n / 15)
	#		for t in temps:
	#			if (t - minTemp) / (maxTemp - minTemp) * 15 >= (n - 0.5):
	#				str += "#"
	#			else:
	#				str += " "
	#		f.write(str + "\n")
			
	# Add a transposed temperature graph at the start of the file (Jeremie)
	f.write(";WoodGraph: Wood temperature graph (from "+str(minTemp)+"C to "+str(maxTemp)+"C, grain size "+str(grainSize)+"):\n")
	for i in xrange(len(temps)-1,0,-1):
		t = int(20 * ( temps[i] - minTemp ) / (maxTemp - minTemp))
		str = ";WoodGraph: layer %3i " % i
		str += "@%3iC | " % temps[i]
		for i in xrange(0,t):
			str += "#"
		for i in xrange(t+1,20):
			str += "."
		f.write(str + "\n")
			
	for line in lines:
		if idx >= len(temps):
			f.write(line) # no more temps to patch
		elif getValue(line, 'G', None) == 1 or getValue(line, 'G', None) == 0: #added G0-command for Cura V13.x
			newZ = getValue(line, 'Z', z)
			if newZ != z:
				z = newZ
				f.write("M104 S%i\n" % (temps[idx]))
				idx += 1
			f.write(line)
		elif not ";woodgraph" in line.lower() and not "m104" in line.lower(): # forget any previous temp and temp graph in the file
			f.write(line)
