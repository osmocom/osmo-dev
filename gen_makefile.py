#!/usr/bin/env python3
'''
Generate a top-level makefile that builds the Osmocom 2G + 3G network components.

  ./gen_makefile.py projects.deps [configuration.opts] [-o Makefile.output]

Configured by text files:

  *.deps: whitespace-separated listing of
    project_name depends_on_project_1 depends_on_project_2 ...

  *.opts: whitespace-separated listing of
    project_name --config-opt-1 --config-opt-2 ...

Thus it is possible to choose between e.g.
- 2G+3G or 2G-only by picking a different projects_and_deps.conf,
- and between building each of those with or without mgcp transcoding support
  by picking a different configure_opts.conf.

From the Makefile nature, the dependencies extend, no need to repeat common deps.

When this script is done, a Makefile has been generated that allows you to
build all projects at once by issuing 'make', but also to refresh only parts of
it when some bits in the middle have changed. The makefile keeps local progress
marker files like .make.libosmocore.configure; if such progress marker is
removed or becomes outdated, that step and all dependent ones are re-run.
This is helpful in daily hacking across several repositories.
'''

import sys
import os
import argparse

parser = argparse.ArgumentParser(epilog=__doc__, formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument('projects_and_deps_file',
  help='''Config file containing projects to build and
dependencies between those''')

parser.add_argument('configure_opts_file',
  help='''Config file containing project name and
./configure options''',
  default=None, nargs='?')

parser.add_argument('-m', '--make-dir', dest='make_dir',
  help='''Place Makefile in this dir (default: create
a new dir named after deps and opts files).''')

parser.add_argument('-s', '--src-dir', dest='src_dir', default='./src',
  help='Parent dir for all git clones.')

parser.add_argument('-b', '--build-dir', dest='build_dir',
  help='''Parent dir for all build trees (default:
directly in the make-dir).''')

parser.add_argument('-u', '--url', dest='url', default='ssh://go',
  help='''git clone base URL. Default is 'ssh://go',
e.g. add this to your ~/.ssh/config:
  host go
  hostname gerrit.osmocom.org
  port 29418
Alternatively pass '-u git://git.osmocom.org'.''')

parser.add_argument('-o', '--output', dest='output', default='Makefile',
  help='''Makefile filename (default: 'Makefile').''')

parser.add_argument('-j', '--jobs', dest='jobs', default='9',
  help='''-j option to pass to 'make'.''')

args = parser.parse_args()


def read_projects_deps(path):
  'Read deps config and return tuples of (project_name, which-other-to-build-first).'
  l = []
  for line in open(path):
    line = line.strip()
    if not line or line.startswith('#'):
      continue
    tokens = line.split()
    l.append((tokens[0], tokens[1:]))
  return l

def read_configure_opts(path):
  'Read config opts file and return tuples of (project_name, config-opts).'
  if not path:
    return {}
  return dict(read_projects_deps(path))

def gen_make(proj, deps, configure_opts, jobs, make_dir, src_dir, build_dir, url):
  src_proj = os.path.join(src_dir, proj)
  build_proj = os.path.join(build_dir, proj)

  make_to_src = os.path.relpath(src_dir, make_dir)
  make_to_src_proj = os.path.relpath(src_proj, make_dir)
  make_to_build_proj = os.path.relpath(build_proj, make_dir)
  build_to_src = os.path.relpath(src_proj, build_proj)

  if configure_opts:
    configure_opts_str = ' '.join(configure_opts)
  else:
    configure_opts_str = ''

  # special hack for libsmpp34: cannot build in parallel
  if proj == 'libsmpp34':
    jobs = 1

  return r'''
### {proj} ###

.make.{proj}.clone:
	@echo "\n\n\n===== $@\n"
	test -d {src} || mkdir -p {src}
	test -d {src_proj} || git -C {src} clone {url}/{proj}
	touch $@

.make.{proj}.autoconf: .make.{proj}.clone {src_proj}/configure.ac
	@echo "\n\n\n===== $@\n"
	cd {src_proj}; autoreconf -fi
	touch $@
	
.make.{proj}.configure: .make.{proj}.autoconf {deps_installed}
	@echo "\n\n\n===== $@\n"
	-chmod -R ug+w {build_proj}
	-rm -rf {build_proj}
	mkdir -p {build_proj}
	cd {build_proj}; {build_to_src}/configure {configure_opts}
	touch $@

.make.{proj}.last_edited:
	touch $@

.PHONY: .make.{proj}.detect_edits
.make.{proj}.detect_edits:
	@test -z "$(shell find {src_proj} -newer .make.{proj}.last_edited -name "*.[hc]")" || (touch .make.{proj}.last_edited; echo {proj} edited)

.make.{proj}.build: .make.{proj}.configure .make.{proj}.last_edited
	@echo "\n\n\n===== $@\n"
	$(MAKE) -C {build_proj} -j {jobs} check
	touch $@

.make.{proj}.install: .make.{proj}.build
	@echo "\n\n\n===== $@\n"
	$(MAKE) -C {build_proj} install
	touch $@
'''.format(
    url=url,
    proj=proj,
    jobs=jobs,
    src=make_to_src,
    src_proj=make_to_src_proj,
    build_proj=make_to_build_proj,
    build_to_src=build_to_src,
    deps_installed=' '.join(['.make.%s.install' % d for d in deps]),
    configure_opts=configure_opts_str)


projects_deps = read_projects_deps(args.projects_and_deps_file)
configure_opts = read_configure_opts(args.configure_opts_file)

make_dir = args.make_dir
if not make_dir:
  make_dir = 'make-%s-%s' % (args.projects_and_deps_file, args.configure_opts_file)

if not os.path.isdir(make_dir):
  os.makedirs(make_dir)

build_dir = args.build_dir
if not build_dir:
  build_dir = make_dir

output = os.path.join(make_dir, args.output)
print('Writing to %r' % output)

with open(output, 'w') as out:
  out.write('# This Makefile was generated by %s\n' % os.path.basename(sys.argv[0]))

  # convenience: add a regen target that updates the generated makefile itself
  out.write(r'''
default: all

# regenerate this Makefile, in case the deps or opts changed
.PHONY: regen
regen:
	{script} {projects_and_deps} {configure_opts} -m {make_dir} -o {makefile} -s {src_dir} -b {build_dir}

'''.format(
    script=os.path.relpath(sys.argv[0], make_dir),
    projects_and_deps=os.path.relpath(args.projects_and_deps_file, make_dir),
    configure_opts=os.path.relpath(args.configure_opts_file, make_dir),
    make_dir='.',
    makefile=args.output,
    src_dir=os.path.relpath(args.src_dir, make_dir),
    build_dir=os.path.relpath(build_dir, make_dir),
    ))

  # now the actual useful build rules
  out.write('all: \\\n\t' + ' \\\n\t'.join([ '.make.%s.detect_edits .make.%s.install' % (p,p) for p, d in projects_deps ]) + '\n\n')

  for proj, deps in projects_deps:
    out.write(gen_make(proj, deps, configure_opts.get(proj), args.jobs,
                       make_dir, args.src_dir, build_dir, args.url))
