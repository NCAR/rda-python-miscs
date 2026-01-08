#!/usr/bin/env python3
##################################################################################
#     Title: rdakill
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: kill a local or batch process and its child processes for a given
#            running process ID by 'rdadata'
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import sys
import time
from rda_python_common.pg_file import PgFile

class RdaKill(PgFile):

   def __init__(self):
      super().__init__()
      self.RDAKILL = {
         'a': None,    # application name
         'h': None,    # hostname
         'p': 0,       # process id to be killed
         'P': 0,       # parent pid
         'r': 0,       # 1 - reserved for exclusive, working with -s PEND only 
         'u': None,    # login user name
         's': None,    # batch status to kill
         'q': None     # batch partition/queue for SLURM/PBS, rda for default
      }

   # function to read parameters
   def read_parameters(self):
      optcnt = 0
      option = None
      argv = sys.argv[1:]
      self.dssdb_dbname()
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "rdakill.log"   # set different log file
      self.cmdlog("rdakill {}".format(' '.join(argv)))
      for arg in argv:
         ms = re.match(r'-([ahpPqstu])$', arg)
         if ms:
            option = ms.group(1)
         elif re.match(r'-r$', arg):
            self.RDAKILL['r'] = 1
         elif re.match(r'-\w+$', arg):
            self.pglog(arg + ": Unknown Option", self.LGEREX)
         elif option:
            if self.RDAKILL[option]: self.pglog("{}: value passed to Option -{} already".format(arg, option), self.LGEREX)
            if 'pPt'.find(option) > -1:
               self.RDAKILL[option] = int(arg)
            elif option == 'h':
               self.RDAKILL[option] = self.get_short_host(arg)
            else:
               self.RDAKILL[option] = arg
            option = None
            optcnt += 1
         else:
            ms = re.match(r'^(\d+)$', arg)
            if ms and self.RDAKILL['p']:
               self.RDAKILL['p'] = int(ms.group(1))   # pid allow value only without leading option
               optcnt += 1
            else:
               self.pglog(arg + ": pass in value without Option", self.LGEREX)
      if not optcnt: self.show_usage("rdakill")
   
   # function to start actions
   def start_actions(self):
      killloc = 1
      if self.RDAKILL['h']:
         self.local_host_action(self.RDAKILL['h'], "kill processes", self.PGLOG['HOSTNAME'], self.LGEREX)
         if not self.pgcmp(self.RDAKILL['h'], self.PGLOG['SLMNAME'], 1):
            if not (self.RDAKILL['p'] or self.RDAKILL['s']):
               self.pglog("Provide Batch ID or Job Status to kill SLURM jobs", self.LGEREX)
            if self.RDAKILL['p']:
               self.dakill_slurm_batch(self.RDAKILL['p'])
            else:
               self.rdakill_slurm_status(self.RDAKILL['s'], self.RDAKILL['q'], self.RDAKILL['u'])
            killloc = 0
         elif not self.pgcmp(self.RDAKILL['h'], self.PGLOG['PBSNAME'], 1):
            if not (self.RDAKILL['p'] or self.RDAKILL['s']):
               self.pglog("Provide Batch ID or Job Status to kill PBS jobs", self.LGEREX)
            if self.RDAKILL['p']:
               self.rdakill_pbs_batch(self.RDAKILL['p'])
            else:
               self.rdakill_pbs_status(self.RDAKILL['s'], self.RDAKILL['q'], self.RDAKILL['u'])
            killloc = 0
      if killloc:
         if not (self.RDAKILL['p'] or self.RDAKILL['P'] or self.RDAKILL['a']):
            self.pglog("Specify process ID, parent PID or App Name to kill", self.LGEREX)
         self.rdakill_processes(self.RDAKILL['p'], self.RDAKILL['P'], self.RDAKILL['a'], self.RDAKILL['u'])
      self.cmdlog()
   
   # kill processes for given condition
   def rdakill_processes(self, pid, ppid, aname = None, uname = None, level = 0):
      kcnt = 0
      if pid:
         cmd = "ps -p {} -f".format(pid)
      elif ppid:
         cmd = "ps --ppid {} -f".format(ppid)
      elif uname:
         cmd = "ps -u {} -f".format(uname)
      else:
         cmd = "ps -ef"
      buf = self.pgsystem(cmd, self.LGWNEX, 20)
      if buf:
         for line in re.split('\n', buf):
            ms = re.match(r'\s*(\w+)\s+(\d+)\s+(\d+)\s+(.*)$', line)
            if ms:
               uid = ms.group(1)
               cid = int(ms.group(2))
               pcid = int(ms.group(3))
               cname = ms.group(4)
               if pid and pid != cid: continue
               if ppid and ppid != pcid: continue
               if uname and not re.match(r'all$', uname, re.I) and uname != uid: continue
               if aname and cname.find(aname) < 0: continue
               kcnt += 1
               self.rdakill_processes(0, cid, None, None, level+1)
               self.kill_local_child(cid, uid, re.sub(r'  +', ' ', line))
               self.record_dscheck_interrupt(cid, self.PGLOG['HOSTNAME'])
      if not (kcnt or level):
         buf = "No process idendified to kill "
         if self.RDAKILL['h']:
            buf += "on " + self.RDAKILL['h']
         else:
            buf += "locally"
            if self.PGLOG['CURBID']: buf += "; add Option '-h SLURM' if SLURM batch ID provided"
         self.pglog(buf, self.LOGWRN)
   
   # a local child process
   def kill_local_child(self, pid, uid, line):
      if self.check_process(pid):
         cmd = self.get_local_command("kill -9 {}".format(pid), uid)
         if self.pgsystem(cmd, self.LOGWRN, 260):     # 4+256
            return self.pglog("Kill: " + line, self.LOGWRN)
         elif self.check_process(pid):
            return self.pglog("Error Kill: {}\n{}".format(line, self.PGLOG['SYSERR']), self.LOGWRN)
      if not self.check_process(pid): self.pglog("Quit: " + line, self.LOGWRN)
   
   # kill a slurm batch job
   def rdakill_slurm_batch(self, bid):
      ret = 0
      stat = self.check_slurm_status(bid, self.LOGWRN)
      if stat:
         cmd = self.get_local_command("scancel {}".format(bid), stat['USER'])
         ret = self.pgsystem(cmd, self.LOGWRN, 6)
         if ret: self.record_dscheck_interrupt(bid, self.PGLOG['SLMNAME'])
      else:
         self.pglog("{}: cannot find SLURM batch ID".format(bid), self.LOGERR)
      if not ret and self.PGLOG['SYSERR']: self.pglog(self.PGLOG['SYSERR'], self.LGEREX)
      return ret
   
   # kill SLURM batch jobs for given status
   def rdakill_slurm_status(self, stat, part, uname):
      if not part: part = 'rda'
      bcmd = "sacct -o jobid,user,state -r {} -".format(part)
      bcmd += ("u " + uname if uname else 'a')
      lines = self.get_slurm_multiple(bcmd)
      bcnt = len(lines['JOBID']) if lines else 0
      pcnt = kcnt = 0
      for i in range(bcnt):
         if lines['STATE'][i] == stat:
            pcnt += 1
            kcnt += self.rdakill_slurm_batch(lines['JOBID'][i])
      if pcnt > 0:
         s = 's' if pcnt > 1 else ''
         line = "{} of {} SLURM '{}' job{} Killed".format(kcnt, pcnt, stat, s)
      else:
         line = "No SLURM '{}' job found to kill".format(stat)
      line += " in Partition '{}'".format(part)
      if uname: line += " for " + uname
      self.pglog(line, self.LOGWRN)
   
   # kill a pbs batch job
   def rdakill_pbs_batch(self, bid):
      ret = 0
      stat = self.get_pbs_info(bid, 0, self.LOGWRN)
      if stat:
         dcmd = 'qdel'
         if self.PGLOG['HOSTTYPE'] == 'ch': dcmd += 'casper'
         cmd = self.get_local_command("{} {}".format(dcmd, bid), stat['UserName'])
         ret = self.pgsystem(cmd, self.LOGWRN, 7)
         if ret: self.record_dscheck_interrupt(bid, self.PGLOG['PBSNAME'])
      else:
         self.pglog("{}: cannot find PBS batch ID".format(bid), self.LOGERR)
      if not ret and self.PGLOG['SYSERR']: self.pglog(self.PGLOG['SYSERR'], self.LGEREX)
      return ret
   
   # kill PBS batch jobs for given status
   def rdakill_pbs_status(self, stat, queue, uname):
      if not queue: queue = 'rda'
      qopts = ''
      if uname:
         qopts = "-u " + uname
      if qopts: qopts += ' '
      qopts += queue
      lines = self.get_pbs_info(qopts, 1)
      bcnt = len(lines['JobID'])
      pcnt = kcnt = 0
      for i in range(bcnt):
         if stat != lines['State'][i]: continue
         pcnt += 1
         kcnt += self.rdakill_pbs_batch(lines['JobID'][i])
      if pcnt > 0:
         s = 's' if pcnt > 1 else ''
         line = "{} of {} PBS '{}' job{} Killed".format(kcnt, pcnt, stat, s)
      else:
         line = "No PBS '{}' job found to kill".format(stat)
      line += " in Queue '{}'".format(queue)
      if uname: line += " for " + uname
      self.pglog(line, self.LOGWRN)

   # record a dscheck 
   def record_dscheck_interrupt(self, pid, host):
      pgrec = self.pgget("dscheck", "cindex", "pid = {} AND hostname = '{}'".format(pid, host), self.LOGERR)
      if pgrec:
         record = {'chktime': int(time.time()), 'status': 'I', 'pid': 0}   # release lock
         self.pgupdt("dscheck", record, "cindex = {}".format(pgrec['cindex']), self.LGEREX)

# main function to excecute this script
def main():
   object = RdaKill()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
