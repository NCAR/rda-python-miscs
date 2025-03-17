#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdasub
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 03/51/2021
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: python script to submit a nohup bachground execution
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################

import os
import sys
import re
import time
from rda_python_common import PgLOG
from rda_python_common import PgFile
from rda_python_common import PgUtil

#
# main function to excecute this script
#
def main():

   aname = 'rdasub'
   PgLOG.set_help_path(__file__)
   coptions = {'cmd' : None, 'cwd' : None, 'env' : None}       # customized options
   copts = '|'.join(coptions)
   option = None
   argv = sys.argv[1:]
   if not argv: PgLOG.show_usage(aname)
   PgLOG.PGLOG['LOGFILE'] = aname + ".log"
   PgLOG.cmdlog("{} {}".format(aname, ' '.join(argv)))

   while argv:
      arg = argv.pop(0)
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
         option = None
         continue
      ms = re.match(r'^-({})$'.format(copts), arg)
      if ms:
         option = ms.group(1)
         continue
      if not option: PgLOG.pglog("{}: Value passed in without leading option for {}".format(arg, aname), PgLOG.LGEREX)
      if arg.find(' ') > -1 and not re.match(r'^[\'\"].*[\'\"]$', arg):   # quote string with space but not quoted yet
         if arg.find("'") > -1:
            arg = '"{}"'.format(arg)
         else:
            arg = "'{}'".format(arg)

      coptions[option] = arg
      if option == "cmd": break
      option = None

   if not coptions['cmd']: PgLOG.pglog(aname + ": specify command via option -cmd to run", PgLOG.LGWNEX)
   args = PgLOG.argv_to_string(argv, 0)   # append command options
   msg = "{}-{}{}".format(PgLOG.PGLOG['HOSTNAME'], PgLOG.PGLOG['CURUID'], PgLOG.current_datetime())
   if coptions['cwd']:
      if coptions['cwd'].find('$'): coptions['cwd'] = PgLOG.replace_environments(coptions['cwd'], '', PgLOG.LGWNEX)
      msg += "-" + coptions['cwd']
      PgFile.change_local_directory(coptions['cwd'], PgLOG.LGEREX)
   else:
      coptions['cwd'] = PgLOG.PGLOG['CURDIR']
   cmd = PgLOG.valid_command(coptions['cmd'])
   if not cmd and not re.match(r'^/', coptions['cmd']): cmd = PgLOG.valid_command('./' + coptions['cmd'])
   if not cmd: PgLOG.pglog(coptions['cmd'] + ": Cannot find given command to run", PgLOG.LGWNEX)
   if args: cmd += " " + args

   msg += ": " + cmd
   PgLOG.pglog(msg, PgLOG.LOGWRN)
   os.system("nohup " + cmd + " > /dev/null 2>&1 &")
   display_process_info(coptions['cmd'], cmd)

   sys.exit(0)

#
# display the the most recent matching process info
#
def display_process_info(cname, cmd):

   ctime = time.time()
   RTIME = PID = 0
   pscmd = "ps -u {},{} -f | grep {} | grep ' 1 ' | grep -v ' grep '".format(PgLOG.PGLOG['CURUID'], PgLOG.PGLOG['RDAUSER'], cname)

   for i in range(2):
      buf = PgLOG.pgsystem(pscmd, PgLOG.LOGWRN, 20)
      if buf:
         lines = buf.split("\n")
         for line in lines:
            mp = "\s+(\d+)\s+1\s+.*\s(\d+:\d+)\s.*{}\S*\s*(.*)$".format(cname)
            ms = re.search(mp, line)
            if ms:
               pid = ms.group(1)
               rtm = ms.group(2)
               arg = ms.group(3)
               if not arg or cmd.find(arg) > -1:
                  rtime = PgUtil.unixtime(rtm + ':00')
                  if rtime > ctime: rtime -= 24*60*60
                  if rtime > RTIME:
                     PID = pid
                     RTIME = rtime
      if PID:
         return PgLOG.pglog("Job <{}> is submitted to background <{}>".format(PID, PgLOG.PgLOG['HOSTNAME']), PgLOG.LOGWRN)
      elif i == 0:
         time.sleep(2)
      else:
         return PgLOG.pglog("{}: No job information found, It may have finished".format(cmd), PgLOG.LOGWRN)

#
# call main() to start program
#
if __name__ == "__main__": main()
