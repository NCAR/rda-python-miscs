#!/usr/bin/env python3
#
##################################################################################
#
#     Title : pgwget
#    Author : Zaihua Ji, zji@ucar.edu
#      Date : 12/02/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose : wrapper to wget to get a file with wildcard in name
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################

import sys
import re
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile

OPTIONS = {
   'OP' : "-np -nH -nd -m -e robots=off --no-check-certificate",
   'UL' : None,
   'RN' : None,
   'FN' : None,
   'FC' : 1,
   'SM' : 0,
   'MC' : 0,
   'CN' : 0,
   'CR' : 0,
   'EX' : None,
   'JC' : 'cat'
}

#
# main function to excecute this script
#
def main():

   option = None
   JCS = ['cat', 'tar', 'first', 'last']
   options = '|'.join(OPTIONS)
   argv = sys.argv[1:] 
   PgLOG.PGLOG['LOGFILE'] = "pgwget.log"
   
   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
         option = None
         continue
      ms = re.match(r'^-({})$'.format(options), arg, re.I)
      if ms:
         option = ms.group(1).upper()
         if re.match(r'^(CN|CR|SM)$', option):
            OPTIONS[option] = 1
            option = None
         continue   
      if re.match(r'^-.*$', arg): PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
      if not option: PgLOG.pglog(arg + ": Value passed in without leading option", PgLOG.LGEREX)

      if option == 'JC' and arg not in JCS:
         PgLOG.pglog(arg + ": Joining Command must be one of {}".format(JCS), PgLOG.LGEREX)
      OPTIONS[option] = int(arg) if re.match(r'^(FC|MC)$', option) else arg
      option = None

   if not (OPTIONS['UL'] and OPTIONS['RN']):
      print("Usage: pgwget [-CN] [-CR] [-FC FileCount] [-JC JoinCommand] [-MC MinFileCount] [-FN FileName] -UL WebURL -RN RootFileName [-EX FileNameExtension]")
      print("   Provide at least WebURL and RootFileName to wget file(s)")
      print("   Option -CN - check new file if presents")
      print("   Option -CR - clean the downloaded remote file(s) if presents")
      print("   Option -FC - number of files to be valid download; defaults to 1")
      print("   Option -JC - file joining command, it defaults to cat, could be tar, or last/first to choose the last/first one")
      print("   Option -SM - Show wget dumping message; defaults to False")
      print("   Option -MC - minimal number of files to be valid download; defaults to -FC")
      print("   Option -FN - file name to be used if successful download; defaults to RootFileName.FileNameExtension")
      print("   Option -OP - options used by wget, defaults to '-np -nH -nd -m -e robots=off'")
      print("   Option -UL - (mandatory) WebURL with path")
      print("   Option -RN - (mandatory) the root portion of the remote file name to be downloaded")
      print("   Option -EX - file name extension to be used.")
      sys.exit(0)

   PgLOG.cmdlog("pgwget " + ' '.join(argv))
   if not OPTIONS['MC']: OPTIONS['MC'] = OPTIONS['FC']
   if not OPTIONS['SM']: OPTIONS['OP'] += ' -q'
   download_wildcard_files()   
   PgLOG.cmdlog()

   sys.exit(0)

#
# download one or multiple remote files via wget; concat files to a single one if multiple
#
def download_wildcard_files():

   deleted = 0
   if OPTIONS['FN']:
      dfile = OPTIONS['FN']
   else:
      dfile = OPTIONS['RN']
      if OPTIONS['EX']: dfile += "." + OPTIONS['EX']

   dinfo = PgFile.check_local_file(dfile, 1)
   if dinfo and not OPTIONS['CN']:
      return PgLOG.pglog("{}: file dowloaded already ({} {})".format(dfile, dinfo['date_modified'], dinfo['time_modified']), PgLOG.LOGWRN)

   build = 0 if dinfo else 1
   wfile = OPTIONS['RN'] + "*"
   if OPTIONS['EX']: wfile += "." + OPTIONS['EX']
   dlist = PgFile.local_glob(wfile, 1)
   if dfile in dlist and dinfo:
      del dlist[dfile]
      deleted = 1
   dcnt = len(dlist)

   if OPTIONS['CN'] or dcnt < OPTIONS['FC']:
      cmd = "wget {} {} -A '{}'".format(OPTIONS['OP'], OPTIONS['UL'], wfile)
      PgLOG.pgsystem(cmd, PgLOG.LOGWRN, 7)
      nlist = PgFile.local_glob(wfile, 1)
      if dfile in nlist and dinfo:
         del nlist[dfile]
         deleted = 1
      ncnt = len(nlist)
   else:
      nlist = dlist
      ncnt = dcnt

   if ncnt == 0:
      if deleted:
         return PgLOG.pglog("{}: File dowloaded on {}".format(dfile, OPTIONS['UL']), PgLOG.LOGWRN)
      else:
         return PgLOG.pglog("{}: NO file to dowload on {}".format(dfile, OPTIONS['UL']), PgLOG.LOGWRN)
   elif ncnt < OPTIONS['MC']:
      return PgLOG.pglog("{}: NOT ready, only {} of {} files dowloaded".format(dfile, ncnt, OPTIONS['MC']), PgLOG.LOGWRN)

   rfiles = sorted(nlist)
   size = skip = 0
   for i in range(ncnt):
      rfile = rfiles[i]
      rinfo = nlist[rfile]
      size += rinfo['data_size']
      if dinfo and PgUtil.cmptime(dinfo['date_modified'], dinfo['time_modified'], rinfo['date_modified'], rinfo['time_modified']) >= 0:
         PgLOG.pglog("{}: Not newer than {}".format(rfile, dfile), PgLOG.LOGWRN)
         skip += 1
      elif rfile not in dlist:
         build = 1
      elif PgFile.compare_file_info(dlist[rfile], rinfo) > 0:
         PgLOG.pglog("{}: Newer file dowloaded from {}".format(rfile, OPTIONS['UL']), PgLOG.LOGWRN)
         build = 1
      else:
         PgLOG.pglog("{}: No newer file found on ".format(rfile, OPTIONS['UL']), PgLOG.LOGWRN)

   if skip == ncnt: return 0

   if not (build or size == dinfo['data_size']): build = 1
   if not build: return PgLOG.pglog(dfile + ": Use existing file", PgLOG.LOGWRN)

   if OPTIONS['JC'] == 'cat':
      for i in range(ncnt):
         rfile = rfiles[i]
         if i == 0:
            if dfile != rfile: PgFile.local_copy_local(dfile, rfile, PgLOG.LOGWRN)
         else:
            PgLOG.pgsystem("cat {} >> {}".format(rfile, dfile), PgLOG.LOGWRN, 5)
         if OPTIONS['CR'] and dfile != rfile: PgLOG.pgsystem("rm -f " + rfile, PgLOG.LOGWRN, 5)
   elif OPTIONS['JC'] == 'tar':
      topt = 'c'
      for i in range(ncnt):
         rfile = rfiles[i]
         PgLOG.pgsystem("tar -{}vf {} {}".format(topt, dfile, rfile), PgLOG.LOGWRN, 5)
         topt = 'u'
         if OPTIONS['CR']: PgLOG.pgsystem("rm -f " + rfile, PgLOG.LOGWRN, 5)
   else:
      didx = 0 if OPTIONS['JC'] == 'first' else (ncnt - 1)
      PgLOG.pgsystem("mv {} {}".format(rfiles[didx], dfile), PgLOG.LOGWRN, 5)
      if OPTIONS['CR']:
         for i in range(ncnt):
            if i == didx: continue
            PgLOG.pgsystem("rm -f " + rfiles[i], PgLOG.LOGWRN, 5)

   return 1

#
# call main() to start program
#
if __name__ == "__main__": main()
