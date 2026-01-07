#!/usr/bin/env python3
##################################################################################
#     Title: rdaps
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: run ps against running process ID locally or remotely
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from rda_python_common.pg_file import PgFile

class RdaPs(PgFile):

   def __init__(self):
      super().__init__()
      self.RDAPS = {
         'a' : None,   # application name
         'h' : None,   # remote hostname
         'p' : 0,      # process id to be checked
         'P' : 0,      # parent process id to be checked
         'u' : None,   # login user name
      }

   # function to read parameters
   def read_parameters(self):
      optcnt = 0
      argv = sys.argv[1:]
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "rdaps.log"   # set different log file
      self.cmdlog("rdaps {}".format(' '.join(argv)))
      for arg in argv:
         ms = re.match(r'-([ahpPtu])$', arg)
         if ms:
            option = ms.group(1)
         elif re.match(r'-\w+$', arg):
            self.pglog(arg + ": Unknown Option", self.LGEREX)
         elif option:
            if self.RDAPS[option]: self.pglog("{}: value passed to Option -{} already".format(arg, option), self.LGEREX)
            if 'pPt'.find(option) > -1:
               self.RDAPS[option] = int(arg)
            elif option == 'h':
               self.RDAPS[option] = self.get_short_host(arg)
            else:
               self.RDAPS[option] = arg
            option = None
            optcnt += 1
         else:
            ms = re.match(r'^(\d+)$', arg)
            if ms and not self.RDAPS['p']:
               self.RDAPS['p'] = int(ms.group(1))   # pid allow value only without leading option
               optcnt += 1
            else:
               self.pglog(arg + ": Value passed in without Option", self.LGEREX)
      if not optcnt: self.show_usage("rdaps")
   
   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      chkloc = 1
      if self.RDAPS['h']:
         self.local_host_action(self.RDAPS['h'], "check processes", self.PGLOG['HOSTNAME'], self.LGEREX)
         if not self.pgcmp(self.RDAPS['h'], self.PGLOG['SLMNAME'], 1):
            self.slurm_snapshot()
            chkloc = 0
         elif not self.pgcmp(self.RDAPS['h'], self.PGLOG['PBSNAME'], 1):
            self.pbs_snapshot()
            chkloc = 0
      if chkloc: self.process_snapshot()
      self.cmdlog()
   
   # get a snapshot of a process status
   def process_snapshot(self):
      if self.RDAPS['p']:
         cmd = "ps -p {} -f".format(self.RDAPS['p'])
      elif self.RDAPS['P']:
         cmd = "ps --ppid {} -f".format(self.RDAPS['P'])
      elif self.RDAPS['u']:
         cmd = "ps -u {} -f".format(self.RDAPS['u'])
      else:
         cmd = "ps -ef"
      buf = self.pgsystem(cmd, self.LGWNEX, 20)
      for line in re.split('\n', buf):
         ms = re.match(r'\s*(\w+)\s+(\d+)\s+(\d+)\s+(.*)$', line)
         if ms:
            uid = ms.group(1)
            pid = int(ms.group(2))
            ppid = int(ms.group(3))
            aname = ms.group(4)
            if self.RDAPS['u'] and self.RDAPS['u'] != uid: continue
            if self.RDAPS['p'] and self.RDAPS['p'] != pid: continue
            if self.RDAPS['P'] and self.RDAPS['P'] != ppid: continue
            if self.RDAPS['a'] and aname.find(self.RDAPS['a']) < 0: continue
            self.pglog(re.sub(r'  +', ' ', line), self.LOGWRN)
   
   # get a snapshot of a SLURM batch process status
   def slurm_snapshot(self):
      qopts = ''
      if self.RDAPS['u']: qopts += " -u " + self.RDAPS['u']
      if self.RDAPS['p']:
         qopts += " -j {}".format(self.RDAPS['p'])
      else:
         qopts =  " -p rda"
      cmd = "squeue -l" + qopts
      buf = self.pgsystem(cmd, self.LOGWRN, 272)
      if not buf:
         if self.PGLOG['SYSERR'] and self.PGLOG['SYSERR'].find('Invalid job id specified') < 0:
            self.pglog(self.PGLOG['SYSERR'], self.LGEREX)
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
            vals = re.split(r'\s+', self.pgtrim(line))
            if self.RDAPS['a'] and vals[2] and self.RDAPS['a'] != vals[2]: continue
            # move user name to front
            val = vals[3]
            vals[3] = vals[2]
            vals[2] = vals[1]
            vals[1] = vals[0]
            vals[0] = val
            self.pglog(' '.join(vals), self.LOGWRN)
   
   # get a snapshot of a PBS batch process status
   def pbs_snapshot(self):
      qopts = ''
      if self.RDAPS['u']:
         qopts = "-u {}".format(self.RDAPS['u'])
      if self.RDAPS['p']:
         if qopts: qopts += ' '
         qopts += str(self.RDAPS['p'])
      if not qopts: qopts = 'rda'
      stat = self.get_pbs_info(qopts, 1, self.LOGWRN)
      if not stat:
         if self.PGLOG['SYSERR']: self.pglog(self.PGLOG['SYSERR'], self.LGEREX)
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
         if self.RDAPS['a'] and stat['JobName'] and self.RDAPS['a'] != stat['JobName']: continue
         vals = []
         for k in ckeys:
            vals.append(stat[k][i])
         self.pglog(' '.join(vals), self.LOGWRN)

# main function to excecute this script
def main():
   object = RdaPs()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
