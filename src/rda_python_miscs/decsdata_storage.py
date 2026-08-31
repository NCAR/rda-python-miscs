#!/usr/bin/env python3
##################################################################################
#     Title: decsdata_storage
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 2026-08-31
#   Purpose: move decsdata datasets into a dated cold storage directory and hand
#            them to the GLADE HSM to be migrated onto tape
#    Github: https://github.com/NCAR/rda-python-miscs.git
##################################################################################
import re
import os
import sys
from os import path as op
from rda_python_common.pg_file import PgFile

class DecsStorage(PgFile):
   """Move decsdata datasets into cold storage and migrate them onto tape.

   Each given dataset directory is moved from the decsdata directory into
   '<decsdata>/cold_storage_<date>/' and then handed to 'glade_hsm migrate',
   which relocates it once more into a 'COLD_STORAGE/' sub-directory and lets
   the HSM batch processes migrate every large file onto tape.  Use
   decsdata_restore to bring the data back.
   """

   def __init__(self):
      """Initialize DecsStorage with default option values and runtime state."""
      super().__init__()
      self.HSM = os.environ.get('GLADE_HSM', op.expanduser('~benkirk/glade_hsm'))
      self.VALOPTS = 'Dwl'   # single-value options
      self.MULOPTS = 'd'     # multi-value options
      self.MODOPTS = 'hx'    # mode options
      self.OPTS = {
         'D': None,   # cold storage date, in YYYYMMDD or YYYY-MM-DD
         'w': None,   # decsdata directory, defaults to PGLOG['DECSHOME']
         'l': None,   # dataset list file
         'd': [],     # dataset IDs
         'h': 0,      # 1 to show help message
         'x': 0,      # 1 to execute, mandatory
      }
      self.SINFO = {
         'decsdir': None,    # decsdata directory the datasets are stored from
         'coldstor': None,   # cold storage directory the datasets are moved to
         'date': None,       # cold storage date
         'dcnt': 0,          # number of datasets moved into cold storage
      }

   # function to read parameters
   def read_parameters(self):
      """Parse the command line into the OPTS option values.

      Single-value options -D, -w and -l take one value each, multi-value
      option -d gathers every following dataset ID, and mode options -h and -x
      are simple flags.  Exits with usage if -h is given or -x is missing.
      """
      self.set_suid(self.PGLOG['EUID'])
      self.set_help_path(__file__)
      self.PGLOG['LOGFILE'] = "decsdata_storage.log"   # set different log file
      argv = sys.argv[1:]
      self.cmdlog("decsdata_storage {}".format(' '.join(argv)))
      option = None
      for arg in argv:
         ms = re.match(r'^-(\w+)$', arg)
         if ms:
            option = ms.group(1)
            if option in self.MODOPTS:
               self.OPTS[option] = 1
               option = None
            elif option not in self.VALOPTS and option not in self.MULOPTS:
               self.pglog(arg + ": Unknown Option", self.LGEREX)
            continue
         if not option: self.pglog(arg + ": Value provided without option", self.LGEREX)
         if option in self.MULOPTS:
            self.OPTS[option].append(arg)   # gather all values until the next option
         else:
            self.OPTS[option] = arg
            option = None
      if self.OPTS['h'] or not self.OPTS['x']: self.show_usage("decsdata_storage")

   # function to start actions
   def start_actions(self):
      """Validate the caller, resolve the cold storage paths, and store each dataset."""
      self.dssdb_dbname()
      self.validate_decs_group('decsdata_storage', self.PGLOG['CURUID'], 1)
      self.set_storage_paths()
      dsids = self.get_dataset_list()
      if not dsids: self.pglog("No dataset found for cold storage", self.LGWNEX)
      for dsid in dsids:
         self.store_one_dataset(dsid)
      s = ('s' if self.SINFO['dcnt'] > 1 else '')
      self.pglog("{} of {} Dataset{} moved into {}".format(self.SINFO['dcnt'],
                 len(dsids), s, self.SINFO['coldstor']), self.LOGWRN)
      self.cmdlog()

   # resolve the decsdata and cold storage directories
   def set_storage_paths(self):
      """Fill SINFO with the decsdata directory, cold storage date and cold storage path.

      Defaults the decsdata directory to PGLOG['DECSHOME'] and the date to
      today.  Dashes are stripped from the given date, which must then be 8
      digits.
      """
      decsdir = self.OPTS['w'] if self.OPTS['w'] else self.PGLOG['DECSHOME']
      if not self.check_local_file(decsdir, 0, self.LOGWRN):
         self.pglog(decsdir + ": decsdata directory NOT exists", self.LGEREX)
      date = re.sub('-', '', self.OPTS['D']) if self.OPTS['D'] else re.sub('-', '', self.curdate())
      if not re.match(r'^\d{8}$', date):
         self.pglog(date + ": Invalid cold storage date, YYYYMMDD expected", self.LGEREX)
      self.SINFO['decsdir'] = decsdir
      self.SINFO['date'] = date
      self.SINFO['coldstor'] = self.join_paths(decsdir, "cold_storage_" + date)

   # gather the dataset IDs to move into cold storage
   def get_dataset_list(self):
      """Return the list of dataset IDs to store.

      Uses the -d values if given.  Otherwise reads the -l list file, creating
      it first from every dNNNNNN directory in the decsdata directory if it
      does not exist yet.

      Returns:
         list[str]: Dataset IDs, empty if none is found.
      """
      if self.OPTS['d']:
         self.pglog("Store {} given Dataset(s) into cold storage".format(len(self.OPTS['d'])), self.LOGWRN)
         return self.OPTS['d']
      lstfile = self.OPTS['l'] if self.OPTS['l'] else "dsids_{}.lst".format(self.SINFO['date'])
      if not op.isfile(lstfile):
         dsids = self.get_decsdata_datasets()
         with open(lstfile, 'w') as OUT:
            for dsid in dsids: OUT.write(dsid + "\n")
         self.pglog("{}: Generated with {} Dataset(s)".format(lstfile, len(dsids)), self.LOGWRN)
      dsids = []
      with open(lstfile, 'r') as IN:
         for line in IN:
            line = line.strip()
            if line: dsids.append(line)
      self.pglog("{}: Read {} Dataset(s) for cold storage".format(lstfile, len(dsids)), self.LOGWRN)
      return dsids

   # find all dNNNNNN dataset directories in the decsdata directory
   def get_decsdata_datasets(self):
      """Return the sorted dataset IDs of every dNNNNNN directory in the decsdata directory.

      Returns:
         list[str]: Dataset IDs; plain files matching the pattern are skipped.
      """
      pattern = self.join_paths(self.SINFO['decsdir'], "d" + "[0-9]"*6)
      files = self.local_glob(pattern, 0, self.LOGWRN)
      dsids = []
      for file in files:
         if not files[file]['isfile']: dsids.append(op.basename(file))
      return sorted(dsids)

   # move one dataset into cold storage and migrate it onto tape
   def store_one_dataset(self, dsid):
      """Move one dataset into the cold storage directory and migrate it onto tape.

      Skips the dataset if it is not an existing directory in the decsdata
      directory or if the move fails.  Increments SINFO['dcnt'] for each
      dataset successfully migrated.

      Args:
         dsid (str): Dataset ID, such as 'd612000'.
      """
      fromfile = self.join_paths(self.SINFO['decsdir'], dsid)
      info = self.check_local_file(fromfile, 0, self.LOGWRN)
      if not info:
         self.pglog(fromfile + ": Dataset NOT exists", self.LOGERR)
         return
      if info['isfile']:
         self.pglog(fromfile + ": Not a dataset directory", self.LOGERR)
         return
      tofile = self.join_paths(self.SINFO['coldstor'], dsid)
      if not self.move_local_file(tofile, fromfile, self.LOGWRN):
         self.pglog("{}: Error move {} into cold storage".format(fromfile, dsid), self.LOGERR)
         return
      cmd = "{} migrate -f {}".format(self.HSM, tofile)
      if self.pgsystem(cmd, self.LOGWRN, 7):
         self.SINFO['dcnt'] += 1
         self.pglog("{}: Migrated onto tape from {}".format(dsid, tofile), self.LOGWRN)
      else:
         self.pglog("{}: Error migrate onto tape from {}".format(dsid, tofile), self.LOGERR)

# main function to execute this script
def main():
   """Entry point: instantiate DecsStorage, parse arguments, run, and exit."""
   from rda_python_setuid.setup_guide import show_setup_guide
   object = DecsStorage()
   show_setup_guide(object, 'rda_python_miscs', ['decsdata_storage', 'decsdata_restore'])
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
