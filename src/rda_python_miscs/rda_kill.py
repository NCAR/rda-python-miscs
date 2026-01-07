#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdakill
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: kill a local or batch process and its child processes for a given
#            running process ID by 'rdadata'
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################
#
import re
import sys
import time
from rda_python_common import PgLOG
from rda_python_common import PgSIG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI

RDAKILL = {
   'a' : None,    # application name
   'h' : None,    # hostname
   'p' : 0,       # process id to be killed
   'P' : 0,       # parent pid
   'r' : 0,       # 1 - reserved for exclusive, working with -s PEND only 
   'u' : None,    # login user name
   's' : None,    # batch status to kill
   'q' : None     # batch partition/queue for SLURM/PBS, rda for default
}

#
# main function to run the application
#
def main():

   optcnt = 0
   option = None
   argv = sys.argv[1:]
   PgDBI.dssdb_dbname()
   PgLOG.set_suid(PgLOG.PGLOG['EUID'])
   PgLOG.set_help_path(__file__)
   PgLOG.PGLOG['LOGFILE'] = "rdakill.log"   # set different log file
   PgLOG.cmdlog("rdakill {}".format(' '.join(argv)))
   
   for arg in argv:
      ms = re.match(r'-([ahpPqstu])$', arg)
      if ms:
         option = ms.group(1)
      elif re.match(r'-r$', arg):
         RDAKILL['r'] = 1
      elif re.match(r'-\w+$', arg):
         PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
      elif option:
         if RDAKILL[option]: PgLOG.pglog("{}: value passed to Option -{} already".format(arg, option), PgLOG.LGEREX)
         if 'pPt'.find(option) > -1:
            RDAKILL[option] = int(arg)
         elif option == 'h':
            RDAKILL[option] = PgLOG.get_short_host(arg)
         else:
            RDAKILL[option] = arg
         option = None
         optcnt += 1
      else:
         ms = re.match(r'^(\d+)$', arg)
         if ms and RDAKILL['p']:
            RDAKILL['p'] = int(ms.group(1))   # pid allow value only without leading option
            optcnt += 1
         else:
            PgLOG.pglog(arg + ": pass in value without Option", PgLOG.LGEREX)
   
   if not optcnt: PgLOG.show_usage("rdakill")
   killloc = 1
   if RDAKILL['h']:
      PgFile.local_host_action(RDAKILL['h'], "kill processes", PgLOG.PGLOG['HOSTNAME'], PgLOG.LGEREX)
      if not PgUtil.pgcmp(RDAKILL['h'], PgLOG.PGLOG['SLMNAME'], 1):
         if not (RDAKILL['p'] or RDAKILL['s']):
            PgLOG.pglog("Provide Batch ID or Job Status to kill SLURM jobs", PgLOG.LGEREX)
         if RDAKILL['p']:
            rdakill_slurm_batch(RDAKILL['p'])
         else:
            rdakill_slurm_status(RDAKILL['s'], RDAKILL['q'], RDAKILL['u'])
         killloc = 0
      elif not PgUtil.pgcmp(RDAKILL['h'], PgLOG.PGLOG['PBSNAME'], 1):
         if not (RDAKILL['p'] or RDAKILL['s']):
            PgLOG.pglog("Provide Batch ID or Job Status to kill PBS jobs", PgLOG.LGEREX)
         if RDAKILL['p']:
            rdakill_pbs_batch(RDAKILL['p'])
         else:
            rdakill_pbs_status(RDAKILL['s'], RDAKILL['q'], RDAKILL['u'])
         killloc = 0
   if killloc:
      if not (RDAKILL['p'] or RDAKILL['P'] or RDAKILL['a']):
         PgLOG.pglog("Specify process ID, parent PID or App Name to kill", PgLOG.LGEREX)
      rdakill_processes(RDAKILL['p'], RDAKILL['P'], RDAKILL['a'], RDAKILL['u'])

   PgLOG.cmdlog()
   PgLOG.pgexit(0)

#
# kill processes for given condition
#
def rdakill_processes(pid, ppid, aname = None, uname = None, level = 0):

   kcnt = 0
   if pid:
      cmd = "ps -p {} -f".format(pid)
   elif ppid:
      cmd = "ps --ppid {} -f".format(ppid)
   elif uname:
      cmd = "ps -u {} -f".format(uname)
   else:
      cmd = "ps -ef"

   buf = PgLOG.pgsystem(cmd, PgLOG.LGWNEX, 20)
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
            rdakill_processes(0, cid, None, None, level+1)
            kill_local_child(cid, uid, re.sub(r'  +', ' ', line))
            record_dscheck_interrupt(cid, PgLOG.PGLOG['HOSTNAME'])

   if not (kcnt or level):
      buf = "No process idendified to kill "
      if RDAKILL['h']:
         buf += "on " + RDAKILL['h']
      else:
         buf += "locally"
         if PgLOG.PGLOG['CURBID']: buf += "; add Option '-h SLURM' if SLURM batch ID provided"
      PgLOG.pglog(buf, PgLOG.LOGWRN)

#
# a local child process
def kill_local_child(pid, uid, line):

   if PgSIG.check_process(pid):
      cmd = PgLOG.get_local_command("kill -9 {}".format(pid), uid)
      if PgLOG.pgsystem(cmd, PgLOG.LOGWRN, 260):     # 4+256
         return PgLOG.pglog("Kill: " + line, PgLOG.LOGWRN)
      elif PgSIG.check_process(pid):
         return PgLOG.pglog("Error Kill: {}\n{}".format(line, PgLOG.PGLOG['SYSERR']), PgLOG.LOGWRN)

   if not PgSIG.check_process(pid): PgLOG.pglog("Quit: " + line, PgLOG.LOGWRN)

#
# kill a slurm batch job
#
def rdakill_slurm_batch(bid):

   ret = 0
   stat = PgSIG.check_slurm_status(bid, PgLOG.LOGWRN)
   if stat:
      cmd = PgLOG.get_local_command("scancel {}".format(bid), stat['USER'])
      ret = PgLOG.pgsystem(cmd, PgLOG.LOGWRN, 6)
      if ret: record_dscheck_interrupt(bid, PgLOG.PGLOG['SLMNAME'])
   else:
      PgLOG.pglog("{}: cannot find SLURM batch ID".format(bid), PgLOG.LOGERR)

   if not ret and PgLOG.PGLOG['SYSERR']: PgLOG.pglog(PgLOG.PGLOG['SYSERR'], PgLOG.LGEREX)
   
   return ret

#
# kill SLURM batch jobs for given status
#
def rdakill_slurm_status(stat, part, uname):
   
   if not part: part = 'rda'
   bcmd = "sacct -o jobid,user,state -r {} -".format(part)
   bcmd += ("u " + uname if uname else 'a')

   lines = PgSIG.get_slurm_multiple(bcmd)
   bcnt = len(lines['JOBID']) if lines else 0
   pcnt = kcnt = 0
   for i in range(bcnt):
      if lines['STATE'][i] == stat:
         pcnt += 1
         kcnt += rdakill_slurm_batch(lines['JOBID'][i])

   if pcnt > 0:
      s = 's' if pcnt > 1 else ''
      line = "{} of {} SLURM '{}' job{} Killed".format(kcnt, pcnt, stat, s)
   else:
      line = "No SLURM '{}' job found to kill".format(stat)

   line += " in Partition '{}'".format(part)
   if uname: line += " for " + uname
   PgLOG.pglog(line, PgLOG.LOGWRN)

#
# kill a pbs batch job
#
def rdakill_pbs_batch(bid):

   ret = 0
   stat = PgSIG.get_pbs_info(bid, 0, PgLOG.LOGWRN)
   if stat:
      dcmd = 'qdel'
      if PgLOG.PGLOG['HOSTTYPE'] == 'ch': dcmd += 'casper'
      cmd = PgLOG.get_local_command("{} {}".format(dcmd, bid), stat['UserName'])
      ret = PgLOG.pgsystem(cmd, PgLOG.LOGWRN, 7)
      if ret: record_dscheck_interrupt(bid, PgLOG.PGLOG['PBSNAME'])
   else:
      PgLOG.pglog("{}: cannot find PBS batch ID".format(bid), PgLOG.LOGERR)

   if not ret and PgLOG.PGLOG['SYSERR']: PgLOG.pglog(PgLOG.PGLOG['SYSERR'], PgLOG.LGEREX)

   return ret

#
# kill PBS batch jobs for given status
#
def rdakill_pbs_status(stat, queue, uname):

   if not queue: queue = 'rda'
   qopts = ''
   if uname:
      qopts = "-u " + uname
   if qopts: qopts += ' '
   qopts += queue
   lines = PgSIG.get_pbs_info(qopts, 1)
   bcnt = len(lines['JobID'])
   pcnt = kcnt = 0
   for i in range(bcnt):
      if stat != lines['State'][i]: continue
      pcnt += 1
      kcnt += rdakill_pbs_batch(lines['JobID'][i])

   if pcnt > 0:
      s = 's' if pcnt > 1 else ''
      line = "{} of {} PBS '{}' job{} Killed".format(kcnt, pcnt, stat, s)
   else:
      line = "No PBS '{}' job found to kill".format(stat)

   line += " in Queue '{}'".format(queue)
   if uname: line += " for " + uname
   PgLOG.pglog(line, PgLOG.LOGWRN)

#
# record a dscheck 
#
def record_dscheck_interrupt(pid, host):

   pgrec = PgDBI.pgget("dscheck", "cindex", "pid = {} AND hostname = '{}'".format(pid, host), PgLOG.LOGERR)
   if pgrec:
      record = {'chktime' : int(time.time()), 'status' : 'I', 'pid' : 0}   # release lock
      PgDBI.pgupdt("dscheck", record, "cindex = {}".format(pgrec['cindex']), PgLOG.LGEREX)

#
# call main() to start program
#
if __name__ == "__main__": main()
