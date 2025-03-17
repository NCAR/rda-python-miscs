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
   'hf' : None,   # htar file name
   'th' : None,   # to host name, defaul to localhost
   'fb' : None,   # from bucket name for a from file in Object Store
   'tb' : None,   # to bucket name for a to file in Object Store
   'fp' : None,   # from Globus endpoint
   'tp' : None,   # to Globus endpoint
   'fl' : 0,      # file limit for htar
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
   'curdir' : os.getcwd(),
   'ishpss' : 0
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
         if option == 'R' or option == 'fl':
            RDACP[option] = int(arg)
         elif 'FD'.find(option) > -1:
            RDACP[option] = PgLOG.base2int(arg, 8)
         else:
            RDACP[option] = arg
            if option == 'th':
               CINFO['thost'] = arg + '-'
               if re.match(r'^HPSS', arg, re.I): CINFO['ishpss'] |= 1
            elif option == 'fh':
               CINFO['fhost'] = arg + '-'
               if re.match(r'^HPSS', arg, re.I): CINFO['ishpss'] |= 2
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
         tinfo = PgFile.check_rda_file(RDACP['t'], RDACP['th'], 0, PgLOG.LGWNEX)
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

   if RDACP['hf']:
      if CINFO['ishpss'] == 2:
         copy_htar_member_files(RDACP['f'])
      elif CINFO['ishpss'] == 1:
         if RDACP['fl'] > 0:
            multiple_htar_hpss()
         elif PgFile.local_htar_hpss(RDACP['hf'], RDACP['f'], PgLOG.LGWNEX):
            CINFO['tcnt'] = len(RDACP['f'])
            CINFO['hcnt'] = 1
      elif CINFO['ishpss'] == 0:
         PgLOG.pglog(RDACP['hf'] + ": Cannot htar for missing option -fh/-th HPSS", PgLOG.LGEREX)
      else:
         PgLOG.pglog(RDACP['hf'] + ": Cannot htar for seting options -fh HPSS & -th HPSS", PgLOG.LGEREX)
   else:
      copy_top_list(RDACP['f'])

   hinfo = ''
   if RDACP['fh']: hinfo += " From " + RDACP['fh']
   if RDACP['th']: hinfo += " To " + RDACP['th']
   if RDACP['hf']:
      s = 'Htarred' if CINFO['ishpss'] == 1 else 'Un-Htarred'
      if CINFO['tcnt'] > 1:
         PgLOG.pglog("Total {} files {}{}".format(CINFO['tcnt'], s, hinfo), PgLOG.LOGWRN)
         if CINFO['hcnt'] > 1: PgLOG.pglog("{} HTAR files are generated".format(CINFO['hcnt']), PgLOG.LOGWRN)
      elif CINFO['tcnt'] == 0:
         PgLOG.pglog("{}: No File {}{}".format((CINFO['fpath'] if CINFO['fpath'] else CINFO['curdir']), s, hinfo), PgLOG.LOGWRN)
   else:
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
         info = PgFile.check_globus_file(file, 'rda-glade', 0, PgLOG.LGWNEX)
      else:
         info = PgFile.check_rda_file(file, RDACP['fh'], 0, PgLOG.LGWNEX)
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
         flist = PgFile.rda_glob(file, RDACP['fh'], 0, PgLOG.LGWNEX)
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
         flist = PgFile.rda_glob(file, RDACP['fh'], 0, PgLOG.LGWNEX)
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
 
   return (1 if PgFile.copy_rda_file(tofile, fromfile, RDACP['th'], RDACP['fh'], PgLOG.LGWNEX) else 0)

#
# copy htar member files from HPSS to local
#
def copy_htar_member_files(files):

   htarfile = RDACP['hf']
   for f in files:
      info = check_htar_file(f, htarfile, 0, PgLOG.LGWNEX)
      if not info:
         PgLOG.pglog("{}{}: {} in tar file {}".format(CINFO['fhost'], f, PgLOG.PGLOG['MISSFILE'], htarfile), PgLOG.LOGERR)
         continue
      elif info['isfile'] == 0:
         PgLOG.pglog("{}{}: Cannot copy directory from htar file {}".format(CINFO['fhost'], f, htarfile), PgLOG.LGEREX)

      if PgFile.hpss_htar_local(f, htarfile, PgLOG.LGWNEX):
         tcnt += 1
         if not CINFO['tpath']:
            t = RDACP['tf']   # copy a single htar member file
         elif CINFO['tpath'] != '.':
            t = PgUtil.join_paths(CINFO['tpath'], f)
         else:
            t = None
         if t:
            ms = re.match(r'^\./{0,1}(.+)$', t)
            if ms: t = ms.group(1)
            if f != t and PgFile.move_local_file(t, f, PgLOG.LGWNEX): CINFO['tcnt'] += 1
   if cinfo['tcnt'] > 0: CINFO['hcnt'] = 1

#
# thar local files to multiple htar files
#
def multiple_htar_hpss():

   locfiles = PgUtil.recursive_files(fromfiles)
   lcnt = len(locfiles)

   if RDACP['fl'] > 5000000:
      PgLOG.pglog("{}: too large, reduces to 5000000".format(RDACP['fl']), PgLOG.LOGWRN)
      RDACP['fl'] = 5000000

   fcnt = int(lcnt/flimit)
   if fcnt*flimit == lcnt:
      mcnt = flimit
   else:
      fcnt += 1
      mcnt = int(lcnt/fcnt)
      if mcnt*fcnt < lcnt: mcnt += 1 

   if fcnt > 1: PgLOG.pglog("{}: archive {} local files to {} htar files".format(htarfile, lcnt, fcnt), PgLOG.LOGWRN)

   for i in range(fcnt):
      idx1 = i*mcnt
      if i == (fcnt-1):
         idx2 = lcnt
         mcnt = lcnt - idx1
      else:
         idx2 = idx1 + mcnt
      mfiles = locfiles[idx1:idx2]
      hfile = re.sub(r'\.htar$', '_{}.htar'.format(i), htarfile) if i > 0 else htarfile
      if PgFile.local_htar_hpss(hfile, mfiles, PgLOG.LGWNEX):
         if fcnt > 1: PgLOG.pglog("HPSS-{}: {} file{} Htarred".format(hfile, mcnt), PgLOG.LOGWRN)
         CINFO['tcnt'] += mcnt
         CINFO['hcnt'] += 1

#
# call main() to start program
#
if __name__ == "__main__": main()

