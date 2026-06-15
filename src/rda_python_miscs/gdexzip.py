#!/usr/bin/env python3
##################################################################################
#     Title: gdexzip
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

class GdexZip(PgFile):
   """Compress or uncompress files using a supported format (gz, Z, bz2, zip).

   When a target format is specified via -f, files are compressed to that format.
   Without -f, each file is uncompressed based on its current extension.
   Conversion between formats is also supported by combining both in one call.
   """

   def __init__(self):
      """Initialize GdexZip with default action (uncompress), no format, and empty file list."""
      super().__init__()
      self.action = 0      # 0 - uncompress, 1 - compress to self.format
      self.format = None   # target compression format (gz, Z, bz2, zip)
      self.files = []      # list of files to process

   # function to read parameters
   def read_parameters(self):
      """Parse command-line arguments into action, format, and file list.

      -f sets compress mode (action=1) and reads the target format from the
      next argument.  -b enables background execution.  All other non-option
      arguments are treated as files to process; each must exist on disk.
      Displays usage and exits if no files are given.
      """
      argv = sys.argv[1:]
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "gdexzip.log"   # set different log file
      self.cmdlog("gdexzip {}".format(' '.join(argv)))
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
      if not self.files: self.show_usage("gdexzip")

   # function to start actions
   def start_actions(self):
      """Compress or uncompress each file in the list, then close the command log."""
      for file in self.files:
         self.compress_local_file(file, self.format, self.action, self.LGWNEX)
      self.cmdlog()

# main function to execute this script
def main():
   """Entry point: instantiate GdexZip, parse arguments, run, and exit."""
   object = GdexZip()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
