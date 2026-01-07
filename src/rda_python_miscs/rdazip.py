#!/usr/bin/env python3
##################################################################################
#     Title: rdazip
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-17 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: compress/uncompress given file names
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################

import re
import os
import sys
from rda_python_common.pg_file import PgFile

class RdaZip(PgFile):

   def __init__(self):
      super().__init__()
      self.action = 0
      self.format = None
      self.files = []

   # function to read parameters
   def read_parameters(self):
      argv = sys.argv[1:]
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "rdazip.log"   # set different log file
      self.cmdlog("rdazip {}".format(' '.join(argv)))
      option = None
      for arg in argv:
         ms = re.match(r'-(\w+)$', arg)
         if ms:
            option = ms.group(1)
            if option == "b":
               self.PGLOG['BCKGRND'] = 1
               option = None
            elif option == "f":
               self.action = 1
            else:
               self.pglog(arg + ": Unknown Option", self.LGEREX)
         elif option:
            if self.format: self.pglog("{}: compression format '{}' provided already".format(arg, self.format), self.LGEREX)
            self.format = arg
            if not self.files: option = None
         else:
            if not os.path.isfile(arg): self.pglog(arg + ": file not exists", self.LGEREX)
            self.files.append(arg)
      if not self.files: self.show_usage("rdazip")

   # function to start actions
   def start_actions(self):
      for file in self.files:
         self.compress_local_file(file, self.format, self.action, self.LGWNEX)
      self.cmdlog()

# main function to excecute this script
def main():
   object = RdaZip()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
