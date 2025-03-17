#!/usr/bin/env python3
#
##################################################################################
#
#     Title: rdals
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/20/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: list files/directories in a local directory and show additional
#            information recorded in RDADB if any
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################
#
import re
import os
import sys
import glob
from os import path as op
from rda_python_common import PgLOG
from rda_python_common import PgDBI
from rda_python_common import PgUtil
from rda_python_common import PgSplit

# define some constants for rdals actions
DIDX = 3   # description column index
CLMT = 500   # reformat list if count reach this limit
WIDTHS = [0, 0, 0]   # WIDTHS for formated display
ALIGNS = [0, 1, 1]   # alignment, 0 - left; 1 - right

RDALS = {
   'd' : 0,     # 1 to list directory information only
   'f' : 0,     # 1 to list file information only
   'N' : 0,     # 1 to list files unformatted
   'r' : 0,     # 1 if recursive all
   'R' : 0,     # > 0 to set recursive limit
   'D' : None,  # specify delimiting symbols, default to '  '
}

LINFO = {
   'files' : [],
   'curdir' : None,
   'tpath' : None,
   'dhome' : None,
   'dsid' : None,
   'dcnt' : 0,
   'gcnt' : 0,
   'fcnt' : 0,
   'pcnt' : 0,
   'pgrecs' : []
}

#
# main function to run the application
#
def main():

   PgDBI.view_dbinfo()
   PgLOG.set_help_path(__file__)
   PgLOG.PGLOG['LOGFILE'] = "rdals.log"   # set different log file
   LINFO['curdir'] = get_real_path(os.getcwd())
   argv = sys.argv[1:]
   PgLOG.pglog("rdals {} ({})".format(' '.join(argv), LINFO['curdir']))
   option = defopt = 'l'
   for arg in argv:
      if re.match(r'-(h|-*help|\?)$', arg): PgLOG.show_usage("rdals")
      ms = re.match(r'-(\w)$', arg)
      if ms:
         option = ms.group(1)
         if option not in RDALS: PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
         if 'dfNr'.find(option) > -1:
            RDALS[option] = 1
            option = defopt
         continue
      if not option: PgLOG.pglog(arg + ": Value provided without option", PgLOG.LGEREX)
      if option == 'l':
         LINFO['files'].append(get_real_path(arg))
         defopt = None
      else:
         if option == 'R':
            RDALS[option] = int(arg)
         else:
            RDALS[option] = arg
         option = defopt
   
   if not LINFO['files']:
      LINFO['files'] = sorted(glob.glob('*'))   # view all files in current directory
      if not LINFO['files']:
         sys.stderr.write(LINFO['curdir'] + ": Empty directory\n")
         PgLOG.pgexit(1)

   if not (RDALS['d'] or RDALS['f']):
      RDALS['d'] = RDALS['f'] = 1   # list both directories and files as default
   if not RDALS['D']: RDALS['D'] = '|' if RDALS['N'] else "  "    # default delimiter for no format display
   if not RDALS['R'] and RDALS['r']: RDALS['R'] = 1000

   display_top_list(LINFO['files'])   # display or cache file/directory list
   if LINFO['pcnt'] > 0: display_format_list()   # if some left over

   if (LINFO['dcnt'] + LINFO['gcnt'] + LINFO['fcnt']) > 1:
      msg = ''
      if LINFO['dcnt'] > 0:
         s = 's' if LINFO['dcnt'] > 1 else ''
         msg += "{} Dataset{}".format(LINFO['dcnt'], s)
      if LINFO['gcnt'] > 0:
         s = 's' if LINFO['gcnt'] > 1 else ''
         if msg: msg += " & "
         msg += "{} Group{}".format(LINFO['gcnt'], s)
      if LINFO['fcnt'] > 0:
         s = 's' if LINFO['fcnt'] > 1 else ''
         if msg: msg += " & "
         msg += "{} File{}".format(LINFO['fcnt'], s)
      print("Total {} displayed".format(msg))
   elif (LINFO['dcnt'] + LINFO['gcnt'] + LINFO['fcnt']) == 0:
      sys.stderr.write((LINFO['tpath'] if LINFO['tpath'] else LINFO['curdir']) + ": No RDA data information found\n")
      PgLOG.pgexit(1)
   
   PgLOG.pgexit(0)

#
# display the top level list
#
def display_top_list(files):

   for file in files:

      if not op.exists(file):
         sys.stderr.write(file + ": NOT exists\n")
         continue

      isdir = 1 if op.isdir(file) else 0
      display = 1
      if isdir and re.search(r'/$', file):
         display = 0   # do not display the directory info if it is ended by '/'
         file = re.sub(r'/$', '', file)

      if not re.match(r'^/', file): file = PgLOG.join_paths(LINFO['curdir'], file)
      LINFO['tpath'] = (op.dirname(file) if display else file) + "/"
      if display: display_line(file, isdir)
      if isdir and (RDALS['R'] or not display or not LINFO['dsid']):
         fs = sorted(glob.glob(file + "/*"))
         display_list(fs, 1)
         if LINFO['pcnt'] > CLMT: display_format_list()

#
# recursively display directory/file info
#
def display_list(files, level):

   for file in files:
      isdir = 1 if op.isdir(file) else 0
      display_line(file, isdir)
      if isdir and level < RDALS['R']:
         fs = sorted(glob.glob(file + "/*"))
         display_list(fs, level+1)
         if LINFO['pcnt'] > CLMT: display_format_list()

#
# find dataset/group info; display or cache file
#
def display_line(file, isdir):
   
   getwfile = 1
   if LINFO['dsid'] and LINFO['dhome']:
      ms = re.match(r'^{}/(.*)$'.format(LINFO['dhome']), file)
      if ms:
         wfile = ms.group(1)
         getwfile = 0
   if getwfile:
      LINFO['dsid'] = PgUtil.find_dataset_id(file, logact = PgLOG.LOGWRN)
      if LINFO['dsid'] == None: return     # skip for missing dsid

      pgrec = PgDBI.pgget("dataset", "title, (dwebcnt + nwebcnt) nc, (dweb_size + nweb_size) ns", "dsid = '{}'".format(LINFO['dsid']), PgLOG.LGEREX)
      if not pgrec: return None

      LINFO['dhome'] = "{}/{}".format(PgLOG.PGLOG['DSDHOME'], LINFO['dsid'])
      if LINFO['dhome'] == file:
         file = re.sub(r'^{}'.format(LINFO['tpath']), '', file, 1)
         if RDALS['d']:
            title = pgrec['title'] if pgrec['title'] else ''
            display_record(["D" + file, pgrec['ns'], str(pgrec['nc']), title])
         LINFO['dcnt'] += 1
         return

      ms = re.match(r'^{}/(.*)$'.format(LINFO['dhome']), file)
      if ms:
         wfile = ms.group(1)
      else:
         return

   if isdir:
      if RDALS['d']:   # check and display group info for directory
         pgrec = PgDBI.pgget("dsgroup", "title, (dwebcnt + nwebcnt) nc, (dweb_size + nweb_size) ns",
                             "dsid = '{}' AND webpath = '{}'".format(LINFO['dsid'], wfile), PgLOG.LGEREX)
         if pgrec:
            file = re.sub(r'^{}'.format(LINFO['tpath']), '', file, 1)
            title = pgrec['title'] if pgrec['title'] else ''
            display_record(["G" + file, pgrec['ns'], str(pgrec['nc']), title])
            LINFO['gcnt'] += 1

   elif RDALS['f']:   # check and display file info
      pgrec = PgSplit.pgget_wfile(LINFO['dsid'], "data_size, data_format, note",
                          "wfile = '{}'".format(wfile), PgLOG.LGEREX)
      if pgrec:
         if pgrec['note']:
            note = re.sub(r'\n', ' ', pgrec['note'])   # remove '\n' in note
         else:
            note = ''
         file = re.sub(r'^{}'.format(LINFO['tpath']), '', file, 1)
         display_record(["F" + file, pgrec['data_size'], pgrec['data_format'], note])
         LINFO['fcnt'] += 1

#
# display one file info
#
def display_record(disp):

   disp[1] = get_float_string(disp[1])
   if RDALS['N']:
      print(RDALS['D'].join(disp))
   else:
      LINFO['pgrecs'].append(disp)
      LINFO['pcnt'] += 1
      for i in range(DIDX):
         dlen = len(disp[i])
         if dlen > WIDTHS[i]: WIDTHS[i] = dlen

#
# display cached list with format
#
def display_format_list():

   for j in range(LINFO['pcnt']):
      disp = LINFO['pgrecs'][j]
      for i in range(DIDX):
         if ALIGNS[i] == 1:
            disp[i] = "{:>{}}".format(disp[i], WIDTHS[i])
         else:
            disp[i] = "{:{}}".format(disp[i], WIDTHS[i])
      print(RDALS['D'].join(disp))

   LINFO['pcnt'] = 0

#
# change size to floating point value with unit
#
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

#
# replace /glade to the real path /gpfs
#
def get_real_path(path):

   if re.match(r'^/gpfs/u', path):
      path = re.sub(r'^/gpfs', '/glade', path, 1)
   elif re.match(r'^/gpfs/csfs1/', path):
      path = re.sub(r'^/gpfs/csfs1', '/glade/campaign', path, 1)

   return path

#
# call main() to start program
#
if __name__ == "__main__": main()
