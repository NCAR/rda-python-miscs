#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdaown
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: change file/directory ownership to 'rdadata' in given one or mutilple
#            local directories that are owned by decs specialists. it needs
#            super user privilege to execute. 
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################
#
import re
import os
import sys
import glob
from os import path as op
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI

RDAOWN = {
   'd' : 0,     # 1 to change directory owner
   'f' : 0,     # 1 to change file owner
   'h' : 0,     # 1 to show help message
   'r' : 0,     # 1 if recursive all
   'R' : 0,     # > 0 to set recursive limit
   'F' : 0o664,   # to change file mode, default to 664
   'D' : 0o775,   # to change directory mode, default to 775
}

OINFO = {
   'files' : [],
   'curdir' : os.getcwd(),
   'tpath' : None,
   'dcnt' : 0,
   'fcnt' : 0
}

#
# main function to run the application
#
def main():

   argv = sys.argv[1:]
   PgDBI.dssdb_scname()
   PgLOG.set_help_path(__file__)
   PgLOG.PGLOG['LOGFILE'] = "rdaown.log"   # set different log file
   PgLOG.cmdlog("rdaown {} ({})".format(' '.join(argv), OINFO['curdir']))
   option = defopt = 'l'
   for arg in argv:
      ms = re.match(r'-(\w+)$', arg)
      if ms:
         option = ms.group(1)
         if option not in RDAOWN: PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
         if 'dfhr'.find(option) > -1:
            RDAOWN[option] = 1
            option = defopt
         continue
      if not option: PgLOG.pglog(arg + ": Value provided without option", PgLOG.LGEREX)
      if option == 'R':
         RDAOWN['R'] = int(arg)
         option = defopt
      else:
         OINFO['files'].append(arg)
         defopt = None

   if RDAOWN['h'] or not OINFO['files']: PgLOG.show_usage("rdaown")   
   if PgLOG.PGLOG['CURUID'] != "root":
      PgLOG.pglog(PgLOG.PGLOG['CURUID'] + ": you must execute 'rdaown' as 'root'!", PgLOG.LGEREX)
   if not (RDAOWN['d'] or RDAOWN['f']):
      RDAOWN['d'] = RDAOWN['f'] = 1   # list both directories and files as default
   if not RDAOWN['R'] and RDAOWN['r']: RDAOWN['R'] = 1000

   change_top_list(OINFO['files'])

   if (OINFO['dcnt'] + OINFO['fcnt']) > 1:
      msg = ""
      if OINFO['dcnt'] > 0:
         s = ("ies" if OINFO['dcnt'] > 1 else "y")
         msg = "{} Director{}".format(OINFO['dcnt'], s) 
      if OINFO['fcnt'] > 0:
         s = ('s' if OINFO['fcnt'] > 1 else '')
         if msg: msg += " & "
         msg += "{} File{}".format(OINFO['fcnt'], s)
      PgLOG.pglog("Total {} changed owner".format(msg), PgLOG.LOGWRN)
   elif (OINFO['dcnt'] + OINFO['fcnt']) == 0:
      PgLOG.pglog((OINFO['tpath'] if OINFO['tpath'] else OINFO['curdir']) + ": No Owner changed", PgLOG.LOGWRN)

   PgLOG.cmdlog()
   PgLOG.pgexit(0)

#
# change owner for the top level list
#
def change_top_list(files):
   
   for file in files:
      info = PgFile.check_local_file(file, 2, PgLOG.LOGWRN)
      if not info:
         PgLOG.pglog(file + ": NOT exists", PgLOG.LOGERR)
         continue
      change = 1
      if not info['isfile'] and re.search(r'/$', file):
         change = 0   # do not change the directory owner if it is ended by '/'
         file = re.sub(r'/$', '', file, 1)

      if not re.match(r'^/', file): file = PgLOG.join_paths(OINFO['curdir'], file)
      OINFO['tpath'] = (op.dirname(file) if change else file) + "/"
      if change: change_owner(file, info)
      if not info['isfile'] and (RDAOWN['R'] or not change):
         fs = glob.glob(file + "/*")
         change_list(fs, 1, file)

#
# recursively change directory/file owner
#
def change_list(files, level, cdir):

   fcnt = 0
   for file in files:
      info = PgFile.check_local_file(file, 2, PgLOG.LOGWRN)
      if not info: continue   # should not happen
      fcnt += change_owner(file, info)
      if not info['isfile'] and level < RDAOWN['R']:
         fs = glob.glob(file + "/*")
         change_list(fs, level+1, file)

   if fcnt > 1:  # display sub count if two more files are changed mode
      PgLOG.pglog("{}: {} Files changed owner in the directory".format(cdir, fcnt), PgLOG.LOGWRN)

#
# change owner for a single directory/file
#
def change_owner(file, info):

   fname = re.sub(r'^{}'.format(OINFO['tpath']), '', file, 1)
   if info['isfile']:
      if not RDAOWN['f']: return 0
      fname = "F" + fname
   else:
      if not RDAOWN['d']: return 0
      fname = "D" + fname

   if info['logname'] == "rdadata": return 0
   if not PgLOG.pgget("dssgrp", "", "logname = '{}'".format(info['logname']), PgLOG.LGEREX):
      return PgLOG.pglog("{}: owner {} not a DECS Specialist!".format(fname, info['logname']), PgLOG.LOGERR)
   
   if PgLOG.pgsystem("su root -c 'chown rdadata {}'".format(file), PgLOG.LOGWRN, 4):
      PgLOG.pglog("{}: {} => rdadata".format(fname, info['logname']), PgLOG.LOGWRN)
      if info['isfile']:
         OINFO['fcnt'] += 1
         return 1
      else:
         OINFO['dcnt'] += 1
         return 0

   return PgLOG.pglog("{}: Error change owner {} to rdadata".format(fname, info['logname']), PgLOG.LOGERR)

#
# call main() to start program
#
if __name__ == "__main__": main()
