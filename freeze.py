#!/usr/bin/python

__author__='Nathan Gallup'
'''
===========================
freeze.py

For freezing Turbomole cartesian coordinate atoms quickly from the command line.

February 2015, UCLA
===========================
'''

import sys, os


## Check command line arguments
#if len(sys.argv[1:]) < 2:
#	print "No files specified.  Exiting!"
#	print "Usage: freeze.py <coord> <atoms to be frozen>"
#	sys.exit(1)
#
## Check if valid turbomole files
#if (not os.path.isfile(sys.argv[1])):
#	print "Not a valid turbomole coord file"
#	sys.exit(1)
#if open(sys.argv[1],'r').readline() != "$coord\n":
#	print "Not a valid turbomole coord file"
#	sys.exit(1)
#

# Create freeze function for freezing atoms
def freeze(coord,*atoms):

	# Define usage statement
	def usage():
		print "Usage: freeze.py <coord> <atoms to be frozen>"

	# Check command line arguments for validity
	if (not os.path.isfile(coord)):
		print "Not a valid turbomole coord file"
		usage()
		sys.exit(1)
	if open(coord,'r').readline() != "$coord\n":
		print "not a valid turbomole coord file"
		usage()
		sys.exit(1)
	if len(atoms) == 0:
		print "No atoms specified.  Exiting!"
		usage()
		sys.exit(1)

	# Read in coord atoms
	coordFile = open(coord,'r')
	coordLines = coordFile.readlines()
	
	atomList = [val for atom in atoms for val in atom]
	
	# Append f's to lines unless already present
	for atom in atomList:
		if coordLines[atom].split()[-1] == 'f':
			print "Frozen coordinate found for atom %d.  Proceeding." % atom
			continue
		else:
			coordLines[atom] = "%s f\n" % coordLines[atom].rstrip('\n')

	coordFile.close()
	
	# Now write all the data back to file
	coordFile = open(coord, 'w')
	
	for line in coordLines:
		coordFile.write(line)

if __name__ == '__main__':
	freeze(sys.argv[1],*sys.argv[2:])
