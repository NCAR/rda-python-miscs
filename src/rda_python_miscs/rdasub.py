#!/usr/bin/env python3
##################################################################################
#     Title: rdasub
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 03/31/2021
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: python script to submit a nohup background execution
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################

import os
import sys
import re
import time
from rda_python_common.pg_file import PgFile

class RdaSub(PgFile):
   """Submit a command as a nohup background process on the local machine.

   Wraps the command in 'nohup ... > /dev/null 2>&1 &' and logs the resulting
   PID once the process is detected in 'ps' output.  Supports optional working
   directory and environment variable setup before launch.
   """

   def __init__(self):
      """Initialize RdaSub with empty customized options and argument string."""
      super().__init__()
      self.coptions = {'cmd': None, 'cwd': None, 'env': None}   # cmd: command to run,
                                                                  # cwd: working directory,
                                                                  # env: environment pairs
      self.args = None   # extra arguments to append after the command

   # function to read parameters
   def read_parameters(self):
      """Parse command-line arguments into coptions and trailing command arguments.

      Recognises -cmd, -cwd, -env as long options and -b as a background flag.
      Parsing stops after -cmd's value is consumed; any remaining argv tokens
      are collected as extra arguments for the command.  Exits with usage if no
      arguments are given; errors if -cmd is not provided.  Arguments containing
      spaces are automatically quoted.
      """
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
      """Resolve the command path, change to the working directory if set, and launch.

      Expands environment variables in cwd when a '$' is present.  Resolves the
      command to an absolute path, appends extra arguments, logs a descriptive
      message, runs the command under nohup, then calls display_process_info to
      find and log the resulting PID.
      """
      msg = "{}-{}{}".format(self.PGLOG['HOSTNAME'], self.PGLOG['CURUID'], self.current_datetime())
      if self.coptions['cwd']:
         if '$' in self.coptions['cwd']: self.coptions['cwd'] = self.replace_environments(self.coptions['cwd'], '', self.LGWNEX)
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

   # display the most recent matching process info
   def display_process_info(self, cname, cmd):
      """Poll 'ps' up to twice to find the newly launched process and log its PID.

      Searches for a process whose command matches cname and whose PPID is 1
      (detached via nohup).  Picks the most recently started match by comparing
      start times.  Sleeps 2 seconds between attempts if the first poll finds
      nothing.  Logs the PID on success or a warning if no matching process is
      found.

      Args:
         cname (str): Base command name used to filter ps output.
         cmd (str): Full command string used to verify argument matches.
      """
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
            return self.pglog("Job <{}> is submitted to background <{}>".format(PID, self.PGLOG['HOSTNAME']), self.LOGWRN)
         elif i == 0:
            time.sleep(2)
         else:
            return self.pglog("{}: No job information found, It may have finished".format(cmd), self.LOGWRN)

# main function to execute this script
def main():
   """Entry point: instantiate RdaSub, parse arguments, run, and exit."""
   object = RdaSub()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
