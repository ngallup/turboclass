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
		self.coord = os.path.join(self.turboDir, 'coord')

		# Create and open stream to log file
		self.logPath = os.path.join(self.turboDir, 'turbohistory.log')

		if os.path.exists(self.logPath) == False:
			with open(self.logPath, 'w') as createLog:
				pass

		self.log = open(self.logPath, 'r+')
		self.firstLog = True
		self.logNum = None

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
		if self.turboDir == comparison.turboDir:
			return True
		else:
			return False

	# Used to conveniently write messages to the log file
	def writeLog(self, message):

		# First check if this is the first log being written for this instance
		# and write header if so
		if self.firstLog == True:
			self.firstLog = False
			logLines = self.log.readlines()
			entries = []
			for line in logLines:
				if '-- LOG --' in line:
					entries.append(line.rstrip('\n'))
			self.logNum = len(entries) + 1
			self.log.write("\n-- LOG -- %s\n" % self.logNum)
		
		# Finally write message to block
		self.log.write(message + '\n')

	# Helper function to send commands to the terminal
	def sendToTerminal(self, command, message, dest='both'):
		
		# Print and log message
		if dest == 'both':
			print message
			self.writeLog(message)
		elif dest == 'print':
			print message
		elif dest == 'log':
			self.writeLog(message)
		else:
			print message
			self.writeLog(message)

		# Return a subprocess with the command
		return subprocess.Popen(command, shell=True, cwd=self.turboDir,
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

	# Helper printer function.  Sends text to stdout and/or log
	# Kind of nice.
	def printLog(self, message):
		print message
		self.writeLog(message)

	# Helper function to send actual -r commands and record them
	def sendActual(self, message):
		print message
		self.writeLog(message)

		actual = subprocess.Popen("actual -r", shell=True, cwd=self.turboDir,
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		
		actual_out = actual.stdout.read()
		print actual_out
		self.writeLog(actual_out.rstrip('\n'))
	
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

	# Helper function for detecting if -ri flags should be used
	def detect_ri(self):
		with open(self.control, 'r') as controlFile:
			control_lines = controlFile.read()
			if "$rij" in control_lines:
				return True
			else:
				return False

	# Helper function for detecting -level <func>
	# level = CC2, MP2, SCF, not a functional
	# Fix some other time
	def detect_level(self):
		#with open(self.control, 'r') as controlFile:
		#	for line in controlFile:
		#		if "functional" in line:
		#			functional, level = line.split()
		#			return level
		return 'scf'

	# Helper function for detecting -frznuclei flag in numforce
	def detect_frznuclei(self):
		with open(self.coord, 'r') as coordFile:
			for line in coordFile:
				if line.split()[-1] == 'f':
					return True
		return False

	# For rolling back a calculation to a particular configuration.  Method
	# will truncate energy and gradient files and replace coord with
	# appropriate geometry
	# DOES NOT CURRENTLY SUPPORT INTERNAL COORDINATES
	def rollback(self, geometry=None):
		
		# No configuration specified so exit
		if geometry == None:
			return
		
		# Configuration greater than number available
		if geometry > len(self):
			pass # Throw and error		


		# If cartesian coords do one thing, else if internal, do another
		with open(self.control, 'r') as controlFile:
			lines = controlFile.read()
			if "$intdef" in lines: # Pick some other metric
				pass # Do internal specific routine
			else:
				pass # Do normal routine

		# Truncate energies
		with open(self.energy, 'r') as enerFile:
			ener_lines = enerFile.readlines()
			ener_lines = ener_lines[:geometry+1]
		with open(self.energy, 'w') as enerFile:
			for line in ener_lines:
				enerFile.write(line)
			if "$end" not in ener_lines[-1]:
				enerFile.write("$end")

		# Find coords and truncate gradient
		with open(self.gradient, 'r') as gradFile:
			gradLines = []
			coordLines = []
			isCycle = False

			for line in gradFile:
				if isCycle == True and 'cycle' in line:
					break
				if '$end' in line:
					break
				gradLines.append(line)
				if isCycle == True and len(line.split()) > 3:
					coordLines.append(line)
				if 'cycle =%7s' % geometry in line:
					isCycle = True
			
			# Throw error if no coordinates found in gradient file
			if coordLines == []:
				message = "Warning!  Rollback couldn't find coordinates "
				message += "corresponding to configuration %s.  " % geometry
				message += "Make sure the gradient file exists, and there is"
				message += " a coordinate entry for that configuration."
				
				print message
				self.writeLog(message)
				sys.exit(1)

		# Write out truncated gradient and new coord file
		with open(self.gradient, 'w') as gradFile:
			for line in gradLines:
				gradFile.write(line)
			gradFile.write("$end")

		with open(self.coord, 'w') as coordFile:
			coordFile.write('$coord\n')
			for line in coordLines:
				coordFile.write(line)
			coordFile.write('$end')

		print "System has been rolled back to configuration %s" % geometry
		self.writeLog("System has been rolled back to configuration %s" % geometry)

	# For running a simple ridft.  Rollback variable implemented for easy recall
	# of an energy for a particular geometry.  Rollback feature could be
	# implemented here or in a dedicated rollback function
	def ridft(self, rollback=None):

		# Implement some other time
		if rollback != None:
			self.rollback(rollback)
		
		print "Submitting ridft command"
		self.writeLog('Submitting ridft command')
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
				self.writeLog("ridft has failed for unknown reasons and could not be " \
					"recovered.  Check that the setup is alright")
				sys.exit(1)

			self.sendActual("Abnormal termination detected.  Attempting actual -r.")
			
			print "Re-attempting ridft"
			self.writeLog("Re-attempting ridft")
			p = subprocess.Popen("ridft", shell=True, cwd=self.turboDir,
								stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			out = p.stdout.read()
			print out
			
			tries += 1

		print "ridft has successfully finished"
		self.writeLog("ridft has successfully finished")

	# For running a simple rdgrad.  Rollback variable implemented for easy 
	# recall of a gradient for a particular geometry.  Rollback feature could be
	# implemented here or in a dedicated rollback function
	def rdgrad(self, rollback=None):
		
		# Implement some other time
		if rollback != None:
			self.rollback(rollback)

		print "Submitting rdgrad command"
		self.writeLog("Submitting rdgrad command")
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
				self.writeLog("rdgrad has failed for unknown reasons and could not be " \
					"recovered.  Check that the setup is alright.")
				sys.exit(1)
			
			message = "Abnormal termination detected.  Attempting actual -r"
			self.sendActual(message)
	
			print "Re-attempting rdgrad"
			self.writeLog("Re-attempting rdgrad")
			p = subprocess.Popen("rdgrad", shell=True, cwd=self.turboDir,
								stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			out = p.stdout.read()
			print out
			
			# Try running ridft to fix the problem
			if "rdgrad ended abnormally" in out:
				print "actual -r didn't work.  Trying new ridft."
				self.writeLog("actual -r didn't work.  Trying new ridft.")
				self.ridft()
		
		print "rdgrad has successfully finished"
		self.writeLog("rdgrad has successfully finished")

	# For running jobex.  Rollback vairable implemented for easy recall of a 
	# particular geometry.  Rollback feature could be implemented
	# here or in a dedicated rollback function.
	# Trans should be removed and rolled into a different method for a more
	# readable method with more advanced error handling.  Maybe.
	# level should automatically detect its function from the control file
	# -l, -ls, -md, -mdfile, -mdscript, -help will probably not be implemented
	def jobex(self, rollback=None, energy=6, gcart=3, c=20, dscf=False, 
		grad=False, statpt=False, relax=False, trans=False, level='',
		ri='', rijk=False, ex=False, keep=False):
		
		# Auto-detect certain flags
		if ri == '':
			ri = self.detect_ri()
		if level == '':
			level = self.detect_level()

		# Organize True/False args into a dictionary of a dictonary for easy access
		flags = { 
			'dscf'   : {True : '-dscf ',   False: ''}, 
			'grad'   : {True : '-grad ',   False: ''},
			'statpt' : {True : '-statpt ', False: ''},
			'relax'  : {True : '-relax ',  False: ''},
			'trans'  : {True : '-trans ',  False: ''},
			'ri'     : {True : '-ri ',     False: ''},
			'rijk'   : {True : '-rijk ',   False: ''},
			'ex'     : {True : '-ex ',     False: ''},
			'keep'   : {True : '-keep ',   False: ''} }

		# Implement later
		if rollback != None:
			self.rollback(rollback)
		
		comm =  "jobex -energy %s -gcart %s -c %s -level %s " % \
			(energy, gcart, c, level)
		comm += flags['dscf'][dscf]
		comm += flags['grad'][grad]
		comm += flags['statpt'][statpt]
		comm += flags['relax'][relax]
		comm += flags['trans'][trans]
		comm += flags['ri'][ri]
		comm += flags['rijk'][rijk]
		comm += flags['ex'][ex]
		comm += flags['keep'][keep]

		# Begin sending commands to the shell
		print "Submitting command %s" % comm
		self.writeLog("Submitting command %s" % comm)
		opt = subprocess.Popen(comm, shell=True, cwd=self.turboDir,
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		
		opt_out = opt.stdout.read()
		print opt_out

		# Super shitty troubleshooting.  Needs refining.
		tries = 1
		numtries = 2
		while "program stopped" in opt_out:
			if tries > numtries:
				print "jobex has failed for unknown reasons and could not be " \
					"recovered.  Check that the setup is alright."
				self.writeLog("jobex has failed for unknown reasons and could not be " \
					"recovered.  Check that the setup is alright.")
				sys.exit(1)

			message = "Abnormal termination detected.  Attempting actual -r"
			self.sendActual(message)

			print "Re-attempting %s command" % comm
			self.writeLog("Re-attempting %s command" % comm)
			new_opt = subprocess.Popen(comm, shell=True, cwd=self.turboDir,
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

			opt_out = new_opt.stdout.read()
			print opt_out

			# Try running ridft to fix the problem, if there was one
			if "program stopped" in opt_out:
				print "actual -r didn't work.  Trying new ridft."
				self.writeLog("actual -r didn't work.  Trying new ridft.")
				self.ridft()

			tries += 1

		print "Jobex command has successfully finished"
		self.writeLog("Jobex command has successfully finished")

	# For running numfore in either a serial or parallel environment.  Rollback
	# method not currently implemented and mfile implementation is probably
	# rudimentary.  Currently -scrpath, -l, and -ls is a little mysterious 
	# and I haven't tested how to use them
	# Ideas to implement later: 
	#  automatic detection of frznuclei
	#  automatic ri
	#  automatic level
	#  mfile generation
	def numforce(self, rollback=None, ri='', rijk=False, level='',
		ex='', d='', thrgrd='', central=False, polyedr=False,
		ecnomic=False, diatmic=False, size='', mfile='', i=False,
		c=False, prep=False, l='', ls='', scrpath='', override=False,
		frznuclei='', cosmo=False):

		# Auto-detect some flags
		if ri == '':
			ri = self.detect_ri()
		if level == '':
			level = self.detect_level()
		if frznuclei == '':
			frznuclei = self.detect_frznuclei()
		
		if level != '':
			level = " -level %s" % level
		if d != '':
			d = " -d %s" %d
		if thrgrd != '':
			thrgrd = " -thrgrd %s" % thrgrd
		if ex != '':
			ex = " -ex %s" % ex
		if size != '':
			size = " -%s" % size
		if mfile != '':
			mfile = " -mfile %s" % mfile
		if l != '':
			l = " -l %s" % l
		if ls != '':
			ls = " -ls %s" % ls
		if scrpath != '':
			scrpath = " -scrpath %s" % scrpath

		flags = {
			'ri'      : {True : ' -ri',   False : ''},
			'rijk'    : {True : ' -rijk', False : ''},
			'central' : {True : ' -central', False : ''},
			'polyedr' : {True : ' -polyedr', False : ''},
			'ecnomic' : {True : ' -ecnomic', False : ''},
			'diatmic' : {True : ' -diatmic', False : ''},
			'i'       : {True : ' -i',    False : ''},
			'c'       : {True : ' -c',    False : ''},
			'prep'    : {True : ' -prep', False : ''},
			'override': {True : ' -override',False : ''},
			'frznuclei':{True : ' -frznuclei',False: ''},
			'cosmo'   : {True : ' -cosmo',False : ''} }

		# Assemble command and list of flags
		comm = 'NumForce'
		comm += level + d + thrgrd + ex + size + mfile + l + ls + scrpath
		comm += flags['ri'][ri]
		comm += flags['rijk'][rijk]
		comm += flags['central'][central]
		comm += flags['polyedr'][polyedr]
		comm += flags['ecnomic'][ecnomic]
		comm += flags['diatmic'][diatmic]
		comm += flags['i'][i]
		comm += flags['c'][c]
		comm += flags['prep'][prep]
		comm += flags['override'][override]
		comm += flags['frznuclei'][frznuclei]
		comm += flags['cosmo'][cosmo]

		# Implement later
		if rollback != None:
			self.rollback(rollback)

		text = "Submitting command %s" % comm
		num_run = self.sendToTerminal(comm, text)

		num_out = num_run.stdout.read()
		print num_out

		# Try to troubleshoot
		tries = 1
		numtries = 2
		while "program stopped" in num_out:

			# Terminal error
			if tries > numtries:
				text = "NumForce has failed for unknown reasons and could not be" \
					" recovered.  Check that the setup is alright."
				print text
				self.writeLog(text)
				sys.exit(1)

			# Try actual -r
			actual_msg = 'Abnormal termination detected.  Attempting actual -r.'
			self.sendActual(actual_msg)

			text = "Re-submitting command %s" % comm
			num_run = self.sendToTerminal(comm, text)

			num_out = num_run.stdout.read()
			print num_out

			# Try running ridft and rdgrad to fix the problem if there was one
			if "program stopped" in num_out:
				print "actual -r didn't work.  Trying ridft -> rdgrad."
				self.writeLog("actual -r didn't work.  Trying ridft -> rdgrad.")
				self.ridft()

				print "...Now Trying rdgrad."
				self.writeLog("...Now trying rdgrad.")
				self.rdgrad()
			
			tries += 1
			
		# Check for missing gradient error
		if "Can not find data group $grad" in num_out:
			print "Gradient is missing.  Running rdgrad."
			self.writeLog("Gradient is missing.  Running rdgrad.")
			self.rdgrad()

			message = "Re-submitting command %s" % comm
			self.sendToTerminal(comm, message)

		print "NumForce has successfully finished."
		self.writeLog("Numforce has successfully finished.")

	def constrained_int_opt(self, rollback=None, otherflags=None):
		pass

	def constrained_int_ts(self, rollback=None, otherflags=None):
		pass
	
