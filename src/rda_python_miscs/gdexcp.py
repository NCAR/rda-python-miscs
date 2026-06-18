#!/usr/bin/env python3
##################################################################################
#     Title: gdexcp
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/24/2020
#            2025-03-10 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: copy files locally and remotely by 'gdexdata'
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from os import path as op
from rda_python_common.pg_file import PgFile

class GdexCp(PgFile):
   """Copy files and directories locally or between remote hosts via 'gdexdata'.

   Supports local-to-local, local-to-remote, remote-to-local, and Object Store /
   Globus transfers.  Target files are owned by 'gdexdata' and created with
   configurable permission modes.  Recursive copying is controlled by -r / -R.
   """

   def __init__(self):
      """Initialize GdexCp with default copy options and runtime state."""
      super().__init__()
      self.RDACP = {
         'fh': None,   # from host name, default to localhost
         'th': None,   # to host name, default to localhost
         'fb': None,   # from bucket name for a from file in Object Store
         'tb': None,   # to bucket name for a to file in Object Store
         'fp': None,   # from Globus endpoint
         'tp': None,   # to Globus endpoint
         'f': [],      # from file names
         't': None,    # to file name
         'r': 0,       # 1 if recursive all
         'R': 0,       # > 0 to set recursive limit
         'o': 0,       # 1 to force a downloaded file owned by COMMONUSER; needs -fp
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
      """Parse command-line arguments into RDACP options and validate inputs.

      The default option is -f (source paths); positional arguments before any
      explicit option flag are treated as source paths.  -r is a boolean flag;
      -R and -F/-D take integer values.  Displays usage and exits if -h is given
      or no source files are specified.
      """
      dohelp = 0
      argv = sys.argv[1:]
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "gdexcp.log"   # set different log file
      self.cmdlog("gdexcp {} ({})".format(' '.join(argv), self.CINFO['curdir']))
      defopt = option = 'f'
      for arg in argv:
         if re.match(r'-(h|-help)$', arg, re.I):
            dohelp = 1
            continue
         ms = re.match(r'-(\w+)$', arg)
         if ms:
            option = ms.group(1)
            if option not in self.RDACP: self.pglog(arg + ": Unknown Option", self.LGEREX)
            if option in ('r', 'o'):
               self.RDACP[option] = 1
               option = None
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option == "f":
            self.RDACP['f'].append(arg)
            defopt = None
         else:
            if option == 'R':
               self.RDACP[option] = int(arg)
            elif option in 'FD':
               self.RDACP[option] = self.base2int(arg, 8)
            else:
               self.RDACP[option] = arg
               if option == 'th':
                  self.CINFO['thost'] = arg + '-'
               elif option == 'fh':
                  self.CINFO['fhost'] = arg + '-'
            option = defopt
      if dohelp or not self.RDACP['f']: self.show_usage("gdexcp")
   
   # function to start actions
   def start_actions(self):
      """Validate copy targets, configure host/bucket/endpoint context, and dispatch copies.

      Resolves the target path, sets file and directory permission modes, checks
      for invalid same-host copies, activates Object Store bucket or Globus endpoint
      when specified, then calls copy_top_list.  Logs a summary count on completion.
      """
      self.dssdb_dbname()
      self.validate_decs_group('gdexcp', self.PGLOG['CURUID'], 1)
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
      if self.RDACP['o']:
         if not self.RDACP['fp']:
            self.pglog("-o: works only when source Globus endpoint -fp is provided", self.LGEREX)
         if self.RDACP['th'] or self.RDACP['tp'] or self.RDACP['tb']:
            self.pglog("-o: works only for downloading to local files (no -th/-tp/-tb)", self.LGEREX)
      self.copy_top_list(self.RDACP['f'])
      hinfo = ''
      if self.RDACP['fh']: hinfo += " From " + self.RDACP['fh']
      if self.RDACP['th']: hinfo += " To " + self.RDACP['th']
      if self.CINFO['tcnt'] > 1:
         self.pglog("Total {} {} copied{}".format(self.CINFO['tcnt'], self.CINFO['cpstr'][self.CINFO['cpflag']], hinfo), self.LOGWRN)
      elif self.CINFO['tcnt'] == 0 and not self.RDACP['fh']:
         self.pglog("{}: No File copied{}".format((self.CINFO['fpath'] if self.CINFO['fpath'] else self.CINFO['curdir']), hinfo), self.LOGWRN)
      self.cmdlog()
   
   # copy the top level list
   def copy_top_list(self, files):
      """Iterate the top-level source paths and initiate copies or recursive traversal.

      For each source path, checks existence via the appropriate method (Globus or
      GDEX).  A directory path ending with '/' copies its contents rather than the
      directory entry itself.  Directories without -r/-R cause an error unless the
      trailing '/' form is used.

      Args:
         files (list[str]): Source paths from the -f option.
      """
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
      """Recursively copy a directory listing up to the configured depth limit.

      Logs a sub-count message when two or more files are copied from a single
      directory.  Accumulates the total copy count in CINFO['tcnt'].

      Args:
         tlist (dict): Mapping of path → file-info dict from gdex_glob.
         level (int): Current recursion depth (1-based); stops when >= RDACP['R'].
         cdir (str): Path of the current directory being processed (for log messages).
      """
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
   
   # copy one file
   def copy_file(self, fromfile, isfile):
      """Resolve the destination path for one source file and perform the copy.

      When a target directory is set (tpath), strips the source base path prefix
      and joins the remainder to tpath.  Otherwise copies directly to the -t value.

      Args:
         fromfile (str): Absolute source file path.
         isfile (int): Non-zero when the source is a regular file (vs. a symlink type).

      Returns:
         int: 1 if the file was copied successfully, 0 otherwise.
      """
      if self.CINFO['tpath']:
         fname = re.sub(r'^{}'.format(self.CINFO['fpath']), '', fromfile)
         if isfile:
            tofile = self.join_paths(self.CINFO['tpath'], fname)
         else:
            tofile = self.CINFO['tpath'] + '/'
      else:
         tofile = self.RDACP['t']
      if self.RDACP['o']: return self.force_owner_copy(tofile, fromfile)
      return (1 if self.copy_gdex_file(tofile, fromfile, self.RDACP['th'], self.RDACP['fh'], self.LGWNEX) else 0)

   # copy one file from a Globus endpoint and force COMMONUSER ownership
   def force_owner_copy(self, tofile, fromfile):
      """Download a Globus file via a tmp file so the final copy is owned by COMMONUSER.

      A Globus endpoint dumps the local file owned by the endpoint's mapped user
      rather than COMMONUSER ('gdexdata').  This downloads to a tmp file under
      PGLOG['TMPPATH'], makes it group readable/writable as its owner via the
      pgstart_<user> setuid wrapper, then copies it locally so the final file is
      owned by COMMONUSER, and removes the tmp file.

      Args:
         tofile (str): Final local destination path.
         fromfile (str): Source file path on the Globus endpoint.

      Returns:
         int: 1 if the file was copied successfully, 0 otherwise.
      """
      tmpfile = self.join_paths(self.PGLOG['TMPPATH'], "{}.{}".format(op.basename(fromfile), os.getpid()))
      if not self.copy_gdex_file(tmpfile, fromfile, self.RDACP['th'], self.RDACP['fh'], self.LGWNEX): return 0
      finfo = self.check_local_file(tmpfile, 2, self.LGWNEX)
      owner = finfo['logname'] if finfo else None
      if owner and owner != self.PGLOG['COMMONUSER']:
         self.pgsystem(self.get_local_command("chmod g+rw " + tmpfile, owner), self.LGWNEX)
      ret = self.copy_gdex_file(tofile, tmpfile, self.RDACP['th'], None, self.LGWNEX)
      self.delete_local_file(tmpfile, self.LGWNEX)
      return (1 if ret else 0)

# main function to execute this script
def main():
   """Entry point: instantiate GdexCp, parse arguments, run, and exit."""
   from rda_python_setuid.setup_guide import show_setup_guide
   object = GdexCp()
   show_setup_guide(object, 'rda_python_miscs', ['gdexcp', 'gdexkill', 'gdexmod'])
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()

