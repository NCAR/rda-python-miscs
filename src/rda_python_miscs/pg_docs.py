#
###############################################################################
#
#     Title : pg_docs.py
#    Author : Zaihua Ji,  zjiucar.edu
#      Date : 09/14/2020
#   Purpose : python library module to help convert text help documents into
#             html format with help of html templates
#
# Work File : $DSSHOME/lib/python/PgDOCS.py
#    Github : https://github.com/NCAR/rda-shared-libraries.git
#
###############################################################################
#
import os
import re
from os import path as op
import PgLOG
import PgUtil
import PgFile


class PgDOCS:

   Q0 = "'"
   Q1 = "<i><b>"
   Q2 = "</i></b>"

   EMLIST = {
      'dsarch' : 1,
      'msarch' : 1,
      'dsupdt' : 1,
      'dsrqst' : 1,
      'gatherxml' : 1,
      'pgconvert' : 1,
      'publish_filelist' : 1,
      'rcm' : 1,
      'dcm' : 1,
   }

   SEARCH = "(Action|Info|Mode|Multi-Value|Single-Value)"

   def __init__(self):
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
      # desc     - section decription
      # opts     - pointer to an array of included option short names
      self.sections = []

      # Option hash keyed by short option names and each is a hash itself
      # secid    - section ID the option belongs
      # name     - option long name
      # type     - option type, 0 - Mode, 1 - Info, 2 - Action
      # alias    - array of alias option names None if none
      # desc     - option decription
      # examples - array of example indices included for the option
      self.options = {}

      # Example array with each example pointing to a hash:
      # opt      - option short name the example belongs
      # title    - example title
      # desc     - example decription
      self.examples = []

      # global info to be used by the whole application
      self.DOCS = {
         'ORIGIN' : PgLOG.PGLOG['DSSHOME'] + "/dssdb/prog_usage", # directory to the original document
         'TMPDIR' : PgLOG.PGLOG['DSSHOME'] + "/lib/templates", # directory to find the templates
         'DCROOT' : None, # root directory to html documents
         'DOCDIR' : "", # directory to final html documents
         'DOCNAM' : "", # document name: dsarch, dsupdt, etc.
         'DOCTIT' : "", # document name in upper case letters
         'DOCLNK' : None,
      }

      self.LINKS = ['dsarch', 'dsupdt', 'dsrqst', 'dscheck']
      self.DOCS['DCROOT'] = PgLOG.get_environment("WEBROOT", PgLOG.PGLOG['DSSWEB']) + "/rdadocs"

   #
   # Function process_docs(docname: document name, 'dsarch', 'dsupdt'
   #                          opts: option hash defined for the document
   #                         alias: alias names for given opts)
   #
   def process_docs(self, docname, opts, alias):

      self.OPTS = opts
      self.ALIAS = alias

      self.parse_docs(docname)
      if not self.sections: PgLOG.pglog(docname + ": empty document", PgLOG.LGWNEX)

      self.DOCS['DOCNAM'] = docname
      if docname in self.LINKS: self.LINKS.remove(docname)
      self.DOCS['DOCLNK'] = r"({})".format('|'.join(self.LINKS))
      self.DOCS['DOCTIT'] = docname.upper()
      self.DOCS['DOCDIR'] = "{}/{}".format(self.DOCS['DCROOT'], docname)

      PgFile.change_local_directory(self.DOCS['DOCDIR'], PgLOG.LGWNEX)
      PgLOG.pglog("Write html document '{}' under {}".format(docname, self.DOCS['DOCDIR']), PgLOG.LOGWRN)

      if op.exists("index.html"):  # write index file once
         PgLOG.pglog("index.html exists already, delete first if needs to be regenerated", PgLOG.LOGWRN)
      else:
         self.write_index(self.sections[0])

      self.write_toc()

      for section in self.sections:
         self.write_section(section)

   #
   # parse the original document and return a array of sections,
   #
   def parse_docs(self, docname):

      docfile = "{}/{}.usg".format(self.DOCS['ORIGIN'], docname)
      PgLOG.pglog("Parsing info for Document '{}'".format(docname), PgLOG.LOGWRN)
      section = self.init_section('0', "Preface")
      option = example = None
      fh = open(docfile, 'r')
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

         # check and replace temporal pattern quotes
         while True:
            ms = re.search(r'(<([A-Z/\-\.]+)>)', line)
            if ms:
               line = line.replace(ms.group(1), "&lt{}&gt".format(ms.group(2)))
            else:
               break
         ms = re.match(r'^([\d\.]+)\s+(.+)$', line)
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
      fh.close()

      self.record_section(section, option, example)

      # check completion of options
      for opt in self.OPTS:
         if opt not in self.options:
            PgLOG.pglog("Missing option Entry -{} (-{}) in Document '{}'".format(opt, self.OPTS[opt][1], docname), PgLOG.LOGWRN)
      if self.sections:
         cnt = len(self.sections)
         s = 's' if cnt > 1 else ''
         PgLOG.pglog("{} Section{} gathered for '{}'".format(cnt, s, docname), PgLOG.LOGWRN)

   #
   # cache section information
   #
   def record_section(self, section, option, exmaple, nsecid=None, ntitle=None):

      if option or section['desc'] != "\n":
         if option: self.record_option(section, option, exmaple)
         self.sections.append(section)    # record section globally

      if nsecid: return self.init_section(nsecid, ntitle)

   #
   # cache option information
   #
   def record_option(self, section, option, example, nopt=None, ndesc=None):

      if option:
         if example: self.record_example(option, example)
         self.options[option['opt']] = option     # record option globally
         section['opts'].append(option['opt']) # record option short name in section

      if nopt: return self.init_option(section['secid'], nopt, ndesc)

   def record_example(self, option, example, ndesc=None):

      if example:
         ms = re.match(r'^(.*)\.\s*(.*)$', example['desc'])
         if ms:
            example['title'] = ms.group(1)
            example['desc'] = ms.group(2)
         option['exmidxs'].append(len(self.examples))   # record example index in option
         self.examples.append(example)     # record example globally

      if ndesc: return self.init_example(option['opt'], ndesc)

   #
   # initialize section dict
   #
   def init_section(self, secid, title):

      section = {
         'secid' : secid,
         'title' : title,
          'desc' : "",
         'level' : 0,
          'opts' : []
      }
      level = len(re.split(r'\.', secid))
      section['level'] = level
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

      option = {}
      types = ("Mode", "Info", "Info", "Action")

      if opt not in self.OPTS:
         PgLOG.pglog("{} -- option not defined for {}".format(opt, self.DOCS['DOCNAM']), PgLOG.LGWNEX)
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
   # initialize example dic
   #
   def init_example(self, opt, desc):

      example = {'opt' : opt, 'title' : "", 'desc' : desc.title() + "\n"}

      return example

   #
   # write the entry file: index.html
   #
   def write_index(self, section):

      hash = {'TITLE' : self.DOCS['DOCTIT'], 'SECID' : section['secid']}

      self.template_to_html("index", hash)

   #
   # write the table of contents: toc.html
   #
   def write_toc(self):

      hash = {'TITLE' : self.DOCS['DOCTIT'], 'TOC' : self.create_toc()}

      self.template_to_html("toc", hash)

   #
   # write a section html file
   #
   def write_section(self, section):

      hash = {}
      secid = section['secid']
      hash['TITLE'] = section['title']
      hash['SECID'] = secid
      hash['SECTION'] = self.create_section(section)

      self.template_to_html("section", hash, secid)

   #
   # convert template to html file
   #
   def template_to_html(self, template, hash, extra=None):

      tempfile = "{}/{}.temp".format(self.DOCS['TMPDIR'], template)
      if extra is None: extra = ""
      htmlfile = "{}/{}{}.html".format(self.DOCS['DOCDIR'], template, extra)

      tf = open(tempfile, 'r')
      hf = open(htmlfile, 'w')
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
               if key not in hash: PgLOG.pglog("{}: not defined at {}({}) {}".format(key, line, idx, tempfile), PgLOG.LGWNEX)
               if not hash[key]: PgLOG.pglog(key + ": empty content", PgLOG.LGWNEX)
               line = line.replace("__{}__".format(key), hash[key])
         hf.write(line + "\n")
         line = tf.readline()

      tf.close()
      hf.close()
      PgLOG.pglog("{}{}.html created from {}.temp".format(template, extra, template), PgLOG.LOGWRN)

   #
   # create a html file for table of contents
   #
   def create_toc(self):

      content = ""

      # table content for all sections
      lvl = 1
      for section in self.sections:
         secid = section['secid']
         if section['level'] > lvl:
            while lvl < section['level']:
               content += "<tr><td>&nbsp</td><td><table>\n"
               lvl += 1
         elif section['level'] < lvl:
            while lvl > section['level']:
               content += "</table></td></tr>\n"
               lvl -= 1
         lvl = section['level']
         content += (("<tr><td align=right><small>{}.</small></td>\n".format(secid)) +
                     ("<td align=left><a href=\"section{}.html\">".format(secid)) +
                     ("<small>{}</small></a></td></tr>\n".format(section['title'])))

      while lvl > 1:
         content += "</table></td></tr>\n"
         lvl -= 1

      # table content for appendix A of examples
      content += ("<tr><td align=right><small>A.</small></td>\n" +
                  "<td align=left><small>List of Examples</small></td></tr>\n" +
                  "<tr><td>&nbsp</td><td><table>\n")

      idx = 1 # used as exmaple index
      for example in self.examples:
         opt = example['opt']
         option = self.options[opt]
         secid = option['secid']
         content += (("<tr><td align=right><small>A.{}.</small></td>\n".format(idx)) +
                     ("<td ali gn=left><a href=\"section{}.html#e{}\">\n".format(secid, idx)) +
                     ("<small>{} Option -{} (-{})</small></a></td></tr>\n".format(option['type'], opt, option['name'])))
         idx += 1
      content += "</table></td></tr>\n"

      return content

   #
   # create a section html content
   #
   def create_section(self, section):

      secid = section['secid']
      content = self.create_description(section['desc'], secid, 0)

      for opt in section['opts']:
         content += self.create_option(opt, secid)

      return content

   #
   # create a option html content
   #
   def create_option(self, opt, secid):

      option = self.options[opt]
      content = self.create_option_name(opt, option)
      dtype = 3 if option['type'] == "Action" else 1
      content += self.create_description(option['desc'], secid, dtype)

      if 'exmidxs' in option:
         for idx in option['exmidxs']:
            content += self.create_example(idx, secid)

      return content

   #
   # create html text for option name
   #
   def create_option_name(self, opt, option):

      qopt = self.Q1 + opt + self.Q2
      nopt = self.Q1 + self.OPTS[opt][1] + self.Q2
      content = "<p><a name={}></a>{} Option -{} (-{})".format(opt, option['type'], qopt, nopt)
      if 'alias' in option:
         alias = option['alias']
         acnt = len(alias)
         s = 'es' if acnt > 1 else ''
         for i in range(acnt):
            content += "<tr>"
            if i == 0:
               content += " (Aliass: "
            else:
               content += ", "
            content += "-{}{}{}".format(self.Q1, alias[i], self.Q2)
         content += ")"

      content += " :</p>\n"

      return content

   #
   # create an example html content
   #
   def create_example(self, exmidx, secid):

      example = self.examples[exmidx]
      exm = exmidx+1
      content = "<br><a name=\"e{}\"></a>EXAMPLE {}. {}\n".format(exm, exm, example['title'])
      content += self.create_description(example['desc'], secid, 2)

      return content

   #
   # add links to other options
   def replace_option_link(self, line, csecid, ptype=None, dtype=None):

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
         if ms: opts = opts.insert(0, ms.groups())
      else:
         opts = re.findall(r'(^-\(*|\W-\(*)([a-zA-Z]{2,})(\W|$)', line)

      if opts is None: opts = []
      for optary in opts:
         opt = self.get_short_option(optary[1])
         pre = optary[0]
         after = optary[2]
         secid = self.options[opt]['secid']
         if secid == csecid:
            link = "#" + opt
         elif self.options[opt]['type'] == "Action":
            link =  "section{}.html".format(secid)
         elif ptype == 2 and opt == "FN":
            link = "#field"
         else:
            link = "section{}.html#{}".format(secid, opt)

         ms = re.search(r'-\(({}\|\w+)\)'.format(opt), line)
         if ms:
            if secid == csecid and ptype == 2: continue
            opt = ms.group(1)
            after = ')'

         replace = pre + opt + after
         if re.search(r'<!>', after): after = after.replace(r'<!>', '<&#33;>')
         link = "{}<a href=\"{}\">{}</a>{}".format(pre, link, opt, after)
         line = line.replace(replace, link)

      opts = re.findall(r'(^|\W){}( Options*\W|\W|$)'.format(self.SEARCH), line)
      for optary in opts:
         opt = optary[1]
         if not self.SECIDS[opt]: continue
         secid = self.SECIDS[opt]
         if secid == csecid or re.match(r'{}'.format(secid), csecid): continue
         pre = optary[0]
         after = optary[2]
         replace = pre + opt + after
         ms = re.search(r'(\sOptions*)\W', after)
         if ms:
            opt += ms.group(1)
            after = after.replace(ms.group(1), '')
         if ptype == 2 and re.search(r'Mode Options*', opt) and dtype == 3:
            link = "{}<a href=\"#mode\">{}</a>{}".format(pre, opt, after)
         else:
            link = "{}<a href=\"section{}.html\">{}</a>{}".format(pre, secid, opt, after)
         line = line.replace(replace, link)


      ms = re.search(r'(https*://\S+)(\.|\,)', line)
      if ms:
         replace = ms.group(1)
         link = "<a href=\"{}\" target=_top>{}</a>".format(replace, replace)
         line = line.replace(replace, link)

      pattern = r"{q}(\S+){q}".format(q=re.escape(self.Q0))
      opts = re.findall(pattern, line)
      for opt in opts:
         if opt not in self.EMLIST: continue  # quote only predefined ones
         replace = self.Q0+opt+self.Q0
         if re.search(self.DOCS['DOCLNK'], opt):
            link = "{}<a href=\"{}/internal/docs/{}\" target=_top>{}</a>{}".format(self.Q1, PgLOG.PGLOG['DSSURL'], opt, opt, self.Q2)
         else:
            link = self.Q1+opt+self.Q2
         line = line.replace(replace, link)

      return line

   #
   # description type (dtype): 0 - section, 1 - option, 2 - exmaple, 3 - action
   #
   def create_description(self, desc, secid, dtype):

      if desc == "\n": return ''
      ptype = 0   # paragraph type: 0 - normal, 1 - table, 2 - synopsys
      content = ''
      cnt = 0
      alllines = re.split(r'\n', desc)
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
               elif cnt == 1 and re.match(r'^\s+%s\s(-|\[|ds\d*|\d+|[A-Z]{2}\s)' % self.DOCS['DOCNAM'], line):
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

      if ptype == 1:
         return self.create_table(lines, cnt, secid)
      elif ptype == 2:
         return self.create_synopsis(lines, cnt, secid, dtype)
      else:
         return self.create_paragraph(lines, cnt, secid, dtype)

   #
   # description type (dtype): 0 - section, 1 - option, 2 - exmaple, 3 - action
   #
   def create_paragraph(self, lines, cnt, secid, dtype):

      doreplace = 1
      content = "<p>\n"
      line0 = lines[0]
      normal = 1
      if dtype == 2:
         ms = re.match(r'^<<(Content .*)>>$', line0)
         if ms:   # input files for examples
            content += ms.group(1) + ":\n</p><p>\n"
            normal = 0
            for i in range(1, cnt):
               line = lines[i]
               if doreplace and line.find('<:>') > -1 and not re.match(r'^[A-Z]\w+<:>[A-Z]\w+<:>', line):
                  doreplace = 0
               if doreplace:
                  content += self.replace_option_link(line, secid, 0) + "<br>\n"
               else:
                  content += line + "<br>\n"
                  if re.match(r'^\[\w+\]$', line): doreplace = 1
            content += "</p>\n"
      if normal:   # normal paragraph
         ii = 0
         if dtype == 3:
            if re.match(r'^\s*Mode options* that ', line0):
               content += "<a name=\"mode\"></a>" + self.replace_option_link(line0, secid, 0) + "\n"
               ii = 1
            elif re.match(r'^\s*Use Info option -FN ', line0):
               content += "<a name=\"field\"></a>" + self.replace_option_link(line0, secid, 0) + "\n"
               ii = 1
         for i in range(ii, cnt):
            line = lines[i]
            content += self.replace_option_link(line, secid, 0) + "\n"
         content += "</p>\n"

      return content

   #
   # create table html content
   #
   def create_table(self, lines, cnt, secid):

      line0 = lines[0]
      ms = re.match(r'^\s+-\s+(.*)', line0)
      if ms:   # create a list
         content = "<ol>\n<li>" + self.replace_option_link(ms.group(1), secid, 1) + "\n"
         for i in range(1, cnt):
            line = lines[i]
            ms = re.match(r'^\s+-\s+(.*)', line)
            if ms:
               content += "</li><li>" + self.replace_option_link(ms.group(1), secid, 1) + "\n"
            else:
               content += self.replace_option_link(line, secid, 1) + "\n"
         content += "</li></ol>\n"
      elif re.search(r'=>$', line0):
         line = re.sub(r'={1,}', '=', line0)
         content = "&nbsp&nbsp{}<br>\n".format(line)
         for i in range(1, cnt):
            line = lines[i]
            line = re.sub(r'={2,}', '=', line)
            content += "&nbsp&nbsp{}<br>\n".format(line)
      else:
         content = "<p><table border=2 cellspacing=0 cellpadding=2 bgcolor=\"#dfcfb3\">\n"
         if re.search(r'\S\s+-\s+\S', line0):
            vals = ['', '']
            for i in range(cnt):
               line = lines[i]
               line = line.lstrip()
               ms = re.match(r'^(.*\S)\s+-\s+(\S.*)$', line)
               if ms:
                  vals[0] = ms.group(1)
                  vals[1] = self.replace_option_link(ms.group(2), secid, 1)
                  if re.match(r'^-', vals[0]):
                     vals[0] = self.replace_option_link(vals[0], secid, 1)
                  else:
                     vals[0] = self.get_title_link(vals[0])
                  if i > 0: content += "<tr><td align=\"right\" nowrap>{}</td><td>{}</td></tr>\n".format(vals[0], vals[1])
               else:
                  vals[1] += "\n" + self.replace_option_link(line, secid, 1)
            content += "<tr><td align=\"right\" nowrap>{}</td><td>{}</td></tr>\n".format(vals[0], vals[1])
         else:
            for i in range(cnt):
               line = lines[i]
               vals = re.split(r'\s{2,}', self.replace_option_link(line, secid, 1))
               for val in vals:
                  content += "<td>{}</td>".format(val)
               content += "</tr>\n"
            content += "</table></p>\n"

      return content

   #
   # description type (dtype): 0 - section, 1 - option, 2 - exmaple, 3 - action
   #
   def create_synopsis(self, lines, cnt, secid, dtype):

      content = "<p><table cellspacing=10>\n"

      for i in range(cnt):
         line = self.replace_option_link(lines[i], secid, 2, dtype)
         if re.search(r'\sor\s', line, re.I):
            content += "<tr><td>Or</td><td>&nbsp</td></tr>"
         else:
            ms = re.match(r'^\s*{}\s+(.+)$'.format(self.DOCS['DOCNAM']), line)
            if ms:
               content += "<tr><td>{}{}{}</td><td>{}</td></tr>\n".format(self.Q1, self.DOCS['DOCNAM'], self.Q2, ms.group(1))
            else:
               content += "<tr><td>&nbsp</td><td>{}</td></tr>\n".format(line)
      content += "</table></p>\n"

      return content

   #
   # get a short option name by searching hashes OPTS and ALIAS
   #
   def get_short_option(self, p):

      plen = len(p)
      if plen == 2 and p in self.options: return p

      for opt in self.OPTS:
         if re.match(r'^{}$'.format(self.OPTS[opt][1]), p, re.I): return opt

      for opt in self.ALIAS:
         for alias in self.ALIAS[opt]:
             if re.match(r'^{}$'.format(alias), p, re.I): return opt

      PgLOG.pglog("{} - unknown option for {}".format(p, self.DOCS['DOCNAM']), PgLOG.LGWNEX)

   #
   # replace with link for a given section title
   #
   def get_title_link(self, title):

      for section in self.sections:
         if title == section['title']:
            return "<a href=\"section{}.html\">{}</a>".format(section['secid'], title)

      return title

   #
   # get section for given section id
   #
   def get_section(self, secid):

      for section in self.sections:
         if section['secid'] == secid: return section

      PgLOG.pglog("Uknown Section ID {}".format(secid), PgLOG.LGWNEX)
