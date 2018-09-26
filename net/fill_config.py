#!/usr/bin/env python3
'''Take values from a config file and fill them into a set of templates.
Write the result to the current directory.'''

import os, sys, re, shutil
import argparse

def file_newer(path_a, than_path_b):
  return os.path.getmtime(path_a) > os.path.getmtime(than_path_b)

LAST_LOCAL_CONFIG_FILE = '.last_config'
LAST_TMPL_DIR = '.last_templates'

parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('sources', metavar='SRC', nargs='*',
                    help='Pass both a template directory and a config file.')
parser.add_argument('-s', '--check-stale', dest='check_stale', action='store_true',
                    help='only verify age of generated files vs. config and templates.'
                    ' Exit nonzero when any source file is newer. Do not write anything.')

args = parser.parse_args()

local_config_file = None
tmpl_dir = None

for src in args.sources:
  if os.path.isdir(src):
    if tmpl_dir is not None:
      print('Error: only one template dir permitted. (%r vs. %r)' % (tmpl_dir, src))
    tmpl_dir = src
  elif os.path.isfile(src):
    if local_config_file is not None:
      print('Error: only one config file permitted. (%r vs. %r)' % (local_config_file, src))
    local_config_file = src

if local_config_file is None and os.path.isfile(LAST_LOCAL_CONFIG_FILE):
  local_config_file = open(LAST_LOCAL_CONFIG_FILE).read().strip()

if tmpl_dir is None and os.path.isfile(LAST_TMPL_DIR):
  tmpl_dir = open(LAST_TMPL_DIR).read().strip()

if not tmpl_dir or not os.path.isdir(tmpl_dir):
  print("Template dir does not exist: %r" % tmpl_dir)
  exit(1)

if not local_config_file or not os.path.isfile(local_config_file):
  print("No such config file: %r" % local_config_file)
  exit(1)

local_config_file = os.path.realpath(local_config_file)
tmpl_dir = os.path.realpath(tmpl_dir)

print('using config file %r\non templates %r' % (local_config_file, tmpl_dir))

with open(LAST_LOCAL_CONFIG_FILE, 'w') as last_file:
  last_file.write(local_config_file)
with open(LAST_TMPL_DIR, 'w') as last_file:
  last_file.write(tmpl_dir)

# read in variable values from config file
local_config = {}

line_nr = 0
for line in open(local_config_file):
  line_nr += 1
  line = line.strip('\n')

  if line.startswith('#'):
    continue

  if not '=' in line:
    if line:
      print("Error: %r line %d: %r" % (local_config_file, line_nr, line))
      exit(1)
    continue

  split_pos = line.find('=')
  name = line[:split_pos]
  val = line[split_pos + 1:]

  if val.startswith('"') and val.endswith('"'):
    val = val[1:-1]

  if name in local_config:
    print("Error: duplicate identifier in %r line %d: %r" % (local_config_file, line_nr, line))
  local_config[name] = val

# replace variable names with above values recursively
replace_re = re.compile('\$\{([A-Za-z0-9_]*)\}')
command_re = re.compile('\$\{([A-Za-z0-9_]*)\(([^)]*)\)\}')

idx = 0

def check_stale(src_path, target_path):
  if file_newer(src_path, target_path):
    print('Stale: %r is newer than %r' % (src_path, target_path))
    exit(1)

def insert_includes(tmpl, tmpl_dir, tmpl_src):
    for m in command_re.finditer(tmpl):
      cmd = m.group(1)
      arg = m.group(2)
      if cmd == 'include':
        include_path = os.path.join(tmpl_dir, arg)
        if not os.path.isfile(include_path):
          print('Error: included file does not exist: %r in %r' % (include_path, tmpl_src))
          exit(1)
        try:
          incl = open(include_path).read()
        except:
          print('Cannot read %r for %r' % (include_path, tmpl_src))
          raise
        if args.check_stale:
          check_stale(include_path, dst)

        # recurse, to follow the paths that the included bits come from
        incl = insert_includes(incl, os.path.dirname(include_path), include_path)

        tmpl = tmpl.replace('${%s(%s)}' % (cmd, arg), incl)
      else:
        print('Error: unknown command: %r in %r' % (cmd, tmpl_src))
        exit(1)
    return tmpl

for tmpl_name in sorted(os.listdir(tmpl_dir)):

  # omit "hidden" files
  if tmpl_name.startswith('.'):
    continue

  tmpl_src = os.path.join(tmpl_dir, tmpl_name)
  dst = tmpl_name

  if args.check_stale:
    check_stale(local_config_file, dst)
    check_stale(tmpl_src, dst)

  local_config['_fname'] = tmpl_name
  local_config['_name'] = os.path.splitext(tmpl_name)[0]
  local_config['_idx0'] = str(idx)
  idx += 1
  local_config['_idx1'] = str(idx)

  try:
    result = open(tmpl_src).read()
  except:
    print('Error in %r' % tmpl_src)
    raise

  while True:
    used_vars = set()

    result = insert_includes(result, tmpl_dir, tmpl_src)

    for m in replace_re.finditer(result):
      name = m.group(1)
      if not name in local_config:
        print('Error: undefined var %r in %r' % (name, tmpl_src))
        exit(1)
      used_vars.add(name)

    if not used_vars:
      break

    for var in used_vars:
      result = result.replace('${%s}' % var, local_config.get(var))

  if not args.check_stale:
    with open(dst, 'w') as dst_file:
      dst_file.write(result)
    shutil.copymode(tmpl_src, dst)

# vim: ts=2 sw=2 expandtab
