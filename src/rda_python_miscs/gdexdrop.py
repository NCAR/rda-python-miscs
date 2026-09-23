#!/usr/bin/env python3
##################################################################################
#     Title: gdexdrop
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 2026-09-23
#   Purpose: copy local files into a GDEX dataset directory as 'gdexdata', for
#            data providers who are not in the DECS group.  Unlike gdexcp, the
#            destination is confined to <DROPROOT>/<dsid> and the caller must be
#            listed in the gdexdrop access list.
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from os import path as op
from rda_python_common.pg_file import PgFile

# These are hardcoded on purpose.  gdexdrop runs setuid to 'gdexdata' for callers
# who are NOT in the DECS group, so nothing deciding WHERE it writes or WHO may
# write there can come from the caller.  PgLOG.SETPGLOG() fills PGLOG['DSDHOME'],
# PGLOG['DSSHOME'] and PGLOG['LOGPATH'] from environment variables of the same
# names, which the caller controls, so those values are deliberately not used.
DROPROOT = "/glade/campaign/collections/gdex/data"      # dataset data root path
DROPCONF = "/glade/u/home/gdexdata/config/gdexdrop.conf"   # access list
DROPLOG = "/glade/u/home/gdexdata/dssdb/log"            # log path
DROPUSER = "gdexdata"                                   # owner of dropped files
DROPTMP = "/tmp"                                        # alternate root, for testing

class GdexDrop(PgFile):
   """Copy local files and directories into a GDEX dataset directory as 'gdexdata'.

   The destination is always <DROPROOT>/<dsid>, optionally with a sub-path given
   by -t, and is verified to stay inside that dataset directory.  The caller must
   be granted the dataset in the gdexdrop access list, and must be able to read
   every source path as themselves; both checks exist because the copy itself
   runs with the privileges of 'gdexdata'.  Everything dropped is then set to the
   GDEX group PGLOG['GDEXGRP'], which the copy does not land in on its own.
   """

   def __init__(self):
      """Initialize GdexDrop with default drop options and runtime state."""
      super().__init__()
      self.DROP = {
         'ds': None,   # target dataset ID, such as d123456
         'f': [],      # from file/directory names
         'i': None,    # input file holding a list of from file names, one per line
         't': None,    # sub-path under the dataset directory to drop the files into
         'O': 0,       # 1 to override an existing target file of the same size
         'F': 0o664,   # to file mode, default to 664
         'D': 0o775,   # to directory mode, default to 775
      }
      self.DINFO = {
         'tcnt': 0,           # count of files/directories copied
         'target': None,      # resolved target directory
         'curdir': os.getcwd()
      }

   # function to read parameters
   def read_parameters(self):
      """Parse command-line arguments, verify read access, then switch to 'gdexdata'.

      The default option is -f (source paths); positional arguments are treated
      as source paths wherever they appear.  -O is a boolean flag; -F and -D take
      octal modes.  The source access check must run before set_suid(), while the
      real user ID is still the caller, so that os.access() reports what the
      CALLER can read rather than what 'gdexdata' can read.
      """
      dohelp = 0
      argv = sys.argv[1:]
      self.set_help_path(__file__)
      self.PGLOG['LOGPATH'] = DROPLOG
      self.PGLOG['LOGFILE'] = "gdexdrop.log"   # set different log file
      defopt = option = 'f'
      for arg in argv:
         if re.match(r'-(h|-help)$', arg, re.I):
            dohelp = 1
            continue
         ms = re.match(r'-(\w+)$', arg)
         if ms:
            option = ms.group(1)
            if option not in self.DROP: self.pglog(arg + ": Unknown Option", self.LGEREX)
            if option == 'O':
               self.DROP[option] = 1
               option = defopt
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option == 'f':
            self.DROP['f'].append(arg)
         else:
            if option in ('F', 'D'):
               self.DROP[option] = self.base2int(arg, 8)
            else:
               self.DROP[option] = arg
            option = defopt
      if self.DROP['i']: self.add_input_files(self.DROP['i'])
      if dohelp or not self.DROP['ds'] or not self.DROP['f']: self.show_usage("gdexdrop")
      self.check_source_access()
      self.set_suid(self.PGLOG['EUID'])
      self.cmdlog("gdexdrop {} ({})".format(' '.join(argv), self.DINFO['curdir']))

   # read source paths from an input file and append them to the -f list
   def add_input_files(self, infile):
      """Append source paths read from an input file to the -f source list.

      Each non-empty line is treated as one source path; leading/trailing
      whitespace is stripped and lines starting with '#' are ignored.  The file
      must be readable by the caller, not merely by 'gdexdata'.

      Args:
         infile (str): Path to the input file holding one source path per line.
      """
      if not os.access(infile, os.R_OK):
         self.pglog("{}: Input file of -i not readable by {}".format(infile, self.PGLOG['CURUID']), self.LGEREX)
      fd = open(infile, 'r')
      for line in fd:
         line = line.strip()
         if not line or line[0] == '#': continue
         self.DROP['f'].append(line)
      fd.close()

   # make sure the caller can read every source path as themselves
   def check_source_access(self):
      """Verify the calling user can read each source path, exiting if not.

      Must be called while the real user ID is still the caller, i.e. before
      set_suid().  Without this check a caller could name a path readable only by
      'gdexdata', have it copied into a dataset directory they can read, and so
      read it indirectly.
      """
      for file in self.DROP['f']:
         path = re.sub(r'/$', '', file, 1)
         if not re.match(r'^/', path): path = self.join_paths(self.DINFO['curdir'], path)
         if not op.exists(path):
            self.pglog("{}: {}".format(file, self.PGLOG['MISSFILE']), self.LGEREX)
         if not self.caller_can_read(path):
            self.pglog("{}: not readable by {}".format(file, self.PGLOG['CURUID']), self.LGEREX)

   # check read access of one path, and of everything under it for a directory
   def caller_can_read(self, path):
      """Return 1 if the real user can read path and all of its contents.

      os.access() tests the REAL user and group IDs, which is exactly what is
      wanted here while running with an effective ID of 'gdexdata'.

      Args:
         path (str): Absolute source path to check.

      Returns:
         int: 1 if fully readable by the calling user, 0 otherwise.
      """
      if not os.access(path, os.R_OK): return 0
      if op.isfile(path): return 1
      if not os.access(path, os.X_OK): return 0
      for root, dirs, files in os.walk(path):
         for name in dirs:
            if not os.access(op.join(root, name), os.R_OK|os.X_OK): return 0
         for name in files:
            if not os.access(op.join(root, name), os.R_OK): return 0
      return 1

   # function to start actions
   def start_actions(self):
      """Resolve and authorize the target dataset directory, then copy the sources.

      Logs a summary count on completion.
      """
      self.DINFO['target'] = self.resolve_target()
      self.validate_caller()
      if not self.PGLOG['GDEXGID']:
         self.pglog(self.PGLOG['GDEXGRP'] + ": Unknown Group to own the dropped files", self.LGEREX)
      self.PGLOG['FILEMODE'] = self.DROP['F']
      self.PGLOG['EXECMODE'] = self.DROP['D']
      self.make_target_directory()
      for file in self.DROP['f']:
         self.DINFO['tcnt'] += self.drop_one(file)
      if self.DINFO['tcnt'] > 0:
         s = ('s' if self.DINFO['tcnt'] > 1 else '')
         self.pglog("Total {} File{} dropped into {}".format(self.DINFO['tcnt'], s, self.DINFO['target']), self.LOGWRN)
      else:
         self.pglog("No File dropped into " + self.DINFO['target'], self.LOGWRN)
      self.cmdlog()

   # resolve the target directory and confine it to the dataset directory
   def resolve_target(self):
      """Return the target directory under DROPROOT for -ds, confined to the dataset.

      The resolved real path of the target must equal, or lie under, the resolved
      real path of the dataset directory, so that neither a '..' component in -t
      nor an existing symbolic link can move the drop outside the dataset.

      An absolute -t under DROPTMP names any sub-path of that directory instead,
      for trying a drop out without touching the dataset tree.  The dataset of
      -ds is still validated against the access list.

      Returns:
         str: Resolved absolute target directory.
      """
      dsid = self.DROP['ds']
      if not re.match(r'^[a-z]\d{6}$', dsid):
         self.pglog(dsid + ": Invalid Dataset ID of -ds, expecting the form d123456", self.LGEREX)
      if self.DROP['t'] and re.match(r'^{}/'.format(DROPTMP), self.DROP['t']):
         return self.tmp_target()
      dsroot = op.realpath(op.join(DROPROOT, dsid))
      if not op.isdir(dsroot):
         self.pglog("{}: Dataset directory NOT exists under {}".format(dsid, DROPROOT), self.LGEREX)
      target = self.confine_path(op.join(dsroot, self.DROP['t']) if self.DROP['t'] else dsroot, dsroot)
      return target

   # resolve a target of -t that names a sub-path of DROPTMP
   def tmp_target(self):
      """Return the resolved -t path under DROPTMP, exiting if it may not be used.

      DROPTMP is world writable, unlike a dataset directory, so a path there can
      be replaced by another user between this check and the copy, and may well
      belong to somebody else already.  The existing part of the path is therefore
      required to belong to the caller or to DROPUSER, so that a drop cannot be
      aimed at a directory a third user controls.

      Returns:
         str: Resolved absolute target directory under DROPTMP.
      """
      tmproot = op.realpath(DROPTMP)
      target = self.confine_path(self.DROP['t'], tmproot)
      dir = target
      while not op.isdir(dir): dir = op.dirname(dir)
      if dir == tmproot: return target   # nothing of the path exists yet
      info = self.check_local_file(dir, 2, self.LOGWRN)
      if info and info['logname'] not in (self.PGLOG['CURUID'], DROPUSER):
         self.pglog("{}: Target path under {} is owned by {}".format(dir, DROPTMP, info['logname']), self.LGEREX)
      return target

   # make sure a path stays inside the dataset directory
   def confine_path(self, path, dsroot):
      """Return the resolved path, exiting if it falls outside the dataset directory.

      Args:
         path (str): Candidate absolute path.
         dsroot (str): Resolved absolute dataset directory.

      Returns:
         str: Resolved absolute path inside dsroot.
      """
      rpath = op.realpath(path)
      if rpath != dsroot and not rpath.startswith(dsroot + '/'):
         self.pglog("{}: Target path is outside of {}".format(path, dsroot), self.LGEREX)
      return rpath

   # check the caller is granted the target dataset in the access list
   def validate_caller(self):
      """Exit unless the calling user is granted the target dataset.

      The access list must be owned by 'gdexdata' and must not be writable by
      group or others; otherwise anyone able to edit it could grant themselves
      access to any dataset.  Each line is 'login: dsid1[:...:dsidn]', or
      'login: all' for every dataset; '#' starts a comment.  The check is
      skipped when 'gdexdata' itself runs the command.
      """
      logname = self.PGLOG['CURUID']
      if logname == DROPUSER: return
      info = self.check_local_file(DROPCONF, 6, self.LOGWRN)
      if not info:
         self.pglog(DROPCONF + ": gdexdrop access list NOT exists", self.LGEREX)
      if info['logname'] != DROPUSER:
         self.pglog("{}: access list must be owned by {}, but is owned by {}".format(DROPCONF, DROPUSER, info['logname']), self.LGEREX)
      if info['mode']&0o022:
         self.pglog("{}: access list must not be group or world writable, mode is {:o}".format(DROPCONF, info['mode']), self.LGEREX)
      dsids = {}
      fd = open(DROPCONF, 'r')
      for line in fd:
         line = re.sub(r'#.*$', '', line).strip()
         if not line: continue
         ms = re.match(r'^(\S+)\s*:\s*(.*)$', line)
         if not ms: continue
         if ms.group(1) != logname: continue
         for dsid in ms.group(2).split(':'):
            dsid = dsid.strip()
            if dsid: dsids[dsid] = 1
      fd.close()
      if not ('all' in dsids or self.DROP['ds'] in dsids):
         self.pglog("{}: NOT granted Dataset {} in {}".format(logname, self.DROP['ds'], DROPCONF), self.LGEREX)

   # create the target directory, and set the group of each directory created
   def make_target_directory(self):
      """Create the sub-directories named by -t that do not exist yet.

      They are created here rather than on the fly by local_copy_local() so that
      set_drop_group() can be called on each one; a directory left in the calling
      user's group could not be written into by the rest of the DECS group later.
      """
      newdirs = []
      dir = self.DINFO['target']
      while not op.isdir(dir):
         newdirs.insert(0, dir)
         dir = op.dirname(dir)
      if not newdirs: return
      self.make_local_directory(self.DINFO['target'], self.LGWNEX)
      for dir in newdirs: self.set_drop_group(dir)

   # set the group of a dropped path, and of everything under it for a directory
   def set_drop_group(self, path):
      """Set the group of path, and of all of its contents for a directory.

      The copy runs with an effective user of 'gdexdata' but with the EFFECTIVE
      GROUP of the caller, so a dropped file lands in the caller's group unless
      the directory it lands in happens to carry the setgid bit.  Symbolic links
      are skipped, since os.chown() follows them out of the dataset directory.

      Args:
         path (str): Absolute path of a dropped file or directory.
      """
      if op.islink(path): return
      self.change_local_group(path, None, None, None, self.LOGWRN)
      if not op.isdir(path): return
      for root, dirs, files in os.walk(path):
         for name in dirs + files:
            subpath = op.join(root, name)
            if op.islink(subpath): continue
            self.change_local_group(subpath, None, None, None, self.LOGWRN)

   # copy one source path into the target directory
   def drop_one(self, file):
      """Copy one source file or directory into the target directory.

      A directory is copied recursively, as the directory itself.  An existing
      target file of the same size is left alone unless -O is given.

      Args:
         file (str): Source path as given on the command line.

      Returns:
         int: 1 if the source was copied, 0 otherwise.
      """
      path = re.sub(r'/$', '', file, 1)
      if not re.match(r'^/', path): path = self.join_paths(self.DINFO['curdir'], path)
      finfo = self.check_local_file(path, 0, self.LOGWRN)
      if not finfo:
         return self.pglog("{}: {}".format(file, self.PGLOG['MISSFILE']), self.LOGERR)
      tofile = self.confine_path(op.join(self.DINFO['target'], op.basename(path)), self.DINFO['target'])
      if finfo['isfile'] and not self.DROP['O']:
         tinfo = self.check_local_file(tofile, 0, self.LOGWRN)
         if tinfo and tinfo['data_size'] == finfo['data_size']:
            self.pglog(tofile + ": Target exists with same size, skip copying", self.LOGWRN)
            return 0
      if not self.local_copy_local(tofile, path, self.LGWNEX): return 0
      self.set_drop_group(tofile)
      return 1

# main function to execute this script
def main():
   """Entry point: instantiate GdexDrop, parse arguments, run, and exit."""
   from rda_python_setuid.setup_guide import show_setup_guide
   object = GdexDrop()
   show_setup_guide(object, 'rda_python_miscs', ['gdexcp', 'gdexdrop', 'gdexkill', 'gdexmod'])
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
