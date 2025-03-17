#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdamod
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: change file/directory modes in given one or mutilple local directories
#            owned by 'rdadata'
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################
#
import re
import os
import sys
from os import path as op
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI

RDAMOD = {
   'd' : 0,     # 1 to change directory mode
   'f' : 0,     # 1 to change file mode
   'h' : 0,     # 1 to show help message
   'r' : 0,     # 1 if recursive all
   'R' : 0,     # > 0 to set recursive limit
   'F' : 0o664,   # to chnage file mode, default to 664
   'D' : 0o775,   # to chnge directory mode, default to 775
}

MINFO = {
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

   PgDBI.dssdb_dbname()
   PgLOG.set_suid(PgLOG.PGLOG['EUID'])
   PgLOG.set_help_path(__file__)
   PgLOG.PGLOG['LOGFILE'] = "rdamod.log"   # set different log file
   argv = sys.argv[1:]
   PgLOG.cmdlog("rdamod {} ({})".format(' '.join(argv), MINFO['curdir']))
   option = defopt = 'l'
   for arg in argv:
      ms = re.match(r'-(\w)$', arg)
      if ms:
         option = ms.group(1)
         if option not in RDAMOD: PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
         if 'dfhr'.find(option) > -1:
            RDAMOD[option] = 1
            option = defopt
         continue
      if not option: PgLOG.pglog(arg + ": Value provided without option", PgLOG.LGEREX)
      if option == 'l':
         MINFO['files'].append(arg)
         defopt = None
      else:
         if option == 'R':
            RDAMOD[option] = int(arg)
         elif 'FD'.find(option) > -1:
            RDAMOD[option] = PgLOG.base2int(arg, 8)
         else:
            RDAMOD[option] = arg
         option = defopt

   if RDAMOD['h'] or not MINFO['files']: PgLOG.show_usage("rdamod")
   if not (RDAMOD['d'] or RDAMOD['f']):
      RDAMOD['d'] = RDAMOD['f'] = 1   # both directories and files as default
   if not RDAMOD['R'] and RDAMOD['r']: RDAMOD['R'] = 1000
   PgDBI.validate_decs_group('rdamod', PgLOG.PGLOG['CURUID'], 1)   

   change_top_list(MINFO['files'])
   
   if (MINFO['dcnt'] + MINFO['fcnt']) > 1:
      msg = ''
      if MINFO['dcnt'] > 0:
         s = ('ies' if MINFO['dcnt'] else 'y')
         msg = "{} Director{}".format(MINFO['dcnt'], s) 
      if MINFO['fcnt'] > 0:
         s = ('s' if MINFO['fcnt'] > 1 else '')
         if msg: msg += " & "
         msg += "{} File{}".format(MINFO['fcnt'], s)
      PgLOG.pglog("Total {} changed Mode".format(msg), PgLOG.LOGWRN)
   elif (MINFO['dcnt'] + MINFO['fcnt']) == 0:
      PgLOG.pglog((MINFO['tpath'] if MINFO['tpath'] else MINFO['curdir']) + ": No Mode changed", PgLOG.LOGWRN)

   PgLOG.cmdlog()   
   PgLOG.pgexit(0)

#
# change mode for the top level list
#
def change_top_list(files):

   for file in files:
      info = PgFile.check_local_file(file, 6, PgLOG.LOGWRN)
      if not info:
         PgLOG.pglog(file + ": NOT exists", PgLOG.LOGERR)
         continue

      change = 1
      if not info['isfile'] and re.search(r'/$', file):
         change = 0    # do not change the directory mode if it is ended by '/'
         file = re.sub(r'/$', '', file, 1)

      if not re.match(r'^/', file): file = PgLOG.join_paths(MINFO['curdir'], file)
      MINFO['tpath'] = (op.dirname(file) if change else file) + "/"
      if change: change_mode(file, info)
      if not info['isfile'] and (RDAMOD['R'] > 0 or not change):
         fs = PgFile.local_glob(file, 6, PgLOG.LOGWRN)
         change_list(fs, 1, file)

#
# recursively change directory/file mode
#
def change_list(files, level, cdir):

   fcnt = 0

   for file in files:
      info = files[file]
      fcnt += change_mode(file, info)
      if not info['isfile'] and level < RDAMOD['R']:
         fs = PgFile.local_glob(file, 6, PgLOG.LOGWRN)
         change_list(fs, level+1, file)

   if fcnt > 1:  # display sub count if two more files are changed mode
      PgLOG.pglog("{}: {} Files changed Mode".format(cdir, fcnt), PgLOG.LOGWRN)

#
# change mode of a single directory/file
#
def change_mode(file, info):

   fname = re.sub(r'^{}'.format(MINFO['tpath']), '', file, 1)
   if info['isfile']:
      if not RDAMOD['d']: return 0
      fname = "F" + fname
      mode = RDAMOD['F']
   else:
      if not RDAMOD['d']: return 0
      fname = "D" + fname
      mode = RDAMOD['D']

   if info['logname'] != "rdadata":
      return PgLOG.pglog("{}: owner {} not rdadata".format(fname, info['logname']), PgLOG.LOGERR)
   if info['mode'] == mode: return 0   # no need change mode

   if PgFile.set_local_mode(file, info['isfile'], mode, info['mode'], info['logname'], PgLOG.LOGWRN):
      if info['isfile']:
         MINFO['fcnt'] += 1
         return 1
      else:
         MINFO['dcnt'] += 1
         return 0

#
# call main() to start program
#
if __name__ == "__main__": main()
