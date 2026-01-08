#!/usr/bin/env python3
##################################################################################
#     Title: rdacp
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: copy files locally and remotely by 'rdadata'
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from os import path as op
from rda_python_common.pg_file import PgFile

class RdaCp(PgFile):

   def __init__(self):
      super().__init__()
      self.RDACP = {
         'fh': None,   # from host name, default to localhost
         'th': None,   # to host name, defaul to localhost
         'fb': None,   # from bucket name for a from file in Object Store
         'tb': None,   # to bucket name for a to file in Object Store
         'fp': None,   # from Globus endpoint
         'tp': None,   # to Globus endpoint
         'f': [],      # from file names
         't': None,    # to file name
         'r': 0,       # 1 if recursive all
         'R': 0,       # > 0 to set recursive limit
         'F': 0o664,   # to file mode, default to 664
         'D': 0o775,   # to directory mode, default to 775
      }
      self.CINFO = {
         'tcnt': 0,
         'htcnt': 0,
         'cpflag': 0,    # 1 file only, 2 directory only, 3 both
         'cpstr': ['', 'Files', 'Directories', 'Files/Directories'],
         'fpath': None,
         'tpath': None,
         'fhost': '',
         'thost': '',
         'curdir': os.getcwd()
      }

   # function to read parameters
   def read_parameters(self):
      dohelp = 0
      argv = sys.argv[1:]
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "rdacp.log"   # set different log file
      self.cmdlog("rdacp {} ({})".format(' '.join(argv), self.CINFO['curdir']))
      defopt = option = 'f'
      for arg in argv:
         if re.match(r'-(h|-help)$', arg, re.I):
            dohelp = 1
            continue
         ms = re.match(r'-(\w+)$', arg)
         if ms:
            option = ms.group(1)
            if option not in self.RDACP: self.pglog(arg + ": Unknown Option", self.LGEREX)
            if option == 'r':
               self.RDACP['r'] = 1
               option = None
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option == "f":
            self.RDACP['f'].append(arg)
            defopt = None
         else:
            if option == 'R':
               self.RDACP[option] = int(arg)
            elif 'FD'.find(option) > -1:
               self.RDACP[option] = self.base2int(arg, 8)
            else:
               self.RDACP[option] = arg
               if option == 'th':
                  self.CINFO['thost'] = arg + '-'
               elif option == 'fh':
                  self.CINFO['fhost'] = arg + '-'
            option = defopt
      if dohelp or not self.RDACP['f']: self.show_usage("rdacp")
   
   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      self.validate_decs_group('rdacp', self.PGLOG['CURUID'], 1)
      if not self.RDACP['R'] and self.RDACP['r']: self.RDACP['R'] = 1000
      if not self.RDACP['t']:
         self.CINFO['tpath'] = self.RDACP['t'] = "."
      else:
         ms = re.match(r'^(.+)/$', self.RDACP['t'])
         if ms:
            self.CINFO['tpath'] = ms.group(1)
         else:
            tinfo = self.check_gdex_file(self.RDACP['t'], self.RDACP['th'], 0, self.LGWNEX)
            if tinfo and tinfo['isfile'] == 0: self.CINFO['tpath'] = self.RDACP['t']
      self.PGLOG['FILEMODE'] = self.RDACP['F']
      self.PGLOG['EXECMODE'] = self.RDACP['D']
      fcnt = len(self.RDACP['f'])
      if not self.CINFO['tpath'] and fcnt > 1:
         self.pglog("{}{}: Cannot copy multiple files to a single file".format(self.CINFO['thost'], self.RDACP['t']), self.LGEREX)
      if self.RDACP['th'] and self.RDACP['fh'] and self.RDACP['th'] == self.RDACP['fh'] and self.RDACP['fh'] != 'HPSS':
         self.pglog(self.RDACP['fh'] + ": Cannot copy file onto the same host", self.LGEREX)
      if self.RDACP['fb']:
         self.PGLOG['OBJCTBKT'] = self.RDACP['fb']
      elif self.RDACP['tb']:
         self.PGLOG['OBJCTBKT'] = self.RDACP['tb']
      if self.RDACP['fp']:
         self.PGLOG['BACKUPEP'] = self.RDACP['fp']
      elif self.RDACP['tp']:
         self.PGLOG['BACKUPEP'] = self.RDACP['tp']
      self.copy_top_list(self.RDACP['f'])
      hinfo = ''
      if self.RDACP['fh']: hinfo += " From " + self.RDACP['fh']
      if self.RDACP['th']: hinfo += " To " + self.RDACP['th']
      if self.CINFO['tcnt'] > 1:
         self.pglog("Total {} {} copiled{}".format(self.CINFO['tcnt'], self.CINFO['cpstr'][self.CINFO['cpflag']], hinfo), self.LOGWRN)
      elif self.CINFO['tcnt'] == 0 and not self.RDACP['fh']:
         self.pglog("{}: No File copied{}".format((self.CINFO['fpath'] if self.CINFO['fpath'] else self.CINFO['curdir']), hinfo), self.LOGWRN)
      self.cmdlog()
   
   # display the top level list
   def copy_top_list(self, files):
      for file in files:
         if self.RDACP['th'] and not self.pgcmp(self.RDACP['th'], self.PGLOG['BACKUPNM'], 1):
            info = self.check_globus_file(file, 'gdex-glade', 0, self.LGWNEX)
         else:
            info = self.check_gdex_file(file, self.RDACP['fh'], 0, self.LGWNEX)
         if not info:
            self.pglog("{}{}: {}".format(self.CINFO['fhost'], file, self.PGLOG['MISSFILE']), self.LOGERR)
            continue
         dosub = 0
         if info['isfile'] == 0:
            self.CINFO['cpflag'] |= 2
            if not self.CINFO['tpath']:
               self.pglog("{}{}: Cannot copy directory to a single file".format(self.CINFO['fhost'], file), self.LGEREX)
            if re.search(r'/$', file):
               dosub = 1   # copy the file under this directory if it is ended by '/'
               file = re.sub(r'/$', '', file)
         else:
            self.CINFO['cpflag'] |= 1
         if not re.match(r'^/', file): file = self.join_paths(self.CINFO['curdir'], file)
         self.CINFO['fpath'] = (file if dosub else op.dirname(file)) + "/"
         if info['isfile']:
            self.CINFO['tcnt'] += self.copy_file(file, info['isfile'])
         elif dosub or self.RDACP['R']:
            flist = self.gdex_glob(file, self.RDACP['fh'], 0, self.LGWNEX)
            if flist: self.copy_list(flist, 1, file)
         else:
            self.pglog("{}{}: Add option -r to copy directory".format(self.CINFO['fhost'], file), self.LGEREX)
   
   # recursively copy directory/file
   def copy_list(self, tlist, level, cdir):
      fcnt = 0
      for file in tlist:
         if tlist[file]['isfile']:
            fcnt += self.copy_file(file, tlist[file]['isfile'])
            self.CINFO['cpflag'] |= (1 if tlist[file]['isfile'] else 2)
         elif level < self.RDACP['R']:
            flist = self.gdex_glob(file, self.RDACP['fh'], 0, self.LGWNEX)
            if flist: self.copy_list(flist, level+1, file)
      if fcnt > 1:   # display sub count if two or more files are copied
         self.pglog("{}{}: {} {} copied from directory".format(self.CINFO['fhost'], cdir, fcnt, self.CINFO['cpstr'][self.CINFO['cpflag']]), self.LOGWRN)
      self.CINFO['tcnt'] += fcnt
   
   # copy one file each time
   def copy_file(self, fromfile, isfile):
      if self.CINFO['tpath']:
         fname = re.sub(r'^{}'.format(self.CINFO['fpath']), '', fromfile)
         if isfile:
            tofile = self.join_paths(self.CINFO['tpath'], fname)
         else:
            tofile = self.CINFO['tpath'] + '/'
      else:
         tofile = self.RDACP['t']
      return (1 if self.copy_gdex_file(tofile, fromfile, self.RDACP['th'], self.RDACP['fh'], self.LGWNEX) else 0)

# main function to excecute this script
def main():
   object = RdaCp()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()

