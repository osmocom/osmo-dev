#!/usr/bin/env python3

import os, sys, re, shutil

def get_arg(nr, default):
  if len(sys.argv) > nr:
    return sys.argv[nr]
  return default

local_config_file = os.path.realpath(get_arg(1, 'local_config'))
tmpl_dir = get_arg(2, 'tmpl')

if not os.path.isdir(tmpl_dir):
  print("Template dir does not exist: %r" % tmpl_dir)
  exit(1)

print('using config file %r\non templates %r' % (local_config_file, tmpl_dir))

# read in variable values from config file
local_config = {}

line_nr = 0
for line in open(local_config_file):
  line_nr += 1
  line = line.strip('\n')
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

print('config:\n\n' + '\n'.join('%s=%r' % (n,v) for n,v in local_config.items()))

# replace variable names with above values recursively
replace_re = re.compile('\$\{([A-Za-z0-9_]*)\}')
command_re = re.compile('\$\{([A-Za-z0-9_]*)\(([^)]*)\)\}')

idx = 0

for tmpl_name in sorted(os.listdir(tmpl_dir)):
  tmpl_src = os.path.join(tmpl_dir, tmpl_name)
  dst = tmpl_name

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
    for m in command_re.finditer(result):
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
        result = result.replace('${%s(%s)}' % (cmd, arg), incl)
      else:
        print('Error: unknown command: %r in %r' % (cmd, tmpl_src))
        exit(1)

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

  with open(dst, 'w') as dst_file:
    dst_file.write(result)

  shutil.copymode(tmpl_src, dst)

# vim: ts=2 sw=2 expandtab
