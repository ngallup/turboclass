#!/usr/bin/python
__author__= 'Nathan Gallup'
'''
==============================================================================
turboclass.py

For running Turbomole with frozen internal coordinate optimizations, but could
be generally used for Turbomole optimizations involving internal coordinates.  
Attempts to automatically handle the problem of Turbomole sometimes producing
linearly dependent internal redundant coordinates during optimization by
switching between optimizing with the frozen cartesian atoms and frozen
internals.  Also attempts to continue the optimization of currently running
internal coordinate calculations via autosubmission.  This script is entirely
intended to be a single user-executed script that then runs a frozen internal
coordinate calculation to its completion, often days later.

March 2015, UCLA
==============================================================================
'''

import os, sys, optparse, subprocess
import freeze, unfreeze

# For easy submission, FINISH LATER.  LONG TERM.
def createSubmission(options):
	print options.submit
	# Check options.submit for true/fals and change script accordingly

#parser = optparse.OptionParser(description='This is some random message')
parser = optparse.OptionParser()

parser.add_option('-t',	action="store", type=int, default=24, dest="time",
						help="Time in hours")
parser.add_option('-N',	action="store", type=int, default=12, dest="cores",
						help="Number of cores")
parser.add_option('--type', action="store", type=int, default=12, dest="type",
						help="Type of node")
parser.add_option('--h_data',	action="store", type=str, default=4, dest="mem",
						help="Memory desired")
parser.add_option('-a',	action="store", type=str, default="autointernal", dest="jobname",
						help="Jobname as you want it to appear in the queue")
parser.add_option('--sub',	action="store_true",	default=False,	dest="submit",
						help="Inclusion of this command with submit the script")

options, args = parser.parse_args()

print options
print options.time
createSubmission(options)
print args

class Turboclass(object):

	# Initialize and create a record of important files
	def __init__(self, turboDir=None):
		self.homeDir = os.getcwd()

		if turboDir == None:
			self.turboDir = os.getcwd()
		else:
			self.turboDir = os.path.realpath(turboDir)

		self.energy = os.path.join(self.turboDir, 'energy')
		self.gradient = os.path.join(self.turboDir, 'gradient')
		# ERROR CHECK LATER TO MAKE SURE THIS EXISTS
		self.control = os.path.join(self.turboDir, 'control')

		if os.path.exists(os.path.join(self.turboDir, 'turbohistory.log')) == False:
			temp = open(os.path.join(self.turboDir, 'turbohistory.log'), 'w')
			temp.close()

	# Use of len(turboclassinstance) will return the number of configurations
	# in the current turbomole directory
	def __len__(self):
		with open(self.energy, 'r') as ener_file:
			ener_file_lines = ener_file.readlines()
			return len(ener_file_lines[1:-1]) # Doesn't read $end or $energy
	
	# Comparisons made using the '==' operator will compare the current
	# turbomole directory against the comparison.  Good for making sure
	# different instances aren't working in the same directory.
	def __eq__(self, comparison):
		if self.turboDir == comparison:
			return True
		else:
			return False

	# Returns the latest energy from the energy file with the specified units
	def getEnergy(self, units='hartree'):
		with open(self.energy, 'r') as ener_file:
			final_line = ener_file.readlines()[-2]
			iter, ener, kin, pot = final_line.split()
			conversion = {'hartree': 1, 'eV' : 27.2107, 'ev': 27.2107,
					'wavenumbers': 219474.63, 'cm^-1': 219474.63, 'cm-1': 219474.63,
					'kcal/mol': 627.503, 'kJ/mol': 2625.5, 'kj/mol': 2625.5}
			try:
				return float(ener) * conversion[units]
			except:
				print "Unit not recognized"
				return


	# For running a simple ridft.  Rollback variable implemented for easy recall
	# of an energy for a particular geometry.  Rollback feature could be
	# implemented here or in a dedicated rollback function
	def ridft(self, rollback=None):

		# Implement some other time
		if rollback != None:
			pass
		
		print "Submitting ridft command"
		p = subprocess.Popen("ridft", shell=True, cwd=self.turboDir, 
									stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		out = p.stdout.read()
		print out

		# Error several times before terminating
		tries = 1
		numtries = 2
		while "ridft ended abnormally" in out:
			if tries > numtries:
				print "ridft has failed for unknown reasons and could not be " \
						"recovered.  Check that the setup is alright"
				sys.exit(1)

			print "Abnormal termination detected.  Attempting actual -r"
			actual = subprocess.Popen("actual -r", shell=True, cwd=self.turboDir,
									stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			out = actual.stdout.read()
			print out
			
			print "Re-attempting ridft"
			p = subprocess.Popen("ridft", shell=True, cwd=self.turboDir,
								stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			out = p.stdout.read()
			print out
			
			tries += 1

		print "ridft has successfully finished"

	# For running a simple rdgrad.  Rollback variable implemented for easy 
	# recall of a gradient for a particular geometry.  Rollback feature could be
	# implemented here or in a dedicated rollback function
	def rdgrad(self, rollback=None):
		
		# Implement some other time
		if rollback != None:
			pass

		print "Submitting rdgrad command"
		p = subprocess.Popen("rdgrad", shell=True, cwd=self.turboDir,
									stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		out = p.stdout.read()
		print out

		# Error several times and troubleshoot
		tries = 1
		numtries = 2
		while "rdgrad ended abnormally" in out:
			if tries > numtries:
				print "rdgrad has failed for unknown reasons and could not be " \
						"recovered.  Check that the setup is alright."
				sys.exit(1)
			
			print "Abnormal termination detected.  Attempting actual -r "
			actual = subprocess.Popen("actual -r", shell=True, cwd=self.turboDir,
								stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			out = actual.stdout.read()
			print out
	
			print "Re-attempting rdgrad"
			p = subprocess.Popen("rdgrad", shell=True, cwd=self.turboDir,
								stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			out = p.stdout.read()
			print out
			
			# Try running ridft to fix the problem
			if "rdgrad ended abnormally" in out:
				print "actual -r didn't work.  Trying new ridft."
				self.ridft()
		
		print "rdgrad has successfully finished"

	# For running jobex.  Rollback vairable implemented for easy recall of a 
	# particular geometry.  Rollback feature could be implemented
	# here or in a dedicated rollback function.  'otherflags' is a placeholder
	# for all the flags that will be necessary with jobex (energy, gcart, etc.)
	def jobex(self, rollback=None, otherflags=None):
		pass

	def constrained_int_opt(self, rollback=None, otherflags=None):
		pass

	def constrained_int_ts(self, rollback=None, otherflags=None):
		pass
	
	def rollback(self):
		pass
