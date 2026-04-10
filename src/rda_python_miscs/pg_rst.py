#!/usr/bin/env python3
#
###############################################################################
#
#     Title : pg_rst.py
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 09/14/2020
#   Purpose : python library module to help convert text help documents into
#             rst format with help of rst templates
#
# Work File : $DSSHOME/lib/python/PgDOCS.py
#    Github : https://github.com/NCAR/rda-shared-libraries.git
#
###############################################################################
#
import os
import re
import inspect
import argparse
import importlib
import importlib.util
from os import path as op
from rda_python_common.pg_file import PgFile
from rda_python_common.pg_util import PgUtil

class PgRST(PgFile, PgUtil):
   """Convert text-based program usage documents (.usg files) into
   reStructuredText (.rst) files using RST template files.

   Inherits from :class:`rda_python_common.pg_file.PgFile` and
   :class:`rda_python_common.pg_util.PgUtil`, giving access to the full
   file-operation and utility MRO chain (``PgFile → PgUtil → PgLOG``).
   Inherited file helpers (e.g. ``change_local_directory``) are called
   directly via ``self`` rather than as bare module functions.

   Parses a structured ``.usg`` source document into sections, options, and
   examples, then renders each as a standalone ``.rst`` file by substituting
   generated RST content into template files found under ``TMPDIR``.

   Class constants:
      Q0     -- quote character used as a markup sentinel in source documents
      Q1     -- RST bold open marker  (**)
      Q2     -- RST bold close marker (**)
      EMLIST -- set of program names rendered as hyperlinks
      SEARCH -- regex alternation matching option-category keywords
   """

   Q0 = "'"
   Q1 = "**"       # RST bold open  (was "<i><b>")
   Q2 = "**"       # RST bold close (was "</i></b>")
   TLEVEL = 3       # max section level to be rendered (1, 2, or 3)
   EMLIST = {
      'dsarch' : 1,
      'msarch' : 1,
      'dsupdt' : 1,
      'dsrqst' : 1,
      'viewrqstusage' : 1,
      'dscheck' : 1,
      'viewcheckusage' : 1,
      'gatherxml' : 1,
      'pgconvert' : 1,
      'publish_filelist' : 1,
      'rcm' : 1,
      'dcm' : 1,
   }
   SEARCH = "(Action|Info|Mode|Multi-Value|Single-Value)"

   def __init__(self):
      """Initialize all per-document state and path configuration.

      Calls ``super().__init__()`` to initialise the full ``PgFile`` /
      ``PgUtil`` / ``PgLOG`` MRO chain before setting up the document-level
      state.  Instance attributes are reset for every new document so that a
      single ``PgRST`` instance can be reused across multiple calls to
      ``process_docs``.
      """
      super().__init__()
      self.OPTS = {}
      self.ALIAS = {}

      self.SECIDS = { # section ids for category
         'Action' : None,
         'Info' : None,
         'Mode' : None,
         'Multi-Value' : None,
         'Single-Value' : None,
      }

      # Section array with each section pointing to a hash:
      # secid    - section ID (1, 1.1, 1.1.1, ...)
      # title    - section title
      # level    - section level, 0 top level
      # desc     - section description
      # opts     - pointer to an array of included option short names
      self.sections = []

      # Option hash keyed by short option names and each is a hash itself
      # secid    - section ID the option belongs
      # name     - option long name
      # type     - option type, 0 - Mode, 1 - Info, 2 - Action
      # alias    - array of alias option names None if none
      # desc     - option description
      # examples - array of example indices included for the option
      self.options = {}

      # Example array with each example pointing to a hash:
      # opt      - option short name the example belongs
      # title    - example title
      # desc     - example description
      self.examples = []

      # global info to be used by the whole application
      self.DOCS = {
         'ORIGIN' : os.getcwd(), # directory to the original document
         'TMPDIR' : op.join(op.dirname(op.abspath(__file__)), "rst_templates"), # directory to find the templates
         'DOCDIR' : os.getcwd(), # root/final directory for rst documents
         'DOCNAM' : "", # document name: dsarch, dsupdt, etc.
         'DOCTIT' : "", # document name in upper case letters
         'DOCLNK' : None,
      }
      self.LINKS = ['dsarch', 'dsupdt', 'dsrqst', 'dscheck']

   #
   # Function process_docs(docname: document name, 'dsarch', 'dsupdt'
   #                          opts: option hash defined for the document
   #                         alias: alias names for given opts)
   #
   def process_docs(self, docname, opts, alias):
      """Parse *docname* and write all RST output files.

      This is the main entry point.  It populates ``self.sections``,
      ``self.options``, and ``self.examples`` by calling ``parse_docs``, then
      writes ``index.rst`` and one ``section<id>.rst`` per
      section into ``DOCDIR``.

      Args:
         docname (str): Short document name (e.g. ``'dsarch'``, ``'dsupdt'``).
         opts (dict): Mapping of two-letter option codes to ``[typidx, longname]``.
         alias (dict): Mapping of option codes to lists of alias names.
      """
      self.OPTS = opts
      self.ALIAS = alias

      self.parse_docs(docname)
      if not self.sections: self.pglog(docname + ": empty document", self.LGWNEX)
      self.DOCS['DOCNAM'] = docname
      if docname in self.LINKS: self.LINKS.remove(docname)
      self.DOCS['DOCLNK'] = r"({})".format('|'.join(self.LINKS))
      self.DOCS['DOCTIT'] = docname.upper()
      self.change_local_directory(self.DOCS['DOCDIR'], self.LGWNEX)
      self.pglog("Write rst document '{}' under {}".format(docname, self.DOCS['DOCDIR']), self.LOGWRN)
      self.write_index(self.sections[0])
      for section in self.sections:
         self.write_section(section)

   #
   # parse the original document and return a array of sections,
   #
   def parse_docs(self, docname):
      """Read *docname*.usg and populate ``sections``, ``options``, and ``examples``.

      Lines beginning with ``#`` are treated as comments and skipped.  In-line
      trailing comments are also stripped.

      Args:
         docname (str): Short document name used to locate ``<ORIGIN>/<docname>.usg``.
      """
      docfile = "{}/{}.usg".format(self.DOCS['ORIGIN'], docname)
      self.pglog("Parsing info for Document '{}'".format(docname), self.LOGWRN)
      section = self.init_section('0', "Preface")
      option = example = None
      with open(docfile, 'r') as fh:
         line = fh.readline()
         while line:
            if re.match(r'\s*#', line):
               line = fh.readline()
               continue   # skip comment lines
            ms = re.match(r'^(.*\S)\s+#', line)
            if ms:
               line = ms.group(1)     # remove comments
            else:
               line = line.rstrip()   # remove trailing white spaces

            ms = re.match(r'^([\d\.]+)\s+([A-Z].+)$', line)
            if ms:   # start new section
               section = self.record_section(section, option, example, ms.group(1), ms.group(2))
               option = example = None
            else:
               ms = re.match(r'^  -([A-Z]{2}) or -\w+(.*)$', line)
               if ms:    # found new option
                  option = self.record_option(section, option, example, ms.group(1), ms.group(2))
                  example = None
               elif option:
                  ms = re.match(r'^  For( | another )example, (.*)$', line)
                  if ms:    # found example
                     example = self.record_example(option, example, ms.group(2))
                  elif example:
                     example['desc'] += line + "\n"
                  else:
                     option['desc'] += line + "\n"
               else:
                  section['desc'] += line + "\n"

            line = fh.readline()

      self.record_section(section, option, example)

      # check completion of options
      for opt in self.OPTS:
         if opt not in self.options:
            self.pglog("Missing option Entry -{} (-{}) in Document '{}'".format(opt, self.OPTS[opt][1], docname), self.LOGWRN)
      if self.sections:
         cnt = len(self.sections)
         s = 's' if cnt > 1 else ''
         self.pglog("{} Section{} gathered for '{}'".format(cnt, s, docname), self.LOGWRN)

   #
   # cache section information
   #
   def record_section(self, section, option, example, nsecid=None, ntitle=None):
      """Append the completed *section* to ``self.sections`` and optionally start a new one.

      Also flushes any pending *option* (and its examples) into the section
      before storing it.  If *nsecid* is provided, initialises and returns a
      fresh section dict; otherwise returns ``None``.

      Args:
         section (dict): The section dict currently being assembled.
         option  (dict | None): Pending option dict, flushed before storing the section.
         example (dict | None): Pending example dict forwarded to ``record_option``.
         nsecid  (str | None): Section ID for the new section to create.
         ntitle  (str | None): Title for the new section.

      Returns:
         dict | None: A new section dict when *nsecid* is given, else ``None``.
      """
      if option or section['desc'] != "\n":
         if option: self.record_option(section, option, example)
         self.sections.append(section)    # record section globally

      if nsecid: return self.init_section(nsecid, ntitle)

   #
   # cache option information
   #
   def record_option(self, section, option, example, nopt=None, ndesc=None):
      """Append the completed *option* to ``self.options`` and optionally start a new one.

      Also flushes any pending *example* before storing the option.  Appends
      the option's short name to the owning *section*'s ``opts`` list.

      Args:
         section (dict): The section that owns this option.
         option  (dict | None): The option dict being completed.
         example (dict | None): Pending example dict forwarded to ``record_example``.
         nopt    (str | None):  Short name for the new option to initialise.
         ndesc   (str | None):  Description fragment for the new option.

      Returns:
         dict | None: A new option dict when *nopt* is given, else ``None``.
      """
      if option:
         if example: self.record_example(option, example)
         self.options[option['opt']] = option     # record option globally
         section['opts'].append(option['opt']) # record option short name in section

      if nopt: return self.init_option(section['secid'], nopt, ndesc)

   def record_example(self, option, example, ndesc=None):
      """Append the completed *example* to ``self.examples`` and optionally start a new one.

      Splits the example's accumulated description on the first period to
      extract a short title, then stores the remainder as the body.

      Args:
         option  (dict): The option that owns this example.
         example (dict | None): The example dict being completed.
         ndesc   (str | None):  Opening description text for the next example.

      Returns:
         dict | None: A new example dict when *ndesc* is given, else ``None``.
      """
      if example:
         lines = example['desc'].split('\n')
         lcnt = len(lines)
         title = lines[0].strip()
         ol = 1
         if title[-1] != ':':
            for l in range(1, lcnt):
               line = lines[l].strip()
               title += ' ' + line
               ol += 1
               if line[-1] == ':': break
         example['desc'] = '\n'.join(lines[ol:]) if lcnt > ol else ''
         example['title'] = title
         option['exmidxs'].append(len(self.examples))   # record example index in option
         self.examples.append(example)     # record example globally

      if ndesc: return self.init_example(option['opt'], ndesc)

   #
   # initialize section dict
   #
   def init_section(self, secid, title):
      """Create and return a new section dict, updating ``SECIDS`` for known categories.

      Args:
         secid (str): Dotted section identifier (e.g. ``'1'``, ``'1.2'``).
         title (str): Human-readable section title.

      Returns:
         dict: New section dict with keys ``secid``, ``title``, ``desc``,
               ``level``, and ``opts``.
      """
      level = secid.count('.') + 1
      section = {
         'secid' : secid,
         'title' : title,
          'desc' : "",
         'level' : level,
          'opts' : []
      }
      if level == 1:
         if re.match(r'^ACTION', section['title']):
            self.SECIDS['Action'] = secid
         elif re.match(r'^MODE', section['title']):
            self.SECIDS['Mode'] = secid
         elif re.match(r'^INFORMATION', section['title']):
            self.SECIDS['Info'] = secid
      elif level == 2:
         if re.match(r'^Single-Value', section['title']):
            self.SECIDS['Single-Value'] = secid
         elif re.match(r'^Multi-Value', section['title']):
            self.SECIDS['Multi-Value'] = secid

      return section

   #
   # initialize option dict
   #
   def init_option(self, secid, opt, desc):
      """Create and return a new option dict populated from ``self.OPTS``.

      Strips any leading alias annotation from *desc* (e.g. ``", "`` or
      ``" (Alias: ...), "``).

      Args:
         secid (str): ID of the section this option belongs to.
         opt   (str): Two-letter option short name.
         desc  (str): Raw description text from the source document.

      Returns:
         dict: New option dict with keys ``secid``, ``opt``, ``desc``,
               ``exmidxs``, ``name``, ``type``, and optionally ``alias``.
      """
      option = {}
      types = ("Mode", "Info", "Info", "Action")

      if opt not in self.OPTS:
         self.pglog("{} -- option not defined for {}".format(opt, self.DOCS['DOCNAM']), self.LGWNEX)
      option['secid'] = secid
      option['opt'] = opt
      ms = re.match(r'^(, | \(Alias: .*\), )(.*)', desc)
      if ms: desc = ms.group(2)
      option['desc'] = desc + "\n"
      option['exmidxs'] = []
      option['name'] = self.OPTS[opt][1]
      if opt in self.ALIAS: option['alias'] = self.ALIAS[opt]
      typidx = self.OPTS[opt][0]
      if typidx > 3: typidx = 3
      option['type'] = types[typidx]

      return option

   #
   # initialize example dict
   #
   def init_example(self, opt, desc):
      """Create and return a new example dict.

      Args:
         opt  (str): Short name of the option this example illustrates.
         desc (str): Opening description text (title-cased on creation).

      Returns:
         dict: New example dict with keys ``opt``, ``title``, and ``desc``.
      """
      desc = (desc[0].upper() + desc[1:]) if desc else desc
      return {'opt' : opt, 'title' : "", 'desc' : desc + "\n"}

   #
   # write the entry file: index.rst
   #
   def write_index(self, section):
      """Write ``index.rst`` from the ``index.rst.temp`` template.

      Passes ``TITLE`` (document title), ``SECID`` (first section id),
      and the generated ``TOC`` RST content as substitution variables.

      Args:
         section (dict): The first section dict, used to supply ``SECID``.
      """
      hash = {'TITLE' : self.DOCS['DOCTIT'], 'SECID' : section['secid'],
              'TOC'   : self.create_toc()}

      self.template_to_rst("index", hash)

   #
   # write a section rst file
   #
   def write_section(self, section):
      """Write ``section<secid>.rst`` from the ``section.rst.temp`` template.

      Passes ``TITLE``, ``SECID``, and the generated ``SECTION`` RST content
      as substitution variables.

      Args:
         section (dict): The section dict to render.
      """
      hash = {}
      secid = section['secid']
      hash['TITLE'] = section['title']
      hash['SECID'] = secid
      hash['SECTION'] = self.create_section(section)

      self.template_to_rst("section", hash, secid)

   #
   # convert rst template to rst file
   #
   def template_to_rst(self, template, hash, extra=None):
      """Read ``<template>.rst.temp``, substitute ``__KEY__`` placeholders, and write the result.

      Comment lines (starting with ``#``) and trailing inline comments are
      stripped from the template before substitution.  Aborts with a log
      error if a placeholder key is missing from *hash* or maps to an empty
      string.

      Args:
         template (str): Base template name (e.g. ``'index'``, ``'toc'``, ``'section'``).
         hash     (dict): Mapping of uppercase placeholder keys to their RST content.
         extra    (str | None): Optional suffix appended to the output filename
                                (e.g. a section id).  Defaults to ``''``.
      """
      tempfile = "{}/{}.rst.temp".format(self.DOCS['TMPDIR'], template)
      if extra is None: extra = ""
      rstfile = "{}/{}{}.rst".format(self.DOCS['DOCDIR'], template, extra)

      with open(tempfile, 'r') as tf, open(rstfile, 'w') as rf:
         idx = 0
         line = tf.readline()
         while line:
            idx += 1
            if re.match(r'\s*#', line):
               line = tf.readline()
               continue   # skip comment lines
            ms = re.match(r'^(.*\S)\s+#', line)
            if ms:
               line = ms.group(1)     # remove comments
            else:
               line = line.rstrip()   # remove trailing white spaces

            matches = re.findall(r'__([A-Z]+)__', line)
            if matches:
               for key in matches:
                  if key not in hash: self.pglog("{}: not defined at {}({}) {}".format(key, line, idx, tempfile), self.LGWNEX)
                  if not hash[key]: self.pglog(key + ": empty content", self.LGWNEX)
                  line = line.replace("__{}__".format(key), hash[key])
            rf.write(line + "\n")
            line = tf.readline()
      self.pglog("{}{}.rst created from {}.rst.temp".format(template, extra, template), self.LOGWRN)

   #
   # create rst content for table of contents
   #
   def create_toc(self, csection=None):
      """Build and return the RST table-of-contents string of a given section.

      Produces a nested bullet list of section links (indented by section
      level) followed by a flat Appendix A list of all example links.

      Returns:
         str: RST-formatted TOC content ready for ``__TOC__`` substitution.
      """
      
      content = ""
      clevel = csection['level'] if csection else 0
      csecid = csection['secid'] if csection else ""
      depth = self.TLEVEL - clevel
      level = clevel+1
      preid = csecid+'.'

      # nested bullet list for all sections
      for section in self.sections:
         secid = section['secid']
         if csecid and not secid.startswith(preid): continue
         if section['level'] == level: content += "   section{}\n".format(secid)

      if not content: return ""

      content = f".. toctree::\n   :maxdepth: {depth}\n   :caption: Table of Contents\n\n{content}\n"
      # appendix A: list of examples for the parent section and its subsections
      appendix = ""
      idx = 1  # used as example index
      for exm in self.examples:
         opt = exm['opt']
         option = self.options[opt]
         secid = option['secid']
         if not csecid or secid == csecid or secid.startswith(preid):
            appendix += "- :ref:`A.{}. {} Option -{} (-{}) <{}_e{}>`\n".format(
                        idx, option['type'], opt, option['name'], secid, idx)
         idx += 1
      if appendix:
         content += "**Appendix A: List of Examples**\n\n" + appendix + "\n"

      return content

   #
   # create a section rst content
   #
   def create_section(self, section):
      """Build and return the full RST body for *section*.

      Concatenates the section's description prose followed by the RST
      content for each option listed in ``section['opts']``.

      Args:
         section (dict): Section dict to render.

      Returns:
         str: RST-formatted section body for ``__SECTION__`` substitution.
      """
      secid = section['secid']
      content = self.create_description(section['desc'], secid, 0)

      for opt in section['opts']:
         content += self.create_option(opt, secid)

      content += self.create_toc(section)  # add a local TOC for the section and its subsections
      return content

   #
   # create an option rst content
   #
   def create_option(self, opt, secid):
      """Build and return the RST content for a single option.

      Renders the option heading (with anchor), its description, and all
      associated examples.

      Args:
         opt   (str): Two-letter option short name.
         secid (str): ID of the containing section.

      Returns:
         str: RST-formatted option block.
      """
      option = self.options[opt]
      content = self.create_option_name(opt, option)
      dtype = 3 if option['type'] == "Action" else 1
      content += self.create_description(option['desc'], secid, dtype)

      if 'exmidxs' in option:
         for idx in option['exmidxs']:
            content += self.create_example(idx, secid)

      return content

   #
   # create rst text for option name
   #
   def create_option_name(self, opt, option):
      """Build the RST anchor and underlined heading for an option.

      Emits a ``.. _<opt>:`` label followed by a title line of the form::

         <Type> Option -**XX** (-**longname**) [Alias(es): ...] :
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

      The ``~`` underline is sized to match the actual title line length
      (including RST bold markers).

      Args:
         opt    (str):  Two-letter option short name.
         option (dict): Option dict containing ``type`` and optionally ``alias``.

      Returns:
         str: RST anchor + heading block.
      """
      qopt = self.Q1 + opt + self.Q2
      nopt = self.Q1 + self.OPTS[opt][1] + self.Q2

      # Build the title line once; its length drives the underline width.
      title = "{} Option -{} (-{})".format(option['type'], qopt, nopt)
      if 'alias' in option:
         alias = option['alias']
         acnt = len(alias)
         parts = ["-{}{}{}".format(self.Q1, a, self.Q2) for a in alias]
         s = 'es' if acnt > 1 else ''
         title += " (Alias{}: {})".format(s, ", ".join(parts))
      title += " :"

      content = "\n.. _{}:\n\n".format(opt)
      content += title + "\n"
      content += "^" * len(title) + "\n\n"

      return content

   #
   # create an example rst content
   #
   def create_example(self, exmidx, secid):
      """Build the RST content for a single example.

      Emits a ``.. _secid_e<N>:`` anchor, a bold ``EXAMPLE N. <title>`` heading,
      and the example's body description.

      Args:
         exmidx (int): Zero-based index into ``self.examples``.
         secid  (str): ID of the containing section (for link resolution).

      Returns:
         str: RST-formatted example block.
      """
      example = self.examples[exmidx]
      exm = exmidx + 1
      content = "\n.. _{}_e{}:\n\n".format(secid, exm)
      content += "**EXAMPLE {}. {}**\n\n".format(exm, example['title'])
      content += self.create_description(example['desc'], secid, 2)

      return content

   #
   # add links to other options (RST format)
   #
   def replace_option_link(self, line, csecid, ptype=None, dtype=None):
      """Scan *line* for option references, section-category keywords, URLs, and
      quoted program names, and replace each with an RST hyperlink.

      All links use RST named anchor references (`` `name`_ `` or
      `` `text <name_>`_ ``) targeting anchors of the form ``.. _name:``.
      Cross-file option links target ``.. _section{secid}:`` anchors.

      Args:
         line   (str): Source text line to process.
         csecid (str): Section ID of the page currently being rendered
                       (used to decide whether a link should be same-file).
         ptype  (int): Paragraph type context: 0=normal, 1=table, 2=synopsis.
                       Defaults to 0.
         dtype  (int): Description type: 0=section, 1=option, 2=example,
                       3=action.  Defaults to -1 (unspecified).

      Returns:
         str: The line with option/URL references replaced by RST links.
      """
      if ptype is None: ptype = 0
      if dtype is None: dtype = -1

      ms = re.search(r'<([=!:])>', line)
      if ms:
         if ms.group(1) == ":":
            opts = re.findall(r'(^|>)([a-zA-Z]{2,})(<:)', line)
         else:
            opts = re.findall(r'(^)([a-zA-Z]{2,})(<%s>)/' % ms.group(1), line)
      elif ptype == 2:
         opts = re.findall(r'(-\(*)([a-zA-Z]{2,})(\W|$)', line)
         ms = re.match(r'^\s*%s(\s+[\w\.]+\s+|\s+)([a-zA-Z]{2})(\s)' % self.DOCS['DOCNAM'], line)
         if ms: opts = [ms.groups()] + opts
      else:
         opts = re.findall(r'(^-\(*|\W-\(*)([a-zA-Z]{2,})(\W|$)', line)

      for optary in opts:
         opt = self.get_short_option(optary[1])
      
         pre = optary[0]
         after = optary[2]
         secid = self.options[opt]['secid']
         anchor = opt
         ms = re.search(r'(-\({}\|\w+\))'.format(opt), line)
         if ms:
            if secid == csecid and ptype == 2: continue
            opt = ms.group(1)
            pre = after = ''
         else:
            ms = re.search(r'(-{})'.format(opt), line)
            if ms:
               opt = ms.group(1)
               pre = pre[:-1]

         replace = pre + opt + after
         link = "{}:ref:`{} <{}>`{}".format(pre, opt, anchor, after)
         line = line.replace(replace, link)

      opts = re.findall(r'(^|\W){}(\s+(o|O)ptions*\W|\W|$)'.format(self.SEARCH), line)
      for optary in opts:
         opt = optary[1]
         if not self.SECIDS[opt]: continue
         secid = self.SECIDS[opt]
         if secid == csecid or re.match(r'{}'.format(secid), csecid): continue
         pre = optary[0]
         after = optary[2]
         replace = pre + opt + after
         ms = re.search(r'(\s+Options*)\W', after, re.I)
         if ms:
            opt += ms.group(1)
            after = after.replace(ms.group(1), '')
         if ptype == 2 and re.search(r'Mode Options*', opt) and dtype == 3:
            link = "{}:ref:`{} <mode{}>`{}".format(pre, opt, csecid, after)
         else:
            link = "{}:ref:`{} <section{}>`{}".format(pre, opt, secid, after)
         line = line.replace(replace, link)

      # Q0...Q0 is a source-document quoting convention: Q0wordQ0 marks
      # a program name to be rendered as a link or bold text.
      opts = re.findall(r"{}(\S+){}".format(self.Q0, self.Q0), line)
      for opt in opts:
         if opt not in self.EMLIST: continue  # quote only predefined ones
         replace = self.Q0 + opt + self.Q0
         if re.search(self.DOCS['DOCLNK'], opt):
            link = "`{} <https://gdex-docs-{}.readthedocs.io>`_".format(opt, opt)
         else:
            link = self.Q1 + opt + self.Q2
         line = line.replace(replace, link)

      return line

   #
   # description type (dtype): 0 - section, 1 - option, 2 - example, 3 - action
   #
   def create_description(self, desc, secid, dtype):
      """Parse *desc* into typed paragraphs and render each as RST.

      Detects paragraph type by inspecting leading lines:

      * A line ending with ``:`` followed by a blank line triggers a table
        block (``ptype=1``).
      * A line matching the synopsis pattern (docname followed by option
        flags) triggers a synopsis block (``ptype=2``).
      * All other non-blank lines form normal paragraphs (``ptype=0``).

      Args:
         desc  (str): Raw multi-line description string.
         secid (str): Section ID for link resolution.
         dtype (int): Description type (0=section, 1=option, 2=example, 3=action).

      Returns:
         str: RST-formatted description content.
      """
      if desc == "\n": return ''
      ptype = 0   # paragraph type: 0 - normal, 1 - table, 2 = synopsis
      content = ''
      cnt = 0
      alllines = desc.split('\n')
      lines = []
      for line in alllines:
         if re.match(r'^\s*\S', line):
            lines.append(line)
            cnt += 1
            if ptype == 0:
               if re.search(r':\s*$', line):
                  content += self.create_paragraph(lines, cnt, secid, dtype)
                  lines = []
                  ptype = 1
                  cnt = 0
               elif cnt == 1 and re.match(r'^\s+%s\s(-|\[|[a-z]\d{6}|[A-Z]{2}\s)' % self.DOCS['DOCNAM'], line):
                  ptype = 2
         elif cnt > 0:
            content += self.create_desc_content(lines, cnt, secid, dtype, ptype)
            cnt = ptype = 0
            lines = []

      if cnt > 0:
         content += self.create_desc_content(lines, cnt, secid, dtype, ptype)

      return content

   #
   # create description content according to the paragraph type
   #
   def create_desc_content(self, lines, cnt, secid, dtype, ptype):
      """Dispatch a collected block of lines to the appropriate RST renderer.

      Args:
         lines (list[str]): Non-empty lines forming one paragraph/block.
         cnt   (int):       Number of lines (``len(lines)``).
         secid (str):       Section ID for link resolution.
         dtype (int):       Description type (0-3).
         ptype (int):       Paragraph type: 0=normal, 1=table, 2=synopsis.

      Returns:
         str: RST-formatted block content.
      """
      if ptype == 1:
         return self.create_table(lines, cnt, secid)
      elif ptype == 2:
         return self.create_synopsis(lines, cnt, secid, dtype)
      else:
         return self.create_paragraph(lines, cnt, secid, dtype)

   #
   # description type (dtype): 0 - section, 1 - option, 2 - example, 3 - action
   #
   def create_paragraph(self, lines, cnt, secid, dtype):
      """Render a normal prose paragraph as RST.

      Special handling:

      * ``dtype=2`` with a ``<<Content ...>>`` header line: renders the
        remaining lines as a verbatim content block.
      * ``dtype=3``: prefixes "Mode options that…" lines with a ``.. _mode<secid>:``
        anchor and "Use Info option -FN…" lines with a ``.. _field:`` anchor.

      Args:
         lines (list[str]): Lines forming the paragraph.
         cnt   (int):       Number of lines.
         secid (str):       Section ID for link resolution.
         dtype (int):       Description type (0=section, 1=option, 2=example,
                            3=action).

      Returns:
         str: RST paragraph text terminated by a blank line.
      """
      doreplace = 1
      content = ""
      line0 = lines[0]
      normal = 1
      if dtype == 2:
         ms = re.match(r'^<<(Content .*)>>$', line0)
         if ms:   # input files for examples
            content += ms.group(1) + ":\n\n.. code-block:: none\n\n"
            normal = 0
            for i in range(1, cnt):
               line = lines[i]
               if doreplace and line.find('<:>') > -1 and not re.match(r'^[A-Z]\w+<:>[A-Z]\w+<:>', line):
                  doreplace = 0
               if doreplace:
                  content += ' '+self.replace_option_link(line, secid, 0) + "\n"
               else:
                  content += ' '+line + "\n"
                  if re.match(r'^\[\w+\]$', line): doreplace = 1
            content += "\n"
      if normal:   # normal paragraph
         ii = 0
         if dtype == 3:
            if re.match(r'^\s*Mode options* that ', line0):
               content += f".. _mode{secid}:\n\n" + self.replace_option_link(line0, secid, 0).strip() + "\n"
               ii = 1
         for i in range(ii, cnt):
            line = lines[i]
            content += self.replace_option_link(line, secid, 0).strip() + "\n"
         content += "\n"

      return content

   #
   # create table rst content
   #
   def create_table(self, lines, cnt, secid):
      """Render a tabular block as RST.

      Detects three sub-formats:

      * Lines ending with ``=>`` → RST line block (``|``).
      * Lines split on `` - `` (key-value pairs) → ``.. list-table::`` directive.
      * All other lines split on 2+ spaces → RST simple table.

      Args:
         lines (list[str]): Lines forming the table block (after the header ``:`` line).
         cnt   (int):       Number of lines.
         secid (str):       Section ID for link resolution.

      Returns:
         str: RST-formatted table or list content.
      """
      line0 = lines[0]
      ms = re.match(r'^\s+-\s+(.*)', line0)
      if ms:
         content = "* " + self.replace_option_link(ms.group(1), secid, 1)
         for i in range(1, cnt):
            line = lines[i]
            ms = re.match(r'^\s+-\s+(.*)', line)
            if ms:
               content += "\n* " + self.replace_option_link(ms.group(1), secid, 1)
            else:
               
               content += " " + self.replace_option_link(line, secid, 1).lstrip()
         content += "\n\n"
      elif re.search(r'=>$', line0):
#         line = re.sub(r'={1,}', '=', line0)
         content = "| {}\n".format(line0)
         for i in range(1, cnt):
            line = lines[i]
#            line = re.sub(r'={2,}', '=', line)
            content += "| {}\n".format(line)
         content += "\n"
      else:
         if re.search(r'\S\s+-\s+\S', line0):
            # Two-column key-value table rendered as a list-table directive.
            # Use prev_vals to accumulate multi-line values: append the
            # previous row only when the next key-value row is encountered,
            # so continuation lines can extend the previous row's value.
            rows = []
            prev_vals = None
            for i in range(cnt):
               line = lines[i].lstrip()
               ms = re.match(r'^(.*\S)\s+-\s+(\S.*)$', line)
               if ms:
                  if prev_vals:
                     rows.append(tuple(prev_vals))
                  col0 = ms.group(1)
                  col1 = self.replace_option_link(ms.group(2), secid, 1)
                  if re.match(r'^-', col0):
                     col0 = self.replace_option_link(col0, secid, 1)
                  else:
                     col0 = self.get_title_link(col0)
                  prev_vals = [col0, col1]
               elif prev_vals:
                  prev_vals[1] += " " + self.replace_option_link(line, secid, 1)
            if prev_vals:
               rows.append(tuple(prev_vals))
            content = self.build_rst_list_table(rows)
         else:
            # multi-column table split on 2+ spaces
            rows = []
            for i in range(cnt):
               line = lines[i].strip()
               vals = re.split(r'\s{2,}', self.replace_option_link(line, secid, 1))
               rows.append(vals)
            content = self.build_rst_simple_table(rows) + "\n"

      return content

   #
   # build a two-column rst list-table
   #
   def build_rst_list_table(self, rows):
      """Render *rows* as an RST ``.. list-table::`` directive.

      Args:
         rows (list[tuple[str, str]]): Sequence of (key, value) pairs.

      Returns:
         str: RST list-table directive string, or ``''`` if *rows* is empty.
      """
      if not rows: return ""
      content = ".. list-table::\n   :widths: auto\n   :header-rows: 0\n\n"
      for col0, col1 in rows:
         if col0[0] == '-': col0 = col0[1:]
         content += "   * - {}\n".format(col0)
         if col1[0] == '-': col1 = col1[1:]
         content += "     - {}\n".format(col1)
      content += "\n"
      return content

   #
   # build a multi-column rst simple table
   #
   def build_rst_simple_table(self, rows):
      """Render *rows* as an RST simple (grid-free) table.

      Column widths are computed from the widest cell in each column, with a
      minimum width of 1 to guarantee valid RST ``=`` separators.

      Args:
         rows (list[list[str]]): Rows of cell strings; rows may have
                                 varying numbers of columns.

      Returns:
         str: RST simple table string, or ``''`` if *rows* is empty.
      """
      if not rows: return ""
      ncols = max(len(r) for r in rows)
      widths = [0] * ncols
      for row in rows:
         for j, val in enumerate(row):
            if j < ncols:
               widths[j] = max(widths[j], len(val), 1)
      content = ".. list-table::\n   :widths: auto\n   :header-rows: 1\n"
      for row in rows:
         if len(row) == 1:
            content += " " + row[0]
            continue
         v = row[0]
         if len(v) > 1 and v[0] == '-': v = v[1:]
         content += "\n   * - " + v
         for c in range(1, ncols):
            v = row[c]
            if len(v) > 1 and v[0] == '-': v = v[1:]
            content += "\n     - " + v

      return content + "\n"

   #
   # description type (dtype): 0 - section, 1 - option, 2 - example, 3 - action
   #
   def create_synopsis(self, lines, cnt, secid, dtype):
      """Render a command synopsis block as RST line blocks.

      Lines matching the document name are formatted as
      ``| **docname** <args>``.  Lines containing `` or `` (case-insensitive)
      are rendered as ``**Or**`` separators.  All other lines are indented
      continuation lines.

      Args:
         lines (list[str]): Lines forming the synopsis block.
         cnt   (int):       Number of lines.
         secid (str):       Section ID for link resolution.
         dtype (int):       Description type (0-3).

      Returns:
         str: RST line-block synopsis content.
      """
      content = ""

      for i in range(cnt):
         line = self.replace_option_link(lines[i], secid, 2, dtype)
         ms = re.match(r'^\s*{}\s+(.+)$'.format(self.DOCS['DOCNAM']), line)
         if ms:
            content += "| {}{}{} {}\n".format(self.Q1, self.DOCS['DOCNAM'], self.Q2, ms.group(1))
         else:
            content += "|  "+line+"\n"
      content += "\n"

      return content

   #
   # get a short option name by searching hashes OPTS and ALIAS
   #
   def get_short_option(self, p):
      """Resolve *p* to a canonical two-letter option short name.

      Checks ``self.options`` directly (for already-seen two-letter codes),
      then searches ``self.OPTS`` long names and ``self.ALIAS`` alias lists
      using case-insensitive matching.

      Args:
         p (str): Option name to look up (short, long, or alias).

      Returns:
         str: Canonical two-letter option short name.

      Raises:
         PgLOG error (LGWNEX) if *p* cannot be resolved.
      """
      plen = len(p)
      if plen == 2 and p in self.options: return p

      for opt in self.OPTS:
         if re.match(r'^{}$'.format(self.OPTS[opt][1]), p, re.I): return opt

      for opt in self.ALIAS:
         for alias in self.ALIAS[opt]:
            if re.match(r'^{}$'.format(alias), p, re.I): return opt

      self.pglog("{} - unknown option for {}".format(p, self.DOCS['DOCNAM']), self.LGWNEX)

   #
   # replace with rst link for a given section title
   #
   def get_title_link(self, title):
      """Return an RST hyperlink for *title* if it matches a known section, else *title* unchanged.

      Args:
         title (str): Section title text to look up.

      Returns:
         str: RST `` `title <sectionN>`_ `` link, or *title* if not found.
      """
      ltitle = title.lower()
      if ltitle == "info options": ltitle = 'information options'
      for section in self.sections:
         if ltitle == section['title'].lower():
            return ":ref:`{} <section{}>`".format(title, section['secid'])

      return title

   #
   # get section for given section id
   #
   def get_section(self, secid):
      """Return the section dict for *secid*, or abort with a log error if not found.

      Args:
         secid (str): Dotted section identifier to look up.

      Returns:
         dict: Matching section dict.

      Raises:
         PgLOG error (LGWNEX) if *secid* is not present in ``self.sections``.
      """
      for section in self.sections:
         if section['secid'] == secid: return section

      self.pglog("Unknown Section ID {}".format(secid), self.LGWNEX)

   def load_opts_alias(self, docname):
      """Import ``rda_python_<docname>.<docname>`` and return its ``(OPTS, ALIAS, origin)`` triple.

      Resolution order for OPTS / ALIAS:

      1. The first class *defined in that module* that carries ``OPTS``
         as a class-level attribute.
      2. Module-level ``OPTS`` / ``ALIAS`` attributes (fallback when no
         qualifying class is found).

      ``ALIAS`` is optional; an empty dict is returned when not found.

      The ``origin`` value is the absolute path of the directory that contains
      ``<docname>.py`` (i.e. ``rda_python_<docname>/``), derived from
      ``mod.__file__``.  It is intended to be assigned to
      ``PgRST.DOCS['ORIGIN']`` so that :meth:`PgRST.parse_docs` looks for the
      ``.usg`` source file in the same location as the document module.

      Args:
         docname (str): Short document name used to build the module path
                        ``rda_python_<docname>.<docname>``.

      Returns:
         tuple[dict, dict, str]: ``(OPTS, ALIAS, origin)`` where *origin* is
         the absolute directory path of the imported module file.

      Raises:
         SystemExit: via :func:`PgLOG.pglog` (``LGWNEX``) if the module
                     cannot be imported or ``OPTS`` cannot be found.
      """
      modname = "rda_python_{}.{}".format(docname, docname)
      try:
         mod = importlib.import_module(modname)
      except ImportError as exc:
         self.pglog(
            "Cannot import module '{}': {}".format(modname, exc),
            self.LGWNEX,
         )

      # Derive ORIGIN from the module's own file path.
      origin = op.dirname(op.abspath(mod.__file__))

      # 1. Find the first class defined in this module and read OPTS / ALIAS from it.
      cls = next(
         (obj for _, obj in inspect.getmembers(mod, inspect.isclass)
          if obj.__module__ == modname),
         None,
      )

      if cls is not None:
         obj   = cls()
         opts  = getattr(obj, 'OPTS',  None)
         alias = getattr(obj, 'ALIAS', None)
      else:
         # 2. Fall back to module-level attributes when no class is found.
         opts  = getattr(mod, 'OPTS',  None)
         alias = getattr(mod, 'ALIAS', None)

      if opts is None:
         self.pglog(
            "Module '{}' does not define OPTS (checked class and "
            "module level)".format(modname),
            self.LGWNEX,
         )

      # ALIAS is optional; default to empty dict.
      if alias is None:
         alias = {}

      return opts, alias, origin

   def load_opts_alias_from_pyfile(self, pyfile):
      """Load OPTS and ALIAS from a Python file given by path.

      Uses ``importlib.util.spec_from_file_location`` to import the file
      without requiring it to be on ``sys.path``.  Resolution order mirrors
      :meth:`load_opts_alias`: class attributes first, then module-level.

      Args:
         pyfile (str): Absolute or relative path to the Python source file.

      Returns:
         tuple[dict, dict]: ``(OPTS, ALIAS)`` where ALIAS defaults to ``{}``
         when not found.

      Raises:
         SystemExit: via :func:`PgLOG.pglog` (``LGWNEX``) if the file
                     cannot be loaded or ``OPTS`` cannot be found.
      """
      pyfile  = op.abspath(pyfile)
      modname = op.splitext(op.basename(pyfile))[0]
      try:
         spec = importlib.util.spec_from_file_location(modname, pyfile)
         mod  = importlib.util.module_from_spec(spec)
         spec.loader.exec_module(mod)
      except Exception as exc:
         self.pglog(
            "Cannot load module from '{}': {}".format(pyfile, exc),
            self.LGWNEX,
         )

      cls = next(
         (obj for _, obj in inspect.getmembers(mod, inspect.isclass)
          if obj.__module__ == modname),
         None,
      )

      if cls is not None:
         obj   = cls()
         opts  = getattr(obj, 'OPTS',  None)
         alias = getattr(obj, 'ALIAS', None)
      else:
         opts  = getattr(mod, 'OPTS',  None)
         alias = getattr(mod, 'ALIAS', None)

      if opts is None:
         self.pglog(
            "File '{}' does not define OPTS (checked class and "
            "module level)".format(pyfile),
            self.LGWNEX,
         )

      if alias is None:
         alias = {}

      return opts, alias


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    """Entry point for command-line usage of pg_rst.py."""
    parser = argparse.ArgumentParser(
        description=(
            "Convert a .usg help document to reStructuredText (.rst) using RST templates. "
            "OPTS and ALIAS are loaded from rda_python_<docname>/<docname>.py "
            "(or from --pyfile if given): "
            "the module is searched first for a class that carries both as class "
            "attributes, then for module-level OPTS/ALIAS variables."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'docname',
        nargs='?',
        default=None,
        help=(
            "Short document name, e.g. 'dsarch' or 'dsupdt'.  "
            "Required unless --usgfile is given, in which case the name is "
            "derived from the .usg filename by removing the extension."
        ),
    )
    parser.add_argument(
        '-u', '--usgfile',
        default=None,
        metavar='FILE',
        help=(
            "Path to the .usg source document.  When given, docname is derived "
            "from the filename by removing the .usg extension, and ORIGIN is set "
            "to the directory containing the file."
        ),
    )
    parser.add_argument(
        '-p', '--pyfile',
        default=None,
        metavar='FILE',
        help=(
            "Path to a Python file that defines OPTS (and optionally ALIAS) "
            "either at module level or as class attributes.  When given, the "
            "module-import convention (rda_python_<docname>/<docname>.py) is "
            "bypassed."
        ),
    )
    parser.add_argument(
        '--docdir',
        default=None,
        metavar='DIR',
        help=(
            "Root directory under which the per-document RST output directory "
            "is created (default: current working directory).  "
            "The final output lands in <docdir>/<docname>/."
        ),
    )
    args = parser.parse_args()

    pg = PgRST()

    # Resolve docname: explicit arg takes priority, then derive from --usgfile.
    if args.docname:
        docname = args.docname
    elif args.usgfile:
        docname = op.splitext(op.basename(args.usgfile))[0]
    else:
        parser.error("docname is required when --usgfile is not given")

    # Set ORIGIN from --usgfile directory when provided.
    if args.usgfile:
        pg.DOCS['ORIGIN'] = op.dirname(op.abspath(args.usgfile)) or os.getcwd()

    # Load OPTS/ALIAS: from --pyfile path or via module-import convention.
    if args.pyfile:
        opts, alias = pg.load_opts_alias_from_pyfile(args.pyfile)
    else:
        opts, alias, origin = pg.load_opts_alias(docname)
        if not args.usgfile:
            pg.DOCS['ORIGIN'] = origin

    if args.docdir is not None:
        pg.DOCS['DOCDIR'] = args.docdir
    pg.process_docs(docname, opts, alias)

if __name__ == "__main__":
    main()
