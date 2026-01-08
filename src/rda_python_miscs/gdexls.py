#!/usr/bin/env python3
##################################################################################
#     Title: gdexls
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/20/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#            2025-09-21 copied from rdals to gdexls
#   Purpose: list files/directories in a local directory and show additional
#            information recorded in GDEXDB if any
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
import glob
from os import path as op
from rda_python_common.pg_split import PgSplit

class GdexLs(PgSplit):

   def __init__(self):
      super().__init__()
      # define some constants for gdexls actions
      self.DIDX = 3   # description column index
      self.CLMT = 500   # reformat list if count reach this limit
      self.WIDTHS = [0, 0, 0]   # WIDTHS for formated display
      self.ALIGNS = [0, 1, 1]   # alignment, 0 - left; 1 - right
      self.GDEXLS = {
         'd': 0,     # 1 to list directory information only
         'f': 0,     # 1 to list file information only
         'N': 0,     # 1 to list files unformatted
         'r': 0,     # 1 if recursive all
         'R': 0,     # > 0 to set recursive limit
         'D': None,  # specify delimiting symbols, default to '  '
      }
      self.LINFO = {
         'files': [],
         'curdir': None,
         'tpath': None,
         'dhome': None,
         'dsid': None,
         'dcnt': 0,
         'gcnt': 0,
         'fcnt': 0,
         'pcnt': 0,
         'pgrecs': []
      }

   # function to read parameters
   def read_parameters(self):
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "gdexls.log"   # set different log file
      self.LINFO['curdir'] = self.get_real_path(os.getcwd())
      argv = sys.argv[1:]
      self.pglog("gdexls {} ({})".format(' '.join(argv), self.LINFO['curdir']))
      option = defopt = 'l'
      for arg in argv:
         if re.match(r'-(h|-*help|\?)$', arg): self.show_usage("gdexls")
         ms = re.match(r'-(\w)$', arg)
         if ms:
            option = ms.group(1)
            if option not in self.GDEXLS: self.pglog(arg + ": Unknown Option", self.LGEREX)
            if 'dfNr'.find(option) > -1:
               self.GDEXLS[option] = 1
               option = defopt
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option == 'l':
            self.LINFO['files'].append(self.get_real_path(arg))
            defopt = None
         else:
            if option == 'R':
               self.GDEXLS[option] = int(arg)
            else:
               self.GDEXLS[option] = arg
            option = defopt

   # functio to start actions
   def start_actions(self):   
      self.view_dbinfo()
      if not self.LINFO['files']:
         self.LINFO['files'] = sorted(glob.glob('*'))   # view all files in current directory
         if not self.LINFO['files']:
            sys.stderr.write(self.LINFO['curdir'] + ": Empty directory\n")
            self.pgexit(1)
   
      if not (self.GDEXLS['d'] or self.GDEXLS['f']):
         self.GDEXLS['d'] = self.GDEXLS['f'] = 1   # list both directories and files as default
      if not self.GDEXLS['D']: self.GDEXLS['D'] = '|' if self.GDEXLS['N'] else "  "    # default delimiter for no format display
      if not self.GDEXLS['R'] and self.GDEXLS['r']: self.GDEXLS['R'] = 1000
   
      self.display_top_list(self.LINFO['files'])   # display or cache file/directory list
      if self.LINFO['pcnt'] > 0: self.display_format_list()   # if some left over
      if (self.LINFO['dcnt'] + self.LINFO['gcnt'] + self.LINFO['fcnt']) > 1:
         msg = ''
         if self.LINFO['dcnt'] > 0:
            s = 's' if self.LINFO['dcnt'] > 1 else ''
            msg += "{} Dataset{}".format(self.LINFO['dcnt'], s)
         if self.LINFO['gcnt'] > 0:
            s = 's' if self.LINFO['gcnt'] > 1 else ''
            if msg: msg += " & "
            msg += "{} Group{}".format(self.LINFO['gcnt'], s)
         if self.LINFO['fcnt'] > 0:
            s = 's' if self.LINFO['fcnt'] > 1 else ''
            if msg: msg += " & "
            msg += "{} File{}".format(self.LINFO['fcnt'], s)
         print("Total {} displayed".format(msg))
      elif (self.LINFO['dcnt'] + self.LINFO['gcnt'] + self.LINFO['fcnt']) == 0:
         sys.stderr.write((self.LINFO['tpath'] if self.LINFO['tpath'] else self.LINFO['curdir']) + ": No GDEX data information found\n")
         self.pgexit(1)

   # display the top level list
   def display_top_list(self, files):
      for file in files:
         if not op.exists(file):
            sys.stderr.write(file + ": NOT exists\n")
            continue
         isdir = 1 if op.isdir(file) else 0
         display = 1 
         if isdir and re.search(r'/$', file):
            display = 0   # do not display the directory info if it is ended by '/'
            file = re.sub(r'/$', '', file)
         if not re.match(r'^/', file): file = self.join_paths(self.LINFO['curdir'], file)
         self.LINFO['tpath'] = (op.dirname(file) if display else file) + "/"
         if display: self.display_line(file, isdir)
         if isdir and (self.GDEXLS['R'] or not display or not self.LINFO['dsid']):
            fs = sorted(glob.glob(file + "/*"))
            self.display_list(fs, 1)
            if self.LINFO['pcnt'] > self.CLMT: self.display_format_list()

   # recursively display directory/file info
   def display_list(self, files, level):
      for file in files:
         isdir = 1 if op.isdir(file) else 0
         self.display_line(file, isdir)
         if isdir and level < self.GDEXLS['R']:
            fs = sorted(glob.glob(file + "/*"))
            self.display_list(fs, level+1)
            if self.LINFO['pcnt'] > self.CLMT: self.display_format_list()

   # find dataset/group info; display or cache file
   def display_line(self, file, isdir):
      getwfile = 1
      if self.LINFO['dsid'] and self.LINFO['dhome']:
         ms = re.match(r'^{}/(.*)$'.format(self.LINFO['dhome']), file)
         if ms:
            wfile = ms.group(1)
            getwfile = 0
      if getwfile:
         self.LINFO['dsid'] = self.find_dataset_id(file)
         if self.LINFO['dsid'] is None: return     # skip for missing dsid
         pgrec = self.pgget("dataset", "title, (dwebcnt + nwebcnt) nc, (dweb_size + nweb_size) ns", "dsid = '{}'".format(self.LINFO['dsid']), self.LGEREX)
         if not pgrec: return None
         self.LINFO['dhome'] = "{}/{}".format(self.PGLOG['DSDHOME'], self.LINFO['dsid'])
         if self.LINFO['dhome'] == file:
            file = re.sub(r'^{}'.format(self.LINFO['tpath']), '', file, 1)
            if self.GDEXLS['d']:
               title = pgrec['title'] if pgrec['title'] else ''
               self.display_record(["D" + file, pgrec['ns'], str(pgrec['nc']), title])
            self.LINFO['dcnt'] += 1
            return
         ms = re.match(r'^{}/(.*)$'.format(self.LINFO['dhome']), file)
         if ms:
            wfile = ms.group(1)
         else:
            return
      if isdir:
         if self.GDEXLS['d']:   # check and display group info for directory
            pgrec = self.pgget("dsgroup", "title, (dwebcnt + nwebcnt) nc, (dweb_size + nweb_size) ns",
                               "dsid = '{}' AND webpath = '{}'".format(self.LINFO['dsid'], wfile), self.LGEREX)
            if pgrec:
               file = re.sub(r'^{}'.format(self.LINFO['tpath']), '', file, 1)
               title = pgrec['title'] if pgrec['title'] else ''
               self.display_record(["G" + file, pgrec['ns'], str(pgrec['nc']), title])
               self.LINFO['gcnt'] += 1
      elif self.GDEXLS['f']:   # check and display file info
         pgrec = self.pgget_wfile(self.LINFO['dsid'], "data_size, data_format, note",
                                  "wfile = '{}'".format(wfile), self.LGEREX)
         if pgrec:
            note = re.sub(r'\n', ' ', pgrec['note']) if pgrec['note'] else ''
            file = re.sub(r'^{}'.format(self.LINFO['tpath']), '', file, 1)
            self.display_record(["F" + file, pgrec['data_size'], pgrec['data_format'], note])
            self.LINFO['fcnt'] += 1

   # display one file info
   def display_record(self, disp):
      disp[1] = self.get_float_string(disp[1])
      if self.GDEXLS['N']:
         print(self.GDEXLS['D'].join(disp))
      else:
         self.LINFO['pgrecs'].append(disp)
         self.LINFO['pcnt'] += 1
         for i in range(self.DIDX):
            dlen = len(disp[i])
            if dlen > self.WIDTHS[i]: self.WIDTHS[i] = dlen

   # display cached list with format
   def display_format_list(self):
      for j in range(self.LINFO['pcnt']):
         disp = self.LINFO['pgrecs'][j]
         for i in range(self.DIDX):
            if self.ALIGNS[i] == 1:
               disp[i] = "{:>{}}".format(disp[i], self.WIDTHS[i])
            else:
               disp[i] = "{:{}}".format(disp[i], self.WIDTHS[i])
         print(self.GDEXLS['D'].join(disp))
      self.LINFO['pcnt'] = 0

   # change size to floating point value with unit
   @staticmethod
   def get_float_string(val):
      units = ['B', 'K', 'M', 'G', 'T', 'P']
      idx = 0
      while val > 1000 and idx < 5:
         val /= 1000
         idx += 1
      if idx > 0:
         return "{:.2f}{}".format(val, units[idx])
      else:
         return "{}{}".format(val, units[idx])

   # replace /gpfs to the path /glade
   @staticmethod
   def get_real_path(path):
      if re.match(r'^/gpfs/u', path):
         path = re.sub(r'^/gpfs', '/glade', path, 1)
      elif re.match(r'^/gpfs/csfs1/', path):
         path = re.sub(r'^/gpfs/csfs1', '/glade/campaign', path, 1)
      return op.realpath(path)

# main function to excecute this script
def main():
   object = GdexLs()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
