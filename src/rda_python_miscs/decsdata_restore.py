#!/usr/bin/env python3
##################################################################################
#     Title: decsdata_restore
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 2026-08-31
#   Purpose: restore decsdata datasets, or parts of them, out of the GLADE HSM
#            cold storage; the opposite of decsdata_storage
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from os import path as op
from rda_python_common.pg_file import PgFile

class DecsRestore(PgFile):
   """Restore decsdata datasets out of the GLADE HSM cold storage.

   'glade_hsm recall' only submits a request that the HSM batch processes
   fulfill later on, so restoring is done in three steps:

      -x  submit the recall requests for the given datasets/paths
      -s  check the recall status, repeat until nothing is left on tape
      -r  copy the recalled data back under the decsdata directory

   Recalled files stay readable inside cold storage for 7 days only, after
   which they are migrated onto tape again, so step -r must be done within
   that window.
   """

   def __init__(self):
      """Initialize DecsRestore with default option values and runtime state."""
      super().__init__()
      self.HSM = os.environ.get('GLADE_HSM', op.expanduser('~benkirk/glade_hsm'))
      self.VALOPTS = 'Dwl'   # single-value options
      self.MULOPTS = 'd'     # multi-value options
      self.MODOPTS = 'hf'    # mode options
      self.ACTOPTS = 'xsr'   # action options, one and only one is required
      self.OPTS = {
         'D': None,   # cold storage date, in YYYYMMDD or YYYY-MM-DD
         'w': None,   # decsdata directory, defaults to PGLOG['DECSHOME']
         'l': None,   # dataset list file
         'd': [],     # dataset IDs, a sub-path may be appended to each one
         't': None,   # target directory of -r, defaults to the decsdata directory
         'h': 0,      # 1 to show help message
         'f': 0,      # 1 to copy back while files are still on tape
      }
      self.ACTION = None     # one of the ACTOPTS letters
      self.SIZEUNITS = {     # units reported by 'gladequota', in bytes
         'B': 1, 'KIB': 1024, 'MIB': 1024**2,
         'GIB': 1024**3, 'TIB': 1024**4, 'PIB': 1024**5,
      }
      self.RINFO = {
         'decsdir': None,   # decsdata directory the data is restored into
         'roots': [],       # cold storage directories to look the data up in
         'acnt': 0,         # number of dataset paths acted on successfully
      }

   # function to read parameters
   def read_parameters(self):
      """Parse the command line into the OPTS option values and the action.

      Single-value options -D, -w and -l take one value each, multi-value
      option -d gathers every following dataset path, mode options -h and -f
      are simple flags, and action options -x, -s and -r are mutually
      exclusive; -r optionally takes a target directory.  Exits with usage if
      -h is given or no action is specified.
      """
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "decsdata_restore.log"   # set different log file
      argv = sys.argv[1:]
      self.cmdlog("decsdata_restore {}".format(' '.join(argv)))
      option = None
      for arg in argv:
         ms = re.match(r'^-(\w+)$', arg)
         if ms:
            option = ms.group(1)
            if option in self.ACTOPTS:
               self.set_action(option)
               if option != 'r': option = None   # -r may be followed by a target directory
            elif option in self.MODOPTS:
               self.OPTS[option] = 1
               option = None
            elif option not in self.VALOPTS and option not in self.MULOPTS:
               self.pglog(arg + ": Unknown Option", self.LGEREX)
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option in self.MULOPTS:
            self.OPTS[option].append(arg)   # gather all values until the next option
         else:
            if option == 'r': option = 't'   # the value of -r is the target directory
            self.OPTS[option] = arg
            option = None
      if self.OPTS['h'] or not self.ACTION: self.show_usage("decsdata_restore")

   # remember the action option and reject a second one
   def set_action(self, option):
      """Record the single action option to perform.

      Args:
         option (str): One of the ACTOPTS letters.
      """
      if self.ACTION and self.ACTION != option:
         self.pglog("-{}: Cannot combine with Action -{}".format(option, self.ACTION), self.LGEREX)
      self.ACTION = option

   # function to start actions
   def start_actions(self):
      """Validate the caller, resolve the cold storage paths, and act on each dataset path."""
      self.dssdb_dbname()
      self.validate_decs_group('decsdata_restore', self.PGLOG['CURUID'], 1)
      self.set_restore_paths()
      specs = self.get_dataset_list()
      if not specs: self.pglog("No dataset found to restore", self.LGWNEX)
      if self.ACTION == 'x': self.check_restore_space(specs)
      for spec in specs:
         self.restore_one_path(spec)
      acts = {'x': 'requested Recall', 's': 'checked Status', 'r': 'copied back'}
      s = ('s' if self.RINFO['acnt'] > 1 else '')
      self.pglog("{} of {} Dataset Path{} {}".format(self.RINFO['acnt'], len(specs),
                 s, acts[self.ACTION]), self.LOGWRN)
      self.cmdlog()

   # resolve the decsdata directory and the cold storage directories
   def set_restore_paths(self):
      """Fill RINFO with the decsdata directory and the cold storage directories to search.

      For a given -D date only '<decsdata>/cold_storage_<date>/COLD_STORAGE' is
      searched.  Without -D both '<decsdata>/COLD_STORAGE' and every
      '<decsdata>/cold_storage_<YYYYMMDD>/COLD_STORAGE' are searched, the most
      recent dated one first.
      """
      decsdir = self.OPTS['w'] if self.OPTS['w'] else self.PGLOG['DECSHOME']
      if not self.check_local_file(decsdir, 0, self.LOGWRN):
         self.pglog(decsdir + ": decsdata directory NOT exists", self.LGEREX)
      self.RINFO['decsdir'] = decsdir
      if not self.OPTS['t']: self.OPTS['t'] = decsdir
      roots = []
      if self.OPTS['D']:
         date = re.sub('-', '', self.OPTS['D'])
         if not re.match(r'^\d{8}$', date):
            self.pglog(date + ": Invalid cold storage date, YYYYMMDD expected", self.LGEREX)
         roots.append(self.join_paths(decsdir, "cold_storage_{}/COLD_STORAGE".format(date)))
      else:
         roots.append(self.join_paths(decsdir, "COLD_STORAGE"))
         files = self.local_glob(self.join_paths(decsdir, "cold_storage_[0-9]*/COLD_STORAGE"), 0, self.LOGWRN)
         for file in sorted(files, reverse = True):
            if not files[file]['isfile']: roots.append(file)
      for root in roots:
         if self.check_local_file(root, 0, 0): self.RINFO['roots'].append(root)
      if not self.RINFO['roots']:
         self.pglog("{}: No cold storage directory found in {}".format(', '.join(roots), decsdir), self.LGEREX)
      self.pglog("Cold storage searched: {}".format(', '.join(self.RINFO['roots'])), self.LOGWRN)

   # gather the dataset paths to restore
   def get_dataset_list(self):
      """Return the list of dataset paths to restore.

      Uses the -d values if given.  Otherwise reads the -l list file, creating
      it first from every dNNNNNN directory in the cold storage directories if
      it does not exist yet.

      Returns:
         list[str]: Dataset IDs, each optionally followed by a sub-path.
      """
      if self.OPTS['d']:
         self.pglog("Restore {} given Dataset Path(s)".format(len(self.OPTS['d'])), self.LOGWRN)
         return self.OPTS['d']
      lstfile = self.OPTS['l'] if self.OPTS['l'] else "dsids_{}.lst".format(re.sub('-', '', self.curdate()))
      if not op.isfile(lstfile):
         dsids = self.get_coldstorage_datasets()
         with open(lstfile, 'w') as OUT:
            for dsid in dsids: OUT.write(dsid + "\n")
         self.pglog("{}: Generated with {} Dataset(s)".format(lstfile, len(dsids)), self.LOGWRN)
      specs = []
      with open(lstfile, 'r') as IN:
         for line in IN:
            line = line.strip()
            if line: specs.append(line)
      self.pglog("{}: Read {} Dataset Path(s) to restore".format(lstfile, len(specs)), self.LOGWRN)
      return specs

   # find all dNNNNNN dataset directories in the cold storage directories
   def get_coldstorage_datasets(self):
      """Return the sorted dataset IDs of every dNNNNNN directory in the cold storage directories.

      Returns:
         list[str]: Unique dataset IDs; plain files matching the pattern are skipped.
      """
      dsids = []
      for root in self.RINFO['roots']:
         files = self.local_glob(self.join_paths(root, "d" + "[0-9]"*6), 0, self.LOGWRN)
         for file in files:
            if files[file]['isfile']: continue
            dsid = op.basename(file)
            if dsid not in dsids: dsids.append(dsid)
      return sorted(dsids)

   # locate a dataset path in the cold storage directories, the first match wins
   def find_cold_path(self, spec):
      """Look a dataset path up in each cold storage directory.

      Warns and names the ignored ones if the path is found in more than one
      cold storage directory.

      Args:
         spec (str): Dataset ID, optionally followed by a sub-path.

      Returns:
         tuple: (path, info dict) of the first match, or (None, None).
      """
      hits = {}
      for root in self.RINFO['roots']:
         path = self.join_paths(root, spec)
         info = self.check_local_file(path, 0, 0)
         if info: hits[path] = info
      if not hits: return (None, None)
      paths = list(hits)
      if len(paths) > 1:
         self.pglog("{}: Found in {} cold storage directories, use {}".format(spec, len(paths), paths[0]), self.LOGWRN)
         self.pglog("{}: Ignored {}".format(spec, ', '.join(paths[1:])), self.LOGWRN)
      return (paths[0], hits[paths[0]])

   # count the files of a cold storage path still on tape
   def hsm_offline_count(self, path, isfile):
      """Return the number of files under a cold storage path that are still on tape.

      Args:
         path (str): Cold storage path of a file or directory.
         isfile (int): 1 if path is a regular file, 0 for a directory.

      Returns:
         int | None: Count of offline files, or None if it cannot be determined.
      """
      out = self.pgsystem("{} status {}".format(self.HSM, path), self.LOGWRN, 51)
      if not out: return None
      if isfile: return (1 if re.search(r'migrated', out) else 0)
      cnts = re.findall(r'Offline:\s*([\d,]+)', out)
      if not cnts: return None
      return int(re.sub(',', '', cnts[-1]))

   # build the sfile condition of one dataset path
   def sfile_condition(self, spec):
      """Turn a dataset path into a condition on table dssdb.sfile.

      A saved file lives in '<decsdata>/<dsid>/<type>/<sfile>', so the first
      component of the path is the dataset ID, the second one the saved file
      type, and the rest the leading part of the sfile field.

      Args:
         spec (str): Dataset ID, optionally followed by a sub-path.

      Returns:
         str: The WHERE condition of the saved files under the path.
      """
      paths = spec.strip('/').split('/')
      if not re.match(r'^[a-z]\d{6}$', paths[0]):
         self.pglog(spec + ": Invalid dataset path, dNNNNNN expected", self.LGEREX)
      cnd = "dsid = '{}'".format(paths[0])
      if len(paths) > 1:
         if not re.match(r'^\w$', paths[1]):
            self.pglog(spec + ": Invalid saved file type, one word character expected", self.LGEREX)
         cnd += " AND type = '{}'".format(paths[1])
      if len(paths) > 2:
         sfile = '/'.join(paths[2:])
         if re.search(r"['\\]", sfile):
            self.pglog(spec + ": Invalid saved file path", self.LGEREX)
         # the path is either a saved file itself or the directory holding them
         cnd += " AND (sfile = '{}' OR sfile LIKE '{}/%')".format(sfile, re.sub(r'([%_])', r'\\\1', sfile))
      return cnd

   # get the archived size of one dataset path
   def restore_data_size(self, spec):
      """Return the total size of the saved files under one dataset path.

      Args:
         spec (str): Dataset ID, optionally followed by a sub-path.

      Returns:
         int: Number of bytes recorded in dssdb.sfile; 0 if nothing is found.
      """
      pgrec = self.pgget('sfile', "sum(data_size) tsize, count(sid) fcnt",
                         self.sfile_condition(spec), self.LOGWRN)
      if not pgrec or not pgrec['tsize']:
         self.pglog(spec + ": No saved file found in RDADB", self.LOGWRN)
         return 0
      self.pglog("{}: {} in {} saved file(s)".format(spec,
                 self.format_float_value(pgrec['tsize']), pgrec['fcnt']), self.LOGWRN)
      return int(pgrec['tsize'])

   # get the GLADE space left for the decsdata directory
   def decsdata_free_size(self):
      """Return the GLADE space left on the quota holding the decsdata directory.

      Parses the 'Used' and 'Quota' columns of 'gladequota' and picks the
      longest reported path the decsdata directory falls under.

      Returns:
         int | None: Number of free bytes, or None if it cannot be determined.
      """
      cmd = self.get_local_command("gladequota", self.PGLOG['COMMONUSER'])
      out = self.pgsystem(cmd, self.LOGWRN, 21)   # 1+4+16, log the command and return stdout
      if not out: return None
      target = op.realpath(self.RINFO['decsdir'])
      (fsize, fpath) = (None, None)
      for line in out.split('\n'):
         ms = re.match(r'^(/\S+)\s+([\d.]+)\s*(\w+)\s+([\d.]+)\s*(\w+)', line)
         if not ms: continue   # skips the header and the 'n/a' quota lines
         path = ms.group(1)
         if not (target == path or target.startswith(path + '/')): continue
         if fpath and len(fpath) >= len(path): continue   # keeps the closest path only
         used = self.quota_size(ms.group(2), ms.group(3))
         quota = self.quota_size(ms.group(4), ms.group(5))
         if used is None or quota is None: continue
         (fsize, fpath) = (max(quota - used, 0), path)
      return fsize

   # convert one 'gladequota' size into bytes
   def quota_size(self, value, unit):
      """Convert one size reported by 'gladequota' into bytes.

      Args:
         value (str): The numeric part of the size.
         unit (str): The unit of the size, such as 'TiB'.

      Returns:
         int | None: Number of bytes, or None for an unknown unit.
      """
      unit = unit.upper()
      if unit not in self.SIZEUNITS: return None
      return int(float(value)*self.SIZEUNITS[unit])

   # make sure the decsdata directory has room for the whole restore
   def check_restore_space(self, specs):
      """Stop the recall if the decsdata directory cannot hold the whole restore.

      The size to restore is added up from table dssdb.sfile and compared to
      the GLADE space left for the decsdata directory.  Twice the size is
      required, since the recall brings the data back on disk inside the cold
      storage first and Action -r copies it back afterwards, so both copies
      live under the decsdata quota at the same time.  The check is skipped,
      with a warning, if either size cannot be determined.

      Args:
         specs (list[str]): Dataset paths to recall.
      """
      tsize = 0
      for spec in specs:
         tsize += self.restore_data_size(spec)
      if not tsize:
         self.pglog("Unknown size to restore, Skip checking the decsdata space", self.LOGWRN)
         return
      fsize = self.decsdata_free_size()
      if fsize is None:
         self.pglog("{}: Cannot get the space left, Skip checking the decsdata space".format(self.RINFO['decsdir']), self.LOGWRN)
         return
      nsize = 2*tsize   # room for the recalled copy and for the copy of Action -r
      msg = "{}: Restore {}, needs {} of the {} left".format(self.RINFO['decsdir'],
            self.format_float_value(tsize), self.format_float_value(nsize),
            self.format_float_value(fsize))
      if nsize > fsize:
         self.pglog(msg + ", NOT enough space", self.LGEREX)
      self.pglog(msg, self.LOGWRN)

   # act on one dataset path in cold storage
   def restore_one_path(self, spec):
      """Perform the requested action on one dataset path in cold storage.

      Args:
         spec (str): Dataset ID, optionally followed by a sub-path.
      """
      (path, info) = self.find_cold_path(spec)
      if not path:
         self.pglog(spec + ": NOT found in cold storage", self.LOGERR)
         return
      if self.ACTION == 'x':
         self.recall_cold_path(spec, path)
      elif self.ACTION == 's':
         self.status_cold_path(spec, path, info['isfile'])
      else:
         self.copy_cold_path(spec, path, info['isfile'])

   # submit the recall request of one cold storage path
   def recall_cold_path(self, spec, path):
      """Submit the HSM recall request for one cold storage path.

      Args:
         spec (str): Dataset ID, optionally followed by a sub-path.
         path (str): Cold storage path of the data.
      """
      if self.pgsystem("{} recall -f {}".format(self.HSM, path), self.LOGWRN, 7):
         self.RINFO['acnt'] += 1
         self.pglog("{}: Recall requested, check the progress via -s".format(spec), self.LOGWRN)
      else:
         self.pglog("{}: Error request Recall of {}".format(spec, path), self.LOGERR)

   # report the recall status of one cold storage path
   def status_cold_path(self, spec, path, isfile):
      """Report the HSM and recall status of one cold storage path.

      Args:
         spec (str): Dataset ID, optionally followed by a sub-path.
         path (str): Cold storage path of the data.
         isfile (int): 1 if path is a regular file, 0 for a directory.
      """
      offline = self.hsm_offline_count(path, isfile)
      if offline is None:
         self.pglog("{}: Cannot get the offline file count of {}".format(spec, path), self.LOGERR)
         return
      self.RINFO['acnt'] += 1
      if offline > 0:
         s = ('s' if offline > 1 else '')
         self.pglog("{}: Recall PENDING, {} File{} still on tape".format(spec, offline, s), self.LOGWRN)
      else:
         self.pglog("{}: Recall COMPLETE, ready to copy back via -r".format(spec), self.LOGWRN)

   # copy one recalled cold storage path back into the decsdata directory
   def copy_cold_path(self, spec, path, isfile):
      """Copy one recalled cold storage path back to its target directory.

      Nothing is copied while files are still on tape unless -f is given.

      Args:
         spec (str): Dataset ID, optionally followed by a sub-path.
         path (str): Cold storage path of the data.
         isfile (int): 1 if path is a regular file, 0 for a directory.
      """
      offline = self.hsm_offline_count(path, isfile)
      if offline:
         s = ('s' if offline > 1 else '')
         if not self.OPTS['f']:
            self.pglog("{}: {} File{} still on tape, add Mode -f to copy anyway".format(spec, offline, s), self.LOGERR)
            return
         self.pglog("{}: {} File{} still on tape, copy it anyway".format(spec, offline, s), self.LOGWRN)
      tofile = self.join_paths(self.OPTS['t'], spec)
      # a directory is copied as '<path>/.' to merge into an existing target
      fromfile = path if isfile else path + "/."
      if self.local_copy_local(tofile, fromfile, self.LOGWRN):
         self.RINFO['acnt'] += 1
         self.pglog("{}: Copied back to {}".format(spec, tofile), self.LOGWRN)
      else:
         self.pglog("{}: Error copy {} back to {}".format(spec, path, tofile), self.LOGERR)

# main function to execute this script
def main():
   """Entry point: instantiate DecsRestore, parse arguments, run, and exit."""
   from rda_python_setuid.setup_guide import show_setup_guide
   object = DecsRestore()
   show_setup_guide(object, 'rda_python_miscs', ['decsdata_storage', 'decsdata_restore'])
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
