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
   """Kill local processes or PBS batch jobs by process ID, parent PID, or status.

   For local processes, sends SIGKILL (-9) to the matched process and all its
   children recursively.  For PBS batch jobs, uses qdel to cancel jobs by job ID
   or by filtering all jobs in a queue by their current status.  Also records an
   interrupt flag in the dscheck table when a tracked process is killed.
   """

   def __init__(self):
      """Initialize RdaKill with default kill options."""
      super().__init__()
      self.RDAKILL = {
         'a': None,    # application name
         'h': None,    # hostname
         'p': 0,       # process id to be killed
         'P': 0,       # parent pid
         'r': 0,       # 1 - reserved for exclusive, working with -s PEND only 
         'u': None,    # login user name
         's': None,    # batch status to kill
         'q': None     # batch partition/queue for PBS, rda for default
      }

   # function to read parameters
   def read_parameters(self):
      """Parse command-line arguments into RDAKILL options.

      Accepts -a, -h, -p, -P, -q, -s, -u flags; -r is a boolean toggle.
      -p and -P are cast to int.  A bare integer argument without a leading
      flag is accepted as a process ID when -p has not been set yet.
      Displays usage and exits if no options or arguments are provided.
      """
      optcnt = 0
      option = None
      argv = sys.argv[1:]
      self.dssdb_dbname()
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "rdakill.log"   # set different log file
      self.cmdlog("rdakill {}".format(' '.join(argv)))
      for arg in argv:
         ms = re.match(r'-([ahpPqsu])$', arg)
         if ms:
            option = ms.group(1)
         elif re.match(r'-r$', arg):
            self.RDAKILL['r'] = 1
         elif re.match(r'-\w+$', arg):
            self.pglog(arg + ": Unknown Option", self.LGEREX)
         elif option:
            if self.RDAKILL[option]: self.pglog("{}: value passed to Option -{} already".format(arg, option), self.LGEREX)
            if option in 'pP':
               self.RDAKILL[option] = int(arg)
            elif option == 'h':
               self.RDAKILL[option] = self.get_short_host(arg)
            else:
               self.RDAKILL[option] = arg
            option = None
            optcnt += 1
         else:
            ms = re.match(r'^(\d+)$', arg)
            if ms and not self.RDAKILL['p']:
               self.RDAKILL['p'] = int(ms.group(1))   # bare integer accepted as PID when -p not yet set
               optcnt += 1
            else:
               self.pglog(arg + ": pass in value without Option", self.LGEREX)
      if not optcnt: self.show_usage("rdakill")
   
   # function to start actions
   def start_actions(self):
      """Dispatch to PBS or local kill path based on the -h option.

      When -h matches the PBS node name, requires either a job ID (-p) or a
      batch status (-s) and delegates accordingly.  Otherwise kills local
      processes matching -p, -P, or -a, requiring at least one to be set.
      """
      killloc = 1
      if self.RDAKILL['h']:
         self.local_host_action(self.RDAKILL['h'], "kill processes", self.PGLOG['HOSTNAME'], self.LGEREX)
         if not self.pgcmp(self.RDAKILL['h'], self.PGLOG['PBSNAME'], 1):
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
   
   # kill local processes matching the given filters
   def rdakill_processes(self, pid, ppid, aname = None, uname = None, level = 0):
      """Recursively kill local processes matching pid, ppid, app name, or user.

      Runs 'ps' with the most specific filter available, then walks each matching
      line, recursing into child processes before killing the parent.  Logs a
      warning if no matching process is found at the top level.  Also records a
      dscheck interrupt for each killed PID.

      Args:
         pid (int): Process ID to kill; 0 means no PID filter.
         ppid (int): Parent PID filter; 0 means no parent filter.
         aname (str|None): Application name substring filter.
         uname (str|None): Owner username filter; None means all users.
         level (int): Recursion depth (0 = top-level call).
      """
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
         buf = "No process identified to kill "
         if self.RDAKILL['h']:
            buf += "on " + self.RDAKILL['h']
         else:
            buf += "locally"
         self.pglog(buf, self.LOGWRN)
   
   # kill a local child process
   def kill_local_child(self, pid, uid, line):
      """Send SIGKILL to a single local process and log the outcome.

      Skips the kill if the process is no longer running.  Logs 'Kill' on
      success, 'Error Kill' if the process persists after the kill command,
      or 'Quit' if the process had already exited before the kill was sent.

      Args:
         pid (int): PID of the process to kill.
         uid (str): Owner username, used to build the kill command via suid.
         line (str): Formatted ps output line for logging context.
      """
      if self.check_process(pid):
         cmd = self.get_local_command("kill -9 {}".format(pid), uid)
         if self.pgsystem(cmd, self.LOGWRN, 260):     # 4+256
            return self.pglog("Kill: " + line, self.LOGWRN)
         elif self.check_process(pid):
            return self.pglog("Error Kill: {}\n{}".format(line, self.PGLOG['SYSERR']), self.LOGWRN)
      if not self.check_process(pid): self.pglog("Quit: " + line, self.LOGWRN)

   # kill a PBS batch job by job ID
   def rdakill_pbs_batch(self, bid):
      """Cancel a single PBS batch job by job ID using qdel.

      Looks up job info to get the owner, then runs qdel (or qdelcasper on
      Casper hosts) as that user.  Records a dscheck interrupt on success.
      Logs an error if the job ID is not found or if qdel fails.

      Args:
         bid (int): PBS batch job ID to cancel.

      Returns:
         int: 1 if the job was successfully cancelled, 0 otherwise.
      """
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

   # kill PBS batch jobs matching a given status
   def rdakill_pbs_status(self, stat, queue, uname):
      """Cancel all PBS batch jobs in a queue that match the given status.

      Queries qstat for the specified queue (defaulting to 'rda') and optional
      user filter, then calls rdakill_pbs_batch for each job whose State field
      matches stat.  Logs a summary of how many jobs were found and killed.

      Args:
         stat (str): PBS job state to match (e.g. 'PEND', 'RUN').
         queue (str|None): PBS queue name; defaults to 'gdex' if None.
         uname (str|None): Limit to jobs owned by this user; None means all users.
      """
      if not queue: queue = 'gdex'
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

   # record a dscheck interrupt for a killed process
   def record_dscheck_interrupt(self, pid, host):
      """Mark a dscheck record as interrupted when its process has been killed.

      Looks up the dscheck entry by PID and hostname.  If found, sets its status
      to 'I' (interrupted), clears the PID lock, and updates the check timestamp.

      Args:
         pid (int): PID (or PBS job ID) of the killed process.
         host (str): Hostname where the process was running.
      """
      pgrec = self.pgget("dscheck", "cindex", "pid = {} AND hostname = '{}'".format(pid, host), self.LOGERR)
      if pgrec:
         record = {'chktime': int(time.time()), 'status': 'I', 'pid': 0}   # release lock
         self.pgupdt("dscheck", record, "cindex = {}".format(pgrec['cindex']), self.LGEREX)

# main function to execute this script
def main():
   """Entry point: instantiate RdaKill, parse arguments, run, and exit."""
   import sys
   object = RdaKill()
   if object.get_command(sys.argv[0]).startswith('setuid_'):
      from rda_python_miscs.miscs_setup import main as setup_main
      setup_main()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
