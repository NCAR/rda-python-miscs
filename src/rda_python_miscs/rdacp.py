#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdacp
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: copy files locally and remotely by 'rdadata'
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
from rda_python_common import PgDBI
from rda_python_common import PgFile

RDACP = {
   'fh' : None,   # from host name, default to localhost
   'th' : None,   # to host name, defaul to localhost
   'fb' : None,   # from bucket name for a from file in Object Store
   'tb' : None,   # to bucket name for a to file in Object Store
   'fp' : None,   # from Globus endpoint
   'tp' : None,   # to Globus endpoint
   'f' : [],      # from file names
   't' : None,    # to file name
   'r' : 0,       # 1 if recursive all
   'R' : 0,       # > 0 to set recursive limit
   'F' : 0o664,   # to file mode, default to 664
   'D' : 0o775,   # to directory mode, default to 775
}

CINFO = {
   'tcnt' : 0,
   'htcnt' : 0,
   'cpflag' : 0,    # 1 file only, 2 directory only, 3 both
   'cpstr' : ['', 'Files', 'Directories', 'Files/Directories'],
   'fpath' : None,
   'tpath' : None,
   'fhost' : '',
   'thost' : '',
   'curdir' : os.getcwd()
}

#
# main function to run the application
#
def main():

   dohelp = 0
   argv = sys.argv[1:]
   PgDBI.dssdb_dbname()
   PgLOG.set_suid(PgLOG.PGLOG['EUID'])
   PgLOG.set_help_path(__file__)
   PgLOG.PGLOG['LOGFILE'] = "rdacp.log"   # set different log file
   PgLOG.cmdlog("rdacp {} ({})".format(' '.join(argv), CINFO['curdir']))
   defopt = option = 'f'
   for arg in argv:
      if re.match(r'-(h|-help)$', arg, re.I):
         dohelp = 1
         continue
      ms = re.match(r'-(\w+)$', arg)
      if ms:
         option = ms.group(1)
         if option not in RDACP: PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
         if option == 'r':
            RDACP['r'] = 1
            option = None
         continue
      if not option: PgLOG.pglog(arg + ": Value provided without option", PgLOG.LGEREX)
      if option == "f":
         RDACP['f'].append(arg)
         defopt = None
      else:
         if option == 'R':
            RDACP[option] = int(arg)
         elif 'FD'.find(option) > -1:
            RDACP[option] = PgLOG.base2int(arg, 8)
         else:
            RDACP[option] = arg
            if option == 'th':
               CINFO['thost'] = arg + '-'
            elif option == 'fh':
               CINFO['fhost'] = arg + '-'
         option = defopt
            
   if dohelp or not RDACP['f']: PgLOG.show_usage("rdacp")
   PgDBI.validate_decs_group('rdacp', PgLOG.PGLOG['CURUID'], 1)
   if not RDACP['R'] and RDACP['r']: RDACP['R'] = 1000
   if not RDACP['t']:
      CINFO['tpath'] = RDACP['t'] = "."
   else:
      ms = re.match(r'^(.+)/$', RDACP['t'])
      if ms:
         CINFO['tpath'] = ms.group(1)
      else:
         tinfo = PgFile.check_gdex_file(RDACP['t'], RDACP['th'], 0, PgLOG.LGWNEX)
         if tinfo and tinfo['isfile'] == 0: CINFO['tpath'] = RDACP['t']
   PgLOG.PGLOG['FILEMODE'] = RDACP['F']
   PgLOG.PGLOG['EXECMODE'] = RDACP['D']

   fcnt = len(RDACP['f'])
   if not CINFO['tpath'] and fcnt > 1:
      PgLOG.pglog("{}{}: Cannot copy multiple files to a single file".format(CINFO['thost'], RDACP['t']), PgLOG.LGEREX)
   if RDACP['th'] and RDACP['fh'] and RDACP['th'] == RDACP['fh'] and RDACP['fh'] != 'HPSS':
      PgLOG.pglog(RDACP['fh'] + ": Cannot copy file onto the same host", PgLOG.LGEREX)
   if RDACP['fb']:
      PgLOG.PGLOG['OBJCTBKT'] = RDACP['fb']
   elif RDACP['tb']:
      PgLOG.PGLOG['OBJCTBKT'] = RDACP['tb']
   if RDACP['fp']:
      PgLOG.PGLOG['BACKUPEP'] = RDACP['fp']
   elif RDACP['tp']:
      PgLOG.PGLOG['BACKUPEP'] = RDACP['tp']

   copy_top_list(RDACP['f'])

   hinfo = ''
   if RDACP['fh']: hinfo += " From " + RDACP['fh']
   if RDACP['th']: hinfo += " To " + RDACP['th']

   if CINFO['tcnt'] > 1:
      PgLOG.pglog("Total {} {} copiled{}".format(CINFO['tcnt'], CINFO['cpstr'][CINFO['cpflag']], hinfo), PgLOG.LOGWRN)
   elif CINFO['tcnt'] == 0 and not RDACP['fh']:
      PgLOG.pglog("{}: No File copied{}".format((CINFO['fpath'] if CINFO['fpath'] else CINFO['curdir']), hinfo), PgLOG.LOGWRN)
   
   PgLOG.cmdlog()
   PgLOG.pgexit(0)

#
# display the top level list
#
def copy_top_list(files):
   
   for file in files:
      if RDACP['th'] and not PgUtil.pgcmp(RDACP['th'], PgLOG.PGLOG['BACKUPNM'], 1):
         info = PgFile.check_globus_file(file, 'gdex-glade', 0, PgLOG.LGWNEX)
      else:
         info = PgFile.check_gdex_file(file, RDACP['fh'], 0, PgLOG.LGWNEX)
      if not info:
         PgLOG.pglog("{}{}: {}".format(CINFO['fhost'], file, PgLOG.PGLOG['MISSFILE']), PgLOG.LOGERR)
         continue

      dosub = 0
      if info['isfile'] == 0:
         CINFO['cpflag'] |= 2
         if not CINFO['tpath']:
            PgLOG.pglog("{}{}: Cannot copy directory to a single file".format(CINFO['fhost'], file), PgLOG.LGEREX)

         if re.search(r'/$', file):
            dosub = 1   # copy the file under this directory if it is ended by '/'
            file = re.sub(r'/$', '', file)
      else:
         CINFO['cpflag'] |= 1

      if not re.match(r'^/', file): file = PgLOG.join_paths(CINFO['curdir'], file)
      CINFO['fpath'] = (file if dosub else op.dirname(file)) + "/"
      if info['isfile']:
         CINFO['tcnt'] += copy_file(file, info['isfile'])
      elif dosub or RDACP['R']:
         flist = PgFile.gdex_glob(file, RDACP['fh'], 0, PgLOG.LGWNEX)
         if flist: copy_list(flist, 1, file)
      else:
         PgLOG.pglog("{}{}: Add option -r to copy directory".format(CINFO['fhost'], file), PgLOG.LGEREX)

#
# recursively copy directory/file
#
def copy_list(tlist, level, cdir):

   fcnt = 0

   for file in tlist:
      if tlist[file]['isfile']:
         fcnt += copy_file(file, tlist[file]['isfile'])
         CINFO['cpflag'] |= (1 if tlist[file]['isfile'] else 2)
      elif level < RDACP['R']:
         flist = PgFile.gdex_glob(file, RDACP['fh'], 0, PgLOG.LGWNEX)
         if flist: copy_list(flist, level+1, file)

   if fcnt > 1:   # display sub count if two or more files are copied
      PgLOG.pglog("{}{}: {} {} copied from directory".format(CINFO['fhost'], cdir, fcnt, CINFO['cpstr'][CINFO['cpflag']]), PgLOG.LOGWRN)
   CINFO['tcnt'] += fcnt

#
# copy one file each time
#
def copy_file(fromfile, isfile):

   if CINFO['tpath']:
      fname = re.sub(r'^{}'.format(CINFO['fpath']), '', fromfile)
      if isfile:
         tofile = PgLOG.join_paths(CINFO['tpath'], fname)
      else:
         tofile = CINFO['tpath'] + '/'
   else:
      tofile = RDACP['t']
 
   return (1 if PgFile.copy_gdex_file(tofile, fromfile, RDACP['th'], RDACP['fh'], PgLOG.LGWNEX) else 0)

#
# call main() to start program
#
if __name__ == "__main__": main()

