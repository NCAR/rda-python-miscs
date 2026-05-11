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
   """Wrapper around wget to download one or more files identified by a root name pattern.

   Supports wildcard-based remote file matching, optional freshness checks, and
   multiple strategies for combining multiple downloaded parts into a single output
   file (concatenation, tar archive, or selecting the first/last file).
   """

   def __init__(self):
      """Initialize PgWget with default wget options and download control flags."""
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
      """Parse command-line arguments into OPTIONS and validate required inputs.

      Recognises boolean flags -CN, -CR, -SM and value options -OP, -UL, -RN,
      -FN, -FC, -MC, -EX, -JC (case-insensitive).  -FC and -MC are cast to int.
      -JC must be one of: cat, tar, first, last.  Prints usage and exits if
      -UL or -RN is missing.  Defaults MC to FC and appends -q to OP when -SM
      is not set.
      """
      self.set_help_path(__file__)
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
         self.show_usage("pgwget")
      self.cmdlog("pgwget " + ' '.join(argv))
      if not self.OPTIONS['MC']: self.OPTIONS['MC'] = self.OPTIONS['FC']
      if not self.OPTIONS['SM']: self.OPTIONS['OP'] += ' -q'
   
   # function to start actions
   def start_actions(self):
      """Run the wildcard download and close the command log."""
      self.download_wildcard_files()
      self.cmdlog()
   
   # download one or multiple remote files via wget; join files to a single one if multiple
   def download_wildcard_files(self):
      """Download remote files matching the wildcard pattern and combine into one output file.

      Skips the download if the local output file already exists and -CN is not set.
      Runs wget only when -CN is set or fewer than FC files are already present locally.
      Compares timestamps and file metadata to decide whether a rebuild is needed.
      Combines downloaded parts using the strategy selected by -JC (cat/tar/first/last).
      Removes intermediate part-files when -CR is set.

      Returns:
         int: 1 if the output file was built or rebuilt, 0 if all parts were already
              up-to-date, or None (implicitly) when a warning/error caused early return.
      """
      deleted = 0
      if self.OPTIONS['FN']:
         dfile = self.OPTIONS['FN']
      else:
         dfile = self.OPTIONS['RN']
         if self.OPTIONS['EX']: dfile += "." + self.OPTIONS['EX']
      dinfo = self.check_local_file(dfile, 1)
      if dinfo and not self.OPTIONS['CN']:
         return self.pglog("{}: file downloaded already ({} {})".format(dfile, dinfo['date_modified'], dinfo['time_modified']), self.LOGWRN)
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
            return self.pglog("{}: File downloaded on {}".format(dfile, self.OPTIONS['UL']), self.LOGWRN)
         else:
            return self.pglog("{}: NO file to download on {}".format(dfile, self.OPTIONS['UL']), self.LOGWRN)
      elif ncnt < self.OPTIONS['MC']:
         return self.pglog("{}: NOT ready, only {} of {} files downloaded".format(dfile, ncnt, self.OPTIONS['MC']), self.LOGWRN)
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
            self.pglog("{}: Newer file downloaded from {}".format(rfile, self.OPTIONS['UL']), self.LOGWRN)
            build = 1
         else:
            self.pglog("{}: No newer file found on {}".format(rfile, self.OPTIONS['UL']), self.LOGWRN)
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

# main function to execute this script
def main():
   """Entry point: instantiate PgWget, parse arguments, run, and exit."""
   object = PgWget()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
