#!/usr/bin/env python

import sys, subprocess, re

if len(sys.argv) < 2:
  print("Usage: %s <git_dir> [...]\nThis is mostly here for helping the 'st' script." % sys.argv[0])
  exit(1)

interesting_branch_names = [ 'master', 'sysmocom/iu', 'sysmocom/sccp', 'aper-prefix-onto-upstream' ]

re_branch_name = re.compile('^..([^ ]+) .*')
re_ahead = re.compile('ahead [0-9]+|behind [0-9]+')

def branch_name(line):
  m = re_branch_name.match(line)
  return m.group(1)

interesting = []

def do_one_git(git_dir):
  global interesting
  branch_strs = subprocess.check_output(('git', '-C', git_dir, 'branch', '-vv')).decode().splitlines()
  interesting_branches = []

  for line in branch_strs:
    name = branch_name(line)
    current_branch = False
    if line.startswith('*'):
      current_branch = True
    elif name not in interesting_branch_names:
      continue
    ahead = re_ahead.findall(line)
    if not ahead and not current_branch:
      continue
    ahead = [x.replace('ahead ', '+').replace('behind ', '-') for x in ahead]
    br = (current_branch, name, ahead)
    if current_branch:
      interesting_branches.insert(0, br)
    else:
      interesting_branches.append(br)

  status = subprocess.check_output(('git', '-C', git_dir, 'status')).decode()
  has_mods = 'modified:' in status

  interesting.append((git_dir, has_mods, interesting_branches))


for git_dir in sys.argv[1:]:
  do_one_git(git_dir)


first_col = max([len(git_dir) for git_dir, _, _ in interesting])
first_col_fmt = '%' + str(first_col) + 's'

for git_dir, has_mods, interesting_branches in interesting:
  strs = [first_col_fmt % git_dir,]
  if has_mods:
    strs.append('MODS')
  for current_branch, name, ahead in interesting_branches:
    br = []
    br.append(name)
    if ahead:
      br.append('[%s]' % '|'.join(ahead))
    strs.append(''.join(br))

  print(' '.join(strs))

# vim: shiftwidth=2 expandtab tabstop=2
