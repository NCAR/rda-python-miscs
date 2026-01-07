#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdaps
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: run ps against running process ID locally or remotely
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################
#
import re
import os
import sys
from rda_python_common import PgLOG
from rda_python_common import PgSIG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI

RDAPS = {
   'a' : None,   # application name
   'h' : None,   # remote hostname
   'p' : 0,      # process id to be checked
   'P' : 0,      # parent process id to be checked
   'u' : None,   # login user name
}

#
# main function to run the application
#
def main():

   optcnt = 0
   argv = sys.argv[1:]
   PgDBI.dssdb_dbname()
   PgLOG.set_suid(PgLOG.PGLOG['EUID'])
   PgLOG.set_help_path(__file__)
   PgLOG.PGLOG['LOGFILE'] = "rdaps.log"   # set different log file
   PgLOG.cmdlog("rdaps {}".format(' '.join(argv)))
   
   for arg in argv:
      ms = re.match(r'-([ahpPtu])$', arg)
      if ms:
         option = ms.group(1)
      elif re.match(r'-\w+$', arg):
         PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
      elif option:
         if RDAPS[option]: PgLOG.pglog("{}: value passed to Option -{} already".format(arg, option), PgLOG.LGEREX)
         if 'pPt'.find(option) > -1:
            RDAPS[option] = int(arg)
         elif option == 'h':
            RDAPS[option] = PgLOG.get_short_host(arg)
         else:
            RDAPS[option] = arg
         option = None
         optcnt += 1
      else:
         ms = re.match(r'^(\d+)$', arg)
         if ms and not RDAPS['p']:
            RDAPS['p'] = int(ms.group(1))   # pid allow value only without leading option
            optcnt += 1
         else:
            PgLOG.pglog(arg + ": Value passed in without Option", PgLOG.LGEREX)
   
   if not optcnt: PgLOG.show_usage("rdaps")
   chkloc = 1
   if RDAPS['h']:
      PgFile.local_host_action(RDAPS['h'], "check processes", PgLOG.PGLOG['HOSTNAME'], PgLOG.LGEREX)
      if not PgUtil.pgcmp(RDAPS['h'], PgLOG.PGLOG['SLMNAME'], 1):
         slurm_snapshot()
         chkloc = 0
      elif not PgUtil.pgcmp(RDAPS['h'], PgLOG.PGLOG['PBSNAME'], 1):
         pbs_snapshot()
         chkloc = 0
   if chkloc: process_snapshot()
   
   PgLOG.cmdlog()
   PgLOG.pgexit(0)

#
# get a snapshot of a process status
#
def process_snapshot():

   if RDAPS['p']:
      cmd = "ps -p {} -f".format(RDAPS['p'])
   elif RDAPS['P']:
      cmd = "ps --ppid {} -f".format(RDAPS['P'])
   elif RDAPS['u']:
      cmd = "ps -u {} -f".format(RDAPS['u'])
   else:
      cmd = "ps -ef"

   buf = PgLOG.pgsystem(cmd, PgLOG.LGWNEX, 20)

   for line in re.split('\n', buf):
      ms = re.match(r'\s*(\w+)\s+(\d+)\s+(\d+)\s+(.*)$', line)
      if ms:
         uid = ms.group(1)
         pid = int(ms.group(2))
         ppid = int(ms.group(3))
         aname = ms.group(4)
         if RDAPS['u'] and RDAPS['u'] != uid: continue
         if RDAPS['p'] and RDAPS['p'] != pid: continue
         if RDAPS['P'] and RDAPS['P'] != ppid: continue
         if RDAPS['a'] and aname.find(RDAPS['a']) < 0: continue
         PgLOG.pglog(re.sub(r'  +', ' ', line), PgLOG.LOGWRN)

#
# get a snapshot of a SLURM batch process status
#
def slurm_snapshot():

   qopts = ''
   if RDAPS['u']: qopts += " -u " + RDAPS['u']
   if RDAPS['p']:
      qopts += " -j {}".format(RDAPS['p'])
   else:
      qopts =  " -p rda"
   cmd = "squeue -l" + qopts

   buf = PgLOG.pgsystem(cmd, PgLOG.LOGWRN, 272)
   if not buf:
      if PgLOG.PGLOG['SYSERR'] and PgLOG.PGLOG['SYSERR'].find('Invalid job id specified') < 0:
         PgLOG.pglog(PgLOG.PGLOG['SYSERR'], PgLOG.LGEREX)
      return

   lines = re.split(r'\n', buf)
   lcnt = len(lines)
   if lcnt < 3: return
   dochk = 1
   for line in lines:
      if not line: continue
      if dochk:
         if re.match(r'^\s*JOBID\s', line): dochk = 0
      else:
         vals = re.split(r'\s+', PgLOG.pgtrim(line))
         if RDAPS['a'] and vals[2] and RDAPS['a'] != vals[2]: continue
         # move user name to front
         val = vals[3]
         vals[3] = vals[2]
         vals[2] = vals[1]
         vals[1] = vals[0]
         vals[0] = val
         PgLOG.pglog(' '.join(vals), PgLOG.LOGWRN)

#
# get a snapshot of a PBS batch process status
#
def pbs_snapshot():

   qopts = ''
   if RDAPS['u']:
      qopts = "-u {}".format(RDAPS['u'])
   if RDAPS['p']:
      if qopts: qopts += ' '
      qopts += str(RDAPS['p'])
   if not qopts: qopts = 'rda'

   stat = PgSIG.get_pbs_info(qopts, 1, PgLOG.LOGWRN)
   if not stat:
      if PgLOG.PGLOG['SYSERR']: PgLOG.pglog(PgLOG.PGLOG['SYSERR'], PgLOG.LGEREX)
      return

   lcnt = len(stat['JobID'])

   ckeys = list(stat.keys())
   kcnt = len(ckeys)
   # moving 'UserName' to the first
   for i in range(kcnt):
      if i > 0 and ckeys[i] == 'UserName':
         j = i
         while j > 0:
            ckeys[j] = ckeys[j-1]
            j -= 1
         ckeys[0] = 'UserName'
         break

   for i in range(lcnt):
      if RDAPS['a'] and stat['JobName'] and RDAPS['a'] != stat['JobName']: continue
      vals = []
      for k in ckeys:
         vals.append(stat[k][i])
      PgLOG.pglog(' '.join(vals), PgLOG.LOGWRN)

#
# call main() to start program
#
if __name__ == "__main__": main()
