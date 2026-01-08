#!/usr/bin/env python3
##################################################################################
#     Title: rdaown
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: change file/directory ownership to 'rdadata' in given one or mutilple
#            local directories that are owned by decs specialists. it needs
#            super user privilege to execute. 
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
import glob
from os import path as op
from rda_python_common.pg_file import PgFile

class RdaOwn(PgFile):

   def __init__(self):
      super().__init__()
      self.RDAOWN = {
         'd': 0,     # 1 to change directory owner
         'f': 0,     # 1 to change file owner
         'h': 0,     # 1 to show help message
         'r': 0,     # 1 if recursive all
         'R': 0,     # > 0 to set recursive limit
         'F': 0o664,   # to change file mode, default to 664
         'D': 0o775,   # to change directory mode, default to 775
      }
      self.OINFO = {
         'files': [],
         'curdir': os.getcwd(),
         'tpath': None,
         'dcnt': 0,
         'fcnt': 0
      }

   # function to read paramters
   def read_parameters(self):
      argv = sys.argv[1:]
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "rdaown.log"   # set different log file
      self.cmdlog("rdaown {} ({})".format(' '.join(argv), self.OINFO['curdir']))
      option = defopt = 'l'
      for arg in argv:
         ms = re.match(r'-(\w+)$', arg)
         if ms:
            option = ms.group(1)
            if option not in self.RDAOWN: self.pglog(arg + ": Unknown Option", self.LGEREX)
            if 'dfhr'.find(option) > -1:
               self.RDAOWN[option] = 1
               option = defopt
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option == 'R':
            self.RDAOWN['R'] = int(arg)
            option = defopt
         else:
            self.OINFO['files'].append(arg)
            defopt = None
      if self.RDAOWN['h'] or not self.OINFO['files']: self.show_usage("rdaown")   
      if self.PGLOG['CURUID'] != "root":
         self.pglog(self.PGLOG['CURUID'] + ": you must execute 'rdaown' as 'root'!", self.LGEREX)
      if not (self.RDAOWN['d'] or self.RDAOWN['f']):
         self.RDAOWN['d'] = self.RDAOWN['f'] = 1   # list both directories and files as default
      if not self.RDAOWN['R'] and self.RDAOWN['r']: self.RDAOWN['R'] = 1000
   
   # function to start actions
   def start_actions(self):
      self.dssdb_scname()
      self.change_top_list(self.OINFO['files'])
      if (self.OINFO['dcnt'] + self.OINFO['fcnt']) > 1:
         msg = ""
         if self.OINFO['dcnt'] > 0:
            s = ("ies" if self.OINFO['dcnt'] > 1 else "y")
            msg = "{} Director{}".format(self.OINFO['dcnt'], s) 
         if self.OINFO['fcnt'] > 0:
            s = ('s' if self.OINFO['fcnt'] > 1 else '')
            if msg: msg += " & "
            msg += "{} File{}".format(self.OINFO['fcnt'], s)
         self.pglog("Total {} changed owner".format(msg), self.LOGWRN)
      elif (self.OINFO['dcnt'] + self.OINFO['fcnt']) == 0:
         self.pglog((self.OINFO['tpath'] if self.OINFO['tpath'] else self.OINFO['curdir']) + ": No Owner changed", self.LOGWRN)
      self.cmdlog()
   
   # change owner for the top level list
   def change_top_list(self, files):
      for file in files:
         info = self.check_local_file(file, 2, self.LOGWRN)
         if not info:
            self.pglog(file + ": NOT exists", self.LOGERR)
            continue
         change = 1
         if not info['isfile'] and re.search(r'/$', file):
            change = 0   # do not change the directory owner if it is ended by '/'
            file = re.sub(r'/$', '', file, 1)
         if not re.match(r'^/', file): file = self.join_paths(self.OINFO['curdir'], file)
         self.OINFO['tpath'] = (op.dirname(file) if change else file) + "/"
         if change: self.change_owner(file, info)
         if not info['isfile'] and (self.RDAOWN['R'] or not change):
            fs = glob.glob(file + "/*")
            self.change_list(fs, 1, file)
   
   # recursively change directory/file owner
   def change_list(self, files, level, cdir):
      fcnt = 0
      for file in files:
         info = self.check_local_file(file, 2, self.LOGWRN)
         if not info: continue   # should not happen
         fcnt += self.change_owner(file, info)
         if not info['isfile'] and level < self.RDAOWN['R']:
            fs = glob.glob(file + "/*")
            self.change_list(fs, level+1, file)
      if fcnt > 1:  # display sub count if two more files are changed mode
         self.pglog("{}: {} Files changed owner in the directory".format(cdir, fcnt), self.LOGWRN)
   
   # change owner for a single directory/file
   def change_owner(self, file, info):
      fname = re.sub(r'^{}'.format(self.OINFO['tpath']), '', file, 1)
      if info['isfile']:
         if not self.RDAOWN['f']: return 0
         fname = "F" + fname
      else:
         if not self.RDAOWN['d']: return 0
         fname = "D" + fname
      if info['logname'] == "rdadata": return 0
      if not self.pgget("dssgrp", "", "logname = '{}'".format(info['logname']), self.LGEREX):
         return self.pglog("{}: owner {} not a DECS Specialist!".format(fname, info['logname']), self.LOGERR)
      if self.pgsystem("su root -c 'chown rdadata {}'".format(file), self.LOGWRN, 4):
         self.pglog("{}: {} => rdadata".format(fname, info['logname']), self.LOGWRN)
         if info['isfile']:
            self.OINFO['fcnt'] += 1
            return 1
         else:
            self.OINFO['dcnt'] += 1
            return 0
      return self.pglog("{}: Error change owner {} to rdadata".format(fname, info['logname']), self.LOGERR)

# main function to excecute this script
def main():
   object = RdaOwn()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
