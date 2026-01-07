#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdazip
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-17 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: compress/uncompress given file names
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################

import re
import os
import sys
from rda_python_common import PgLOG
from rda_python_common import PgFile

#
# main function to run the application
#
def main():

   act = 0
   argv = sys.argv[1:]
   PgLOG.set_help_path(__file__)
   PgLOG.PGLOG['LOGFILE'] = "rdazip.log"   # set different log file
   PgLOG.cmdlog("rdazip {}".format(' '.join(argv)))
   files = []
   fmt = option = None
   for arg in argv:
      ms = re.match(r'-(\w+)$', arg)
      if ms:
         option = ms.group(1)
         if option == "b":
            PgLOG.PGLOG['BCKGRND'] = 1
            option = None
         elif option == "f":
            act = 1
         else:
            PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
      elif option:
         if fmt: PgLOG.pglog("{}: compression format '{}' provided already".format(arg, fmt), PgLOG.LGEREX)
         fmt = arg
         if not files: option = None
      else:
         if not os.path.isfile(arg): PgLOG.pglog(arg + ": file not exists", PgLOG.LGEREX)
         files.append(arg)
   
   if not files: PgLOG.show_usage("rdazip")
   
   for file in files:
      PgFile.compress_local_file(file, fmt, act, PgLOG.LGWNEX)

   PgLOG.cmdlog()
   sys.exit(0)

#
# call main() to start program
#
if __name__ == "__main__": main()
