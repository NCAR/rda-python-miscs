#!/usr/bin/env python3
##################################################################################
#     Title: rdamod
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: change file/directory modes in given one or mutilple local directories
#            owned by 'rdadata'
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from os import path as op
from rda_python_common.pg_file import PgFile

class RdaMod(PgFile):

   def __init__(self):
      super().__init__()
      self.RDAMOD = {
         'd': 0,     # 1 to change directory mode
         'f': 0,     # 1 to change file mode
         'h': 0,     # 1 to show help message
         'r': 0,     # 1 if recursive all
         'R': 0,     # > 0 to set recursive limit
         'F': 0o664,   # to chnage file mode, default to 664
         'D': 0o775,   # to chnge directory mode, default to 775
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
            if 'dfhr'.find(option) > -1:
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
            elif 'FD'.find(option) > -1:
               self.RDAMOD[option] = self.base2int(arg, 8)
            else:
               self.RDAMOD[option] = arg
            option = defopt
      if self.RDAMOD['h'] or not self.MINFO['files']: self.show_usage("rdamod")

   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      if not (self.RDAMOD['d'] or self.RDAMOD['f']):
         self.RDAMOD['d'] = self.RDAMOD['f'] = 1   # both directories and files as default
      if not self.RDAMOD['R'] and self.RDAMOD['r']: self.RDAMOD['R'] = 1000
      self.validate_decs_group('rdamod', self.PGLOG['CURUID'], 1)   
      self.change_top_list(self.MINFO['files'])
      if (self.MINFO['dcnt'] + self.MINFO['fcnt']) > 1:
         msg = ''
         if self.MINFO['dcnt'] > 0:
            s = ('ies' if self.MINFO['dcnt'] else 'y')
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
      fcnt = 0
      for file in files:
         info = files[file]
         fcnt += self.change_mode(file, info)
         if not info['isfile'] and level < self.RDAMOD['R']:
            fs = self.local_glob(file, 6, self.LOGWRN)
            self.change_list(fs, level+1, file)
      if fcnt > 1:  # display sub count if two more files are changed mode
         self.pglog("{}: {} Files changed Mode".format(cdir, fcnt), self.LOGWRN)

   # change mode of a single directory/file
   def change_mode(self, file, info):
      fname = re.sub(r'^{}'.format(self.MINFO['tpath']), '', file, 1)
      if info['isfile']:
         if not self.RDAMOD['d']: return 0
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

# main function to excecute this script
def main():
   object = RdaMod()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
