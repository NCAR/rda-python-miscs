#!/usr/bin/env python3
##################################################################################
#     Title: rdasub
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 03/51/2021
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: python script to submit a nohup bachground execution
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################

import os
import sys
import re
import time
from rda_python_common.pg_file import PgFile

class RdaSub(PgFile):

   def __init__(self):
      super().__init__()
      self.coptions = {'cmd': None, 'cwd': None, 'env': None}       # customized options
      self.args = None

   # function to read parameters
   def read_parameters(self):
      aname = 'rdasub'
      self.set_help_path(__file__)
      copts = '|'.join(self.coptions)
      option = None
      argv = sys.argv[1:]
      if not argv: self.show_usage(aname)
      self.PGLOG['LOGFILE'] = aname + ".log"
      self.cmdlog("{} {}".format(aname, ' '.join(argv)))
      while argv:
         arg = argv.pop(0)
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
            option = None
            continue
         ms = re.match(r'^-({})$'.format(copts), arg)
         if ms:
            option = ms.group(1)
            continue
         if not option: self.pglog("{}: Value passed in without leading option for {}".format(arg, aname), self.LGEREX)
         if arg.find(' ') > -1 and not re.match(r'^[\'\"].*[\'\"]$', arg):   # quote string with space but not quoted yet
            if arg.find("'") > -1:
               arg = '"{}"'.format(arg)
            else:
               arg = "'{}'".format(arg)
         self.coptions[option] = arg
         if option == "cmd": break
         option = None
      if not self.coptions['cmd']: self.pglog(aname + ": specify command via option -cmd to run", self.LGWNEX)
      self.args = self.argv_to_string(argv, 0)   # append command options

   # function to start actions
   def start_actions(self):
      msg = "{}-{}{}".format(self.PGLOG['HOSTNAME'], self.PGLOG['CURUID'], self.current_datetime())
      if self.coptions['cwd']:
         if self.coptions['cwd'].find('$'): self.coptions['cwd'] = self.replace_environments(self.coptions['cwd'], '', self.LGWNEX)
         msg += "-" + self.coptions['cwd']
         self.change_local_directory(self.coptions['cwd'], self.LGEREX)
      else:
         self.coptions['cwd'] = self.PGLOG['CURDIR']
      cmd = self.valid_command(self.coptions['cmd'])
      if not cmd and not re.match(r'^/', self.coptions['cmd']): cmd = self.valid_command('./' + self.coptions['cmd'])
      if not cmd: self.pglog(self.coptions['cmd'] + ": Cannot find given command to run", self.LGWNEX)
      if self.args: cmd += " " + self.args
      msg += ": " + cmd
      self.pglog(msg, self.LOGWRN)
      os.system("nohup " + cmd + " > /dev/null 2>&1 &")
      self.display_process_info(self.coptions['cmd'], cmd)

   # display the the most recent matching process info
   def display_process_info(self, cname, cmd):
      ctime = time.time()
      RTIME = PID = 0
      pscmd = "ps -u {},{} -f | grep {} | grep ' 1 ' | grep -v ' grep '".format(self.PGLOG['CURUID'], self.PGLOG['RDAUSER'], cname)
      for i in range(2):
         buf = self.pgsystem(pscmd, self.LOGWRN, 20)
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
                     rtime = self.unixtime(rtm + ':00')
                     if rtime > ctime: rtime -= 24*60*60
                     if rtime > RTIME:
                        PID = pid
                        RTIME = rtime
         if PID:
            return self.pglog("Job <{}> is submitted to background <{}>".format(PID, self.PgLOG['HOSTNAME']), self.LOGWRN)
         elif i == 0:
            time.sleep(2)
         else:
            return self.pglog("{}: No job information found, It may have finished".format(cmd), self.LOGWRN)

# main function to excecute this script
def main():
   object = RdaSub()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
