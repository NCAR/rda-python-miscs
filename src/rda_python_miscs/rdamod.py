#!/usr/bin/env python3
##################################################################################
#     Title: rdamod
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: change file/directory modes in given one or multiple local directories
#            owned by 'rdadata'
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from os import path as op
from rda_python_common.pg_file import PgFile

class RdaMod(PgFile):
   """Change file and directory permission modes for paths owned by 'rdadata'.

   Only items owned by 'rdadata' are changed; items with a different owner are
   logged as errors.  Items already at the target mode are silently skipped.
   A leading letter ('D' or 'F') is logged with each changed path to indicate
   its type.
   """

   def __init__(self):
      """Initialize RdaMod with default mode-change options and runtime state."""
      super().__init__()
      self.RDAMOD = {
         'd': 0,     # 1 to change directory mode
         'f': 0,     # 1 to change file mode
         'h': 0,     # 1 to show help message
         'r': 0,     # 1 if recursive all
         'R': 0,     # > 0 to set recursive limit
         'F': 0o664,   # target file mode, default to 664
         'D': 0o775,   # target directory mode, default to 775
      }
      self.MINFO = {
         'files': [],
         'curdir': os.getcwd(),
         'tpath': None,
         'dcnt': 0,
         'fcnt': 0
      }

   # function to read parameters
   def read_parameters(self):
      """Parse command-line arguments into RDAMOD option flags and the file/directory list.

      Recognises boolean flags -d, -f, -h, -r and value options -R, -F, -D.
      -R is cast to int; -F and -D are parsed as octal integers.  Positional
      arguments are collected into MINFO['files'].  Exits with usage if -h is
      given or no files are specified.
      """
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "rdamod.log"   # set different log file
      argv = sys.argv[1:]
      self.cmdlog("rdamod {} ({})".format(' '.join(argv), self.MINFO['curdir']))
      option = defopt = 'l'
      for arg in argv:
         ms = re.match(r'-(\w)$', arg)
         if ms:
            option = ms.group(1)
            if option not in self.RDAMOD: self.pglog(arg + ": Unknown Option", self.LGEREX)
            if option in 'dfhr':
               self.RDAMOD[option] = 1
               option = defopt
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option == 'l':
            self.MINFO['files'].append(arg)
            defopt = None
         else:
            if option == 'R':
               self.RDAMOD[option] = int(arg)
            elif option in 'FD':
               self.RDAMOD[option] = self.base2int(arg, 8)
            else:
               self.RDAMOD[option] = arg
            option = defopt
      if self.RDAMOD['h'] or not self.MINFO['files']: self.show_usage("rdamod")

   # function to start actions
   def start_actions(self):
      """Validate DECS group membership, process the path list, and log a summary count."""
      self.dssdb_dbname()
      if not (self.RDAMOD['d'] or self.RDAMOD['f']):
         self.RDAMOD['d'] = self.RDAMOD['f'] = 1   # both directories and files as default
      if not self.RDAMOD['R'] and self.RDAMOD['r']: self.RDAMOD['R'] = 1000
      self.validate_decs_group('rdamod', self.PGLOG['CURUID'], 1)   
      self.change_top_list(self.MINFO['files'])
      if (self.MINFO['dcnt'] + self.MINFO['fcnt']) > 1:
         msg = ''
         if self.MINFO['dcnt'] > 0:
            s = ('ies' if self.MINFO['dcnt'] > 1 else 'y')
            msg = "{} Director{}".format(self.MINFO['dcnt'], s) 
         if self.MINFO['fcnt'] > 0:
            s = ('s' if self.MINFO['fcnt'] > 1 else '')
            if msg: msg += " & "
            msg += "{} File{}".format(self.MINFO['fcnt'], s)
         self.pglog("Total {} changed Mode".format(msg), self.LOGWRN)
      elif (self.MINFO['dcnt'] + self.MINFO['fcnt']) == 0:
         self.pglog((self.MINFO['tpath'] if self.MINFO['tpath'] else self.MINFO['curdir']) + ": No Mode changed", self.LOGWRN)
      self.cmdlog()

   # change mode for the top level list
   def change_top_list(self, files):
      """Iterate top-level paths and change modes, expanding directories as needed.

      A directory path ending with '/' changes the mode of its contents rather
      than the directory entry itself.  Relative paths are resolved against curdir.
      Recurses into directories when -R is set or when the trailing '/' form is used.

      Args:
         files (list[str]): Source paths from the command line.
      """
      for file in files:
         info = self.check_local_file(file, 6, self.LOGWRN)
         if not info:
            self.pglog(file + ": NOT exists", self.LOGERR)
            continue
         change = 1
         if not info['isfile'] and re.search(r'/$', file):
            change = 0    # do not change the directory mode if it is ended by '/'
            file = re.sub(r'/$', '', file, 1)
         if not re.match(r'^/', file): file = self.join_paths(self.MINFO['curdir'], file)
         self.MINFO['tpath'] = (op.dirname(file) if change else file) + "/"
         if change: self.change_mode(file, info)
         if not info['isfile'] and (self.RDAMOD['R'] > 0 or not change):
            fs = self.local_glob(file, 6, self.LOGWRN)
            self.change_list(fs, 1, file)

   # recursively change directory/file mode
   def change_list(self, files, level, cdir):
      """Recursively change modes for a directory listing up to the depth limit.

      Logs a sub-count when two or more files have their mode changed in a
      single directory.

      Args:
         files (dict): Mapping of path → file-info dict from local_glob.
         level (int): Current recursion depth (1-based); stops when >= RDAMOD['R'].
         cdir (str): Path of the current directory (for log messages).
      """
      fcnt = 0
      for file in files:
         info = files[file]
         fcnt += self.change_mode(file, info)
         if not info['isfile'] and level < self.RDAMOD['R']:
            fs = self.local_glob(file, 6, self.LOGWRN)
            self.change_list(fs, level+1, file)
      if fcnt > 1:  # display sub count if two or more files changed mode
         self.pglog("{}: {} Files changed Mode".format(cdir, fcnt), self.LOGWRN)

   # change mode of a single file or directory
   def change_mode(self, file, info):
      """Change the permission mode of one file or directory.

      Skips the item if the -f/-d flag for its type is not set, if it is not
      owned by 'rdadata', or if its current mode already matches the target.
      Logs the old-to-new mode transition on success or an error on owner mismatch.
      Updates MINFO['fcnt'] for files and MINFO['dcnt'] for directories on success.

      Args:
         file (str): Absolute path to the file or directory.
         info (dict): File metadata dict from local_glob/check_local_file
                      (includes 'isfile', 'logname', 'mode').

      Returns:
         int: 1 if a file mode was successfully changed, 0 otherwise.
      """
      fname = re.sub(r'^{}'.format(self.MINFO['tpath']), '', file, 1)
      if info['isfile']:
         if not self.RDAMOD['f']: return 0
         fname = "F" + fname
         mode = self.RDAMOD['F']
      else:
         if not self.RDAMOD['d']: return 0
         fname = "D" + fname
         mode = self.RDAMOD['D']
      if info['logname'] != "rdadata":
         return self.pglog("{}: owner {} not rdadata".format(fname, info['logname']), self.LOGERR)
      if info['mode'] == mode: return 0   # no need change mode
      if self.set_local_mode(file, info['isfile'], mode, info['mode'], info['logname'], self.LOGWRN):
         if info['isfile']:
            self.MINFO['fcnt'] += 1
            return 1
         else:
            self.MINFO['dcnt'] += 1
            return 0

# main function to execute this script
def main():
   """Entry point: instantiate RdaMod, parse arguments, run, and exit."""
   import sys
   object = RdaMod()
   if object.get_command(sys.argv[0]).startswith('setuid_'):
      from rda_python_miscs.miscs_setup import main as setup_main
      setup_main()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
