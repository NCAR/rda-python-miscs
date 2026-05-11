#!/usr/bin/env python3
##################################################################################
#     Title: tcshqsub
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 11/19/2020
#            2025-03-07 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#            2025-12-29 convert to class TcshQsub
#   Purpose: python script to submit a batch job on PBS node via tcsh script
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import os
import sys
import re
from os import path as op
from rda_python_common.pg_log import PgLOG

class TcshQsub(PgLOG):
   """Submit a PBS batch job via a dynamically generated tcsh script using qsub.

   Builds a tcsh script with PBS directives, module loads, and conda environment
   activation, then submits it through the PBS qsub command.
   """

   def __init__(self):
      """Initialize TcshQsub with default PBS resource settings and options."""
      super().__init__()
      self.DEFMODS = {
         'default': "ncarenv,netcdf,ncl,nco,cdo,conda,grib-util,wgrib2"
      }
      self.DEFLIBS = {
         'default': "conda activate /glade/work/gdexdata/conda-envs/pg-gdex"
      }
      self.SWAPMODS = {}
      self.RESOURCES = {   # resource list for option -l
         'walltime': '6:00:00',   # if this is changed, change defpbstime in PgCheck.py too
         'select': '1:ncpus=1:mem=1gb'
      }
      self.SOPTIONS = {   # single-dash option values
         'o': None,    # will set to default if not provided
         'e': None,
         'A': "P43713000",
         'q': "gdex@casper-pbs",
      #   'm': 'a',
         'm': 'n',
      }
      self.gdexsub = self.BCHCMDS['PBS']
      self.coptions = {'cmd': None, 'cwd': None, 'env': None, 'mod': None, 'res': 'default'}       # customized options
      self.args = None

   # function to read parameters
   def read_parameters(self):
      """Parse command-line arguments and populate PBS options and customized options.

      Handles single-dash qsub options (e.g. -q, -A, -l) and long custom options
      (-cmd, -cwd, -env, -mod, -res). Validates that the qsub command is available
      and that a -cmd value is provided. Sets default log paths and job name if not
      specified, and changes the working directory if -cwd is given.
      """
      aname = 'tcshqsub'
      pname = 'gdexqsub'
      self.set_help_path(__file__)
      copts = '|'.join(self.coptions)
      option = None
      argv = sys.argv[1:]
      if not argv: self.show_usage(aname)
      self.PGLOG['LOGFILE'] = pname + ".log"
      self.cmdlog("{} {}".format(aname, ' '.join(argv)))
      if not self.valid_command(self.gdexsub): self.pglog("{}: miss {} command to submit batch job".format(self.gdexsub, self.PGLOG['PBSNAME']), self.LGWNEX)
      while argv:
         arg = argv.pop(0)
         ms = re.match(r'^-(\w)$', arg)
         if ms:
            option = ms.group(1)
            if option == "b":
               self.PGLOG['BCKGRND'] = 1
               option = None
            else:
               self.SOPTIONS[option] = ''
            continue
         ms = re.match(r'^-({})$'.format(copts), arg)
         if ms:
            option = ms.group(1)
            if option == "env": option = 'v'
            continue
         if not option: self.pglog("{}: Value passed in without leading option for {}".format(arg, self.gdexsub), self.LGEREX)
         if arg.find(' ') > -1 and not re.match(r'^[\'\"].*[\'\"]$', arg):   # quote string with space but not quoted yet
            if arg.find("'") > -1:
               arg = '"{}"'.format(arg)
            else:
               arg = "'{}'".format(arg)
         if option in self.coptions:
            self.coptions[option] = arg
            if option == "cmd": break
         else:
            self.SOPTIONS[option] = arg
         option = None
      self.args = self.argv_to_string(argv, 0)   # append command options
      if not self.coptions['cmd']: self.pglog(aname + ": specify command via option -cmd to run", self.LGWNEX)
      if not self.SOPTIONS['o']: self.SOPTIONS['o'] = "{}/{}/".format(self.PGLOG['LOGPATH'], pname)
      if not self.SOPTIONS['e']: self.SOPTIONS['e'] = "{}/{}/".format(self.PGLOG['LOGPATH'], pname)
      if 'N' not in self.SOPTIONS: self.SOPTIONS['N'] = op.basename(self.coptions['cmd'])
      if self.coptions['cwd']:
         if '$' in self.coptions['cwd']: self.coptions['cwd'] = self.replace_environments(self.coptions['cwd'], '', self.LGWNEX)
         os.chdir(self.coptions['cwd'])

   # function to start actions
   def start_actions(self):
      """Resolve the command path, build the tcsh script, and submit it via qsub."""
      cmd = self.valid_command(self.coptions['cmd'])
      if not cmd and not re.match(r'^/', self.coptions['cmd']): cmd = self.valid_command('./' + self.coptions['cmd'])
      if not cmd: self.pglog(self.coptions['cmd'] + ": Cannot find given command to run", self.LGWNEX)
      if self.args: cmd += " " + self.args
      sbuf = self.build_tcsh_script(cmd)
      self.pglog(sbuf, self.MSGLOG)
      self.PGLOG['ERR2STD'] = ['bind mouting']
      self.pgsystem(self.gdexsub, self.LOGWRN, 6, sbuf)
      self.PGLOG['ERR2STD'] = []

   # build tcsh script to submit a PBS batch job
   def build_tcsh_script(self, cmd):
      """Build and return a tcsh script string with PBS directives for the given command.

      Sets HOME, sources system and conda profile scripts and the user's .tcshrc,
      loads modules, activates the conda environment, then runs the command.

      Args:
         cmd (str): The fully-resolved command (with arguments) to execute in the job.

      Returns:
         str: The complete tcsh batch script content.
      """
      buf = "#!/bin/tcsh\n\n"   # sbatch starting tcsh script
      if 'l' in self.SOPTIONS: self.add_resources()
      # add options to tcsh script for qsub
      for option in self.SOPTIONS:
         buf += "#PBS -" + option
         if self.SOPTIONS[option]: buf += " {}".format(self.SOPTIONS[option])
         buf += "\n"
      for option in self.RESOURCES:
         buf += "#PBS -l"
         if self.RESOURCES[option]: buf += " {}={}".format(option, self.RESOURCES[option])
         buf += "\n"
      # always include the login user's tcsh resource file
      homedir = "{}/{}".format(self.PGLOG['USRHOME'], self.PGLOG['CURUID'])
      buf += "setenv HOME {}\n".format(homedir)
      buf += "source /etc/profile.d/z00_modules.csh\n"
      buf += "source /glade/u/apps/opt/conda/etc/profile.d/conda.csh\n"
      buf += "source {}/.tcshrc\n".format(homedir)
      buf += "pwd; hostname; date\n"
      buf += self.add_modules(self.coptions['res'], self.coptions['mod'])
      buf += self.set_vm_libs(self.coptions['res'])
      buf += "\necho {}\n{}\n\ndate\n".format(cmd, cmd)
      return buf

   # check and add resource options
   def add_resources(self):
      """Parse -l option value into the RESOURCES dict and remove the raw -l entry.

      Expects comma-separated name=value pairs (e.g. 'walltime=2:00:00,select=1:ncpus=4').
      Logs an error if a token does not contain '='.
      """
      for res in re.split(',', self.SOPTIONS['l']):
         ms = re.match(r'^([^=]+)=(.+)$', res)
         if ms:
            self.RESOURCES[ms.group(1)] = ms.group(2)
         else:
            self.pglog(res + ": use '=' to separate resource name & value", self.LGEREX)
      del self.SOPTIONS['l']

   # add module loads for modules provided
   def add_modules(self, res, mods):
      """Build and return module load/unload commands for the tcsh script.

      Loads the default module set for the given reservation (or the 'default' set).
      Additional modules in ``mods`` are appended; path-style entries (starting with
      '/') use 'module use' instead of 'module load'.  Modules already in the default
      set are skipped.  SWAPMODS entries trigger an unload before the new load.

      Args:
         res (str): Reservation name used to look up DEFMODS; falls back to 'default'.
         mods (str): Comma-separated list of extra modules (or None).

      Returns:
         str: Shell commands to load/unload modules.
      """
      mbuf = "\n"
      defmods = self.DEFMODS[res] if res in self.DEFMODS else self.DEFMODS['default']
      dmods = re.split(',', defmods)
      for dmod in dmods:
         ms = re.match(r'^(.+)/', dmod)
         smod = ms.group(1) if ms else dmod
         if smod in self.SWAPMODS: mbuf += "module unload {}\n".format(self.SWAPMODS[smod])
         mbuf += "module load {}\n".format(dmod)
      if mods:
         amods = re.split(',', mods)
         for amod in amods:
            if re.match(r'^/', amod):
               mbuf += "module use {}\n".format(amod)
            else:
               ms = re.match(r'^(.+)/', amod)
               smod = ms.group(1) if ms else amod
               if smod in dmods: continue
               if smod in self.SWAPMODS: mbuf += "module unload {}\n".format(self.SWAPMODS[smod])
               mbuf += "module load {}\n".format(amod)
      return mbuf

   # set virtual machine libraries
   def set_vm_libs(self, res):
      """Build and return conda/VM library activation commands for the tcsh script.

      Looks up DEFLIBS for the given reservation (falls back to 'default').

      Args:
         res (str): Reservation name used to look up DEFLIBS; falls back to 'default'.

      Returns:
         str: Shell commands to activate virtual environment libraries, or '' if none.
      """
      deflibs = self.DEFLIBS[res] if res in self.DEFLIBS else self.DEFLIBS['default']
      if not deflibs: return ''
      dlibs = re.split(',', deflibs)
      libbuf = "\n"
      for dlib in dlibs:
         libbuf += dlib + "\n"
      return libbuf

# main function to execute this script
def main():
   """Entry point: instantiate TcshQsub, parse arguments, run, and exit."""
   object = TcshQsub()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
