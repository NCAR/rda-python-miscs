#!/usr/bin/env python3
##################################################################################
#     Title : pgwget
#    Author : Zaihua Ji, zji@ucar.edu
#      Date : 12/02/2020
#             2025-03-10 transferred to package rda_python_miscs from
#             https://github.com/NCAR/rda-utility-programs.git
#             2026-01-05 convert to class PgWget
#   Purpose : wrapper to wget to get a file with wildcard in name
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import sys
import re
from rda_python_common.pg_file import PgFile

class PgWget(PgFile):

   def __init__(self):
      super().__init__()
      self.OPTIONS = {
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

   # function to read parameters
   def read_parameters(self):
      option = None
      JCS = ['cat', 'tar', 'first', 'last']
      options = '|'.join(self.OPTIONS)
      argv = sys.argv[1:] 
      self.PGLOG['LOGFILE'] = "pgwget.log"
      for arg in argv:
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
            option = None
            continue
         ms = re.match(r'^-({})$'.format(options), arg, re.I)
         if ms:
            option = ms.group(1).upper()
            if re.match(r'^(CN|CR|SM)$', option):
               self.OPTIONS[option] = 1
               option = None
            continue   
         if re.match(r'^-.*$', arg): self.pglog(arg + ": Unknown Option", self.LGEREX)
         if not option: self.pglog(arg + ": Value passed in without leading option", self.LGEREX)
         if option == 'JC' and arg not in JCS:
            self.pglog(arg + ": Joining Command must be one of {}".format(JCS), self.LGEREX)
         self.OPTIONS[option] = int(arg) if re.match(r'^(FC|MC)$', option) else arg
         option = None
      if not (self.OPTIONS['UL'] and self.OPTIONS['RN']):
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
      self.cmdlog("pgwget " + ' '.join(argv))
      if not self.OPTIONS['MC']: self.OPTIONS['MC'] = self.OPTIONS['FC']
      if not self.OPTIONS['SM']: self.OPTIONS['OP'] += ' -q'
   
   # function to start actions
   def start_actions(self):
      self.download_wildcard_files()   
      self.cmdlog()
   
   # download one or multiple remote files via wget; concat files to a single one if multiple
   def download_wildcard_files(self):
      deleted = 0
      if self.OPTIONS['FN']:
         dfile = self.OPTIONS['FN']
      else:
         dfile = self.OPTIONS['RN']
         if self.OPTIONS['EX']: dfile += "." + self.OPTIONS['EX']
      dinfo = self.check_local_file(dfile, 1)
      if dinfo and not self.OPTIONS['CN']:
         return self.pglog("{}: file dowloaded already ({} {})".format(dfile, dinfo['date_modified'], dinfo['time_modified']), self.LOGWRN)
      build = 0 if dinfo else 1
      wfile = self.OPTIONS['RN'] + "*"
      if self.OPTIONS['EX']: wfile += "." + self.OPTIONS['EX']
      dlist = self.local_glob(wfile, 1)
      if dfile in dlist and dinfo:
         del dlist[dfile]
         deleted = 1
      dcnt = len(dlist)
      if self.OPTIONS['CN'] or dcnt < self.OPTIONS['FC']:
         cmd = "wget {} {} -A '{}'".format(self.OPTIONS['OP'], self.OPTIONS['UL'], wfile)
         self.pgsystem(cmd, self.LOGWRN, 7)
         nlist = self.local_glob(wfile, 1)
         if dfile in nlist and dinfo:
            del nlist[dfile]
            deleted = 1
         ncnt = len(nlist)
      else:
         nlist = dlist
         ncnt = dcnt
      if ncnt == 0:
         if deleted:
            return self.pglog("{}: File dowloaded on {}".format(dfile, self.OPTIONS['UL']), self.LOGWRN)
         else:
            return self.pglog("{}: NO file to dowload on {}".format(dfile, self.OPTIONS['UL']), self.LOGWRN)
      elif ncnt < self.OPTIONS['MC']:
         return self.pglog("{}: NOT ready, only {} of {} files dowloaded".format(dfile, ncnt, self.OPTIONS['MC']), self.LOGWRN)
      rfiles = sorted(nlist)
      size = skip = 0
      for i in range(ncnt):
         rfile = rfiles[i]
         rinfo = nlist[rfile]
         size += rinfo['data_size']
         if dinfo and self.cmptime(dinfo['date_modified'], dinfo['time_modified'], rinfo['date_modified'], rinfo['time_modified']) >= 0:
            self.pglog("{}: Not newer than {}".format(rfile, dfile), self.LOGWRN)
            skip += 1
         elif rfile not in dlist:
            build = 1
         elif self.compare_file_info(dlist[rfile], rinfo) > 0:
            self.pglog("{}: Newer file dowloaded from {}".format(rfile, self.OPTIONS['UL']), self.LOGWRN)
            build = 1
         else:
            self.pglog("{}: No newer file found on ".format(rfile, self.OPTIONS['UL']), self.LOGWRN)
      if skip == ncnt: return 0
      if not (build or size == dinfo['data_size']): build = 1
      if not build: return self.pglog(dfile + ": Use existing file", self.LOGWRN)
      if self.OPTIONS['JC'] == 'cat':
         for i in range(ncnt):
            rfile = rfiles[i]
            if i == 0:
               if dfile != rfile: self.local_copy_local(dfile, rfile, self.LOGWRN)
            else:
               self.pgsystem("cat {} >> {}".format(rfile, dfile), self.LOGWRN, 5)
            if self.OPTIONS['CR'] and dfile != rfile: self.pgsystem("rm -f " + rfile, self.LOGWRN, 5)
      elif self.OPTIONS['JC'] == 'tar':
         topt = 'c'
         for i in range(ncnt):
            rfile = rfiles[i]
            self.pgsystem("tar -{}vf {} {}".format(topt, dfile, rfile), self.LOGWRN, 5)
            topt = 'u'
            if self.OPTIONS['CR']: self.pgsystem("rm -f " + rfile, self.LOGWRN, 5)
      else:
         didx = 0 if self.OPTIONS['JC'] == 'first' else (ncnt - 1)
         self.pgsystem("mv {} {}".format(rfiles[didx], dfile), self.LOGWRN, 5)
         if self.OPTIONS['CR']:
            for i in range(ncnt):
               if i == didx: continue
               self.pgsystem("rm -f " + rfiles[i], self.LOGWRN, 5)
      return 1

# main function to excecute this script
def main():
   object = PgWget()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
