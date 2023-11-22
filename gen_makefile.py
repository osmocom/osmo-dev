#!/usr/bin/env python3
'''
Generate a top-level makefile that builds the Osmocom 2G + 3G network components.

  ./gen_makefile.py [configure.opts [more.opts]] [-o Makefile.output]

Configured by text files:

  all.deps: whitespace-separated listing of
    project_name depends_on_project_1 depends_on_project_2 ...

  *.opts: whitespace-separated listing of
    project_name --config-opt-1 --config-opt-2 ...

Thus it is possible to choose between e.g.
- building each of those with or without mgcp transcoding support by adding or
  removing "transcoding.opts" from the command line

From the Makefile nature, the dependencies extend, no need to repeat common deps.

When this script is done, a Makefile has been generated that allows you to
build all projects at once by issuing 'make', but also to refresh only parts of
it when some bits in the middle have changed. The makefile keeps local progress
marker files like .make.libosmocore.configure; if such progress marker is
removed or becomes outdated, that step and all dependent ones are re-run.
This is helpful in daily hacking across several repositories.

Note that by default, this includes 'sudo ldconfig' calls following each
installation. You may want to permit your user to run 'sudo ldconfig' without
needing a password, e.g. by

  sudo sh -c "echo '$USER  ALL= NOPASSWD: /sbin/ldconfig' > /etc/sudoers.d/${USER}_ldconfig"

You can skip the 'sudo ldconfig' by issuing the --no-ldconfig option.

You can run 'ldconfig' without sudo by issuing the --ldconfig-without-sudo option.

By default, it is assumed that your user has write permission to /usr/local. If you
need sudo to install there, you may issue the --sudo-make-install option.

EXAMPLE:

  ./gen_makefile.py default.opts iu.opts -I -m build
  cd build
  make

'''

import sys
import os
import argparse
import multiprocessing

topdir = os.path.dirname(os.path.realpath(__file__))
all_deps_file = os.path.join(topdir, "all.deps")
all_urls_file = os.path.join(topdir, "all.urls")
all_buildsystems_file = os.path.join(topdir, "all.buildsystems")
parser = argparse.ArgumentParser(epilog=__doc__, formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument('configure_opts_files',
  help='''Config file containing project name and
./configure options''',
  nargs='*')

parser.add_argument('-m', '--make-dir', dest='make_dir',
  help='''Place Makefile in this dir (default: create
a new dir named after opts files).''')

parser.add_argument('-s', '--src-dir', dest='src_dir', default='./src',
  help='Parent dir for all git clones.')

parser.add_argument('-b', '--build-dir', dest='build_dir',
  help='''Parent dir for all build trees (default:
directly in the make-dir).''')

parser.add_argument('-u', '--url', dest='url', default='https://gerrit.osmocom.org',
  help='''git clone base URL. Default is 'https://gerrit.osmocom.org'.
e.g. with a config like this in your ~/.ssh/config:
  host go
  hostname gerrit.osmocom.org
  port 29418
you may pass '-u ssh://go' to be able to submit to gerrit.''')

parser.add_argument('-p', '--push-url', dest='push_url', default='',
  help='''git push-URL. Default is to not configure a separate push-URL.''')

parser.add_argument('-o', '--output', dest='output', default='Makefile',
  help='''Makefile filename (default: 'Makefile').''')

parser.add_argument('-j', '--jobs', dest='jobs', type=int,
  default=multiprocessing.cpu_count(), nargs='?',
  const=multiprocessing.cpu_count(),
  help='''-j option to pass to 'make'.''')

parser.add_argument('-I', '--sudo-make-install', dest='sudo_make_install',
  action='store_true',
  help='''run 'make install' step with 'sudo'.''')

parser.add_argument('-L', '--no-ldconfig', dest='no_ldconfig',
  action='store_true',
  help='''omit the 'sudo ldconfig' step.''')

parser.add_argument('--ldconfig-without-sudo', dest='ldconfig_without_sudo',
  action='store_true',
  help='''call just 'ldconfig', without sudo, which implies
root privileges (not recommended)''')

parser.add_argument('-c', '--no-make-check', dest='make_check',
  default=True, action='store_false',
  help='''do not 'make check', just 'make' to build.''')

parser.add_argument('--docker-cmd',
    help='''prefix configure/make/make install calls with this command (used by ttcn3.sh)''')

parser.add_argument('-g', '--build-debug', dest='build_debug', default=False, action='store_true',
    help='''set 'CFLAGS=-g' when calling src/configure''')

parser.add_argument('-a', '--auto-distclean', action='store_true',
    help='''run "make distclean" automatically if source directory already configured''')

args = parser.parse_args()

class listdict(dict):
  'a dict of lists { "a": [1, 2, 3],  "b": [1, 2] }'

  def add(self, name, item):
    l = self.get(name)
    if not l:
      l = []
      self[name] = l
    l.append(item)

  def extend(self, name, l):
    for v in l:
      self.add(name, v)

  def add_dict(self, d):
    for k,v in d.items():
      self.add(k, v)

  def extend_dict(self, d):
    for k,v in d.items():
      l = self.extend(k, v)

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

def read_projects_dict(path):
  'Read urls/buildsystems config and return dict {project_name: url, …}.'
  ret = {}
  for line in open(path):
    line = line.strip()
    if not line or line.startswith('#'):
      continue
    project, url = line.split()
    assert project not in ret, f"project '{project} found twice in {path}"
    ret[project] = url
  return ret

def read_configure_opts(path):
  'Read config opts file and return tuples of (project_name, config-opts).'
  if not path:
    return {}
  return dict(read_projects_deps(path))

def gen_makefile_clone(proj, src, src_proj, url, push_url):
  if proj == "osmocom-bb_layer23":
    return f'''
.make.{proj}.clone: .make.osmocom-bb.clone
	@echo -e "\\n\\n\\n===== $@\\n"
	test -L {src_proj} || ln -s osmocom-bb/src/host/layer23 {src_proj}
	touch $@
  '''

  if proj == "osmocom-bb_virtphy":
    return f'''
.make.{proj}.clone: .make.osmocom-bb.clone
	@echo -e "\\n\\n\\n===== $@\\n"
	test -L {src_proj} || ln -s osmocom-bb/src/host/virt_phy {src_proj}
	touch $@
  '''

  if proj == "simtrace2_host":
    return f'''
.make.{proj}.clone: .make.simtrace2.clone
	@echo -e "\\n\\n\\n===== $@\\n"
	test -L {src_proj} || ln -s simtrace2/host {src_proj}
	touch $@
  '''

  if proj in projects_urls:
    url = projects_urls[proj]
    cmd_set_push_url = "true"
  else:
    url = f"{url}/{proj}"
    push_url = f"{push_url}/{proj}"
    cmd_set_push_url = f'git -C "{src}/{proj}" remote set-url --push origin "{push_url}"'

  cmd_clone = f'git -C {src} clone --recurse-submodules "{url}" "{proj}"'

  return f'''
.make.{proj}.clone:
	@echo -e "\\n\\n\\n===== $@\\n"
	test -d {src} || mkdir -p {src}
	test -d {src_proj} || ( {cmd_clone} && {cmd_set_push_url} )
	sync
	touch $@
  '''

def gen_makefile_autoconf(proj, src_proj, distclean_cond):
  buildsystem = projects_buildsystems.get(proj, "autotools")
  if buildsystem == "autotools":
    return f'''
.make.{proj}.autoconf: .make.{proj}.clone {src_proj}/configure.ac
	if {distclean_cond}; then $(MAKE) {proj}-distclean; fi
	@echo -e "\\n\\n\\n===== $@\\n"
	-rm -f {src_proj}/.version
	cd {src_proj}; autoreconf -fi
	sync
	touch $@
    '''
  elif buildsystem == "meson":
    return ""
  else:
    assert False, f"unknown buildsystem: {buildsystem}"


def gen_makefile_configure(proj, deps_installed, distclean_cond, build_proj,
                           cflags, docker_cmd, build_to_src, configure_opts):
  buildsystem = projects_buildsystems.get(proj, "autotools")
  if buildsystem == "autotools":
    return f'''
.make.{proj}.configure: .make.{proj}.autoconf {deps_installed} $({proj}_configure_files)
	if {distclean_cond}; then $(MAKE) {proj}-distclean .make.{proj}.autoconf; fi
	@echo -e "\\n\\n\\n===== $@\\n"
	-chmod -R ug+w {build_proj}
	-rm -rf {build_proj}
	mkdir -p {build_proj}
	cd {build_proj}; {cflags}{docker_cmd}{build_to_src}/configure {configure_opts}
	sync
	touch $@
    '''
  elif buildsystem == "meson":
    return f'''
.make.{proj}.configure: .make.{proj}.clone {deps_installed} $({proj}_configure_files)
	@echo -e "\\n\\n\\n===== $@\\n"
	-chmod -R ug+w {build_proj}
	-rm -rf {build_proj}
	mkdir -p {build_proj}
	cd {build_proj}; {cflags}{docker_cmd}meson {build_to_src} .
	sync
	touch $@
    '''
  else:
    assert False, f"unknown buildsystem: {buildsystem}"

def gen_makefile_build(proj, distclean_cond, build_proj, docker_cmd, jobs,
                       check):
  buildsystem = projects_buildsystems.get(proj, "autotools")

  if buildsystem == "autotools":
    return f'''
.make.{proj}.build: .make.{proj}.configure $({proj}_files)
	if {distclean_cond}; then $(MAKE) {proj}-distclean .make.{proj}.configure; fi
	@echo -e "\\n\\n\\n===== $@\\n"
	{docker_cmd}$(MAKE) -C {build_proj} -j {jobs} {check}
	sync
	touch $@
    '''
  elif buildsystem == "meson":
    target = "test" if check else "compile"
    test_line = ""
    # TODO: currently tests don't pass in this env
    # if check:
    #   test_line = f"{docker_cmd}meson test -C {build_proj} -v"
    return f'''
.make.{proj}.build: .make.{proj}.configure $({proj}_files)
	@echo -e "\\n\\n\\n===== $@\\n"
	{docker_cmd}meson compile -C {build_proj} -j {jobs}
	{test_line}
	sync
	touch $@
    '''
  else:
    assert False, f"unknown buildsystem: {buildsystem}"

def gen_makefile_install(proj, docker_cmd, sudo_make_install, build_proj,
                         no_ldconfig, sudo_ldconfig):
  buildsystem = projects_buildsystems.get(proj, "autotools")
  if buildsystem == "autotools":
    return f'''
.make.{proj}.install: .make.{proj}.build
	@echo -e "\\n\\n\\n===== $@\\n"
	{docker_cmd}{sudo_make_install}$(MAKE) -C {build_proj} install
	{no_ldconfig}{sudo_ldconfig}ldconfig
	sync
	touch $@
    '''
  elif buildsystem == "meson":
    return f'''
.make.{proj}.install: .make.{proj}.build
	@echo -e "\\n\\n\\n===== $@\\n"
	{docker_cmd}{sudo_make_install}ninja -C {build_proj} install
	{no_ldconfig}{sudo_ldconfig}ldconfig
	sync
	touch $@
    '''
  else:
    assert False, f"unknown buildsystem: {buildsystem}"

def gen_makefile_reinstall(proj, deps_reinstall, sudo_make_install,
                           build_proj):
  return f'''
.PHONY: {proj}-reinstall
{proj}-reinstall: {deps_reinstall}
	{sudo_make_install}$(MAKE) -C {build_proj} install
  '''

def gen_makefile_clean(proj, build_proj):
  return f'''
.PHONY: {proj}-clean
{proj}-clean:
	@echo -e "\\n\\n\\n===== $@\\n"
	-chmod -R ug+w {build_proj}
	-rm -rf {build_proj}
	-rm -rf .make.{proj}.*
  '''

def gen_makefile_distclean(proj, src_proj):
  return f'''
.PHONY: {proj}-distclean
{proj}-distclean: {proj}-clean
	@echo -e "\\n\\n\\n===== $@\\n"
	$(MAKE) -C {src_proj} distclean
  '''

def gen_make(proj, deps, configure_opts, jobs, make_dir, src_dir, build_dir, url, push_url, sudo_make_install, no_ldconfig, ldconfig_without_sudo, make_check):
  src_proj = os.path.join(src_dir, proj)
  if proj == 'openbsc':
    src_proj = os.path.join(src_proj, 'openbsc')

  build_proj = os.path.join(build_dir, proj)
  build_to_src = os.path.relpath(src_proj, build_proj)
  build_proj = os.path.relpath(build_proj, make_dir)

  src = os.path.relpath(src_dir, make_dir)
  src_proj = os.path.relpath(src_proj, make_dir)
  push_url = push_url or url

  if configure_opts:
    configure_opts_str = ' '.join(configure_opts)
  else:
    configure_opts_str = ''

  distclean_cond = f'[ -e {src_proj}/config.status ]' if args.auto_distclean else 'false'
  deps_installed = ' '.join(['.make.%s.install' % d for d in deps])
  deps_reinstall = ' '.join(['%s-reinstall' %d for d in deps])
  cflags = 'CFLAGS=-g ' if args.build_debug else ''
  docker_cmd = f'{args.docker_cmd} ' if args.docker_cmd else ''
  check = 'check' if make_check else ''
  no_ldconfig = '#' if no_ldconfig else ''
  sudo_ldconfig = '' if ldconfig_without_sudo else 'sudo '
  sudo_make_install = 'sudo ' if sudo_make_install else ''

  return r'''
### {proj} ###

{proj}_configure_files := $(shell find -L {src_proj} \
    -name "Makefile.am" \
    -or -name "*.in" \
    -and -not -name "Makefile.in" \
    -and -not -name "config.h.in" 2>/dev/null)
{proj}_files := $(shell find -L {src_proj} \
    \( \
      -name "*.[hc]" \
      -or -name "*.py" \
      -or -name "*.cpp" \
      -or -name "*.tpl" \
      -or -name "*.map" \
    \) \
    -and -not -name "config.h" 2>/dev/null)

{clone_rule}

{autoconf_rule}

{configure_rule}

{build_rule}

{install_rule}

{reinstall_rule}

{clean_rule}

{distclean_rule}

.PHONY: {proj}
{proj}: .make.{proj}.install

'''.format(
    proj=proj,
    src_proj=src_proj,
    clone_rule=gen_makefile_clone(proj, src, src_proj, url, push_url),
    autoconf_rule=gen_makefile_autoconf(proj, src_proj, distclean_cond),
    configure_rule=gen_makefile_configure(proj, deps_installed, distclean_cond,
                                          build_proj, cflags, docker_cmd,
                                          build_to_src, configure_opts_str),
    build_rule=gen_makefile_build(proj, distclean_cond, build_proj, docker_cmd,
                                  jobs, check),
    install_rule=gen_makefile_install(proj, docker_cmd, sudo_make_install,
                                      build_proj, no_ldconfig, sudo_ldconfig),
    reinstall_rule=gen_makefile_reinstall(proj, deps_reinstall,
                                          sudo_make_install, build_proj),
    clean_rule=gen_makefile_clean(proj, build_proj),
    distclean_rule=gen_makefile_distclean(proj, src_proj),
    )


projects_deps = read_projects_deps(all_deps_file)
projects_urls = read_projects_dict(all_urls_file)
projects_buildsystems = read_projects_dict(all_buildsystems_file)
configure_opts = listdict()
configure_opts_files = sorted(args.configure_opts_files or [])
for configure_opts_file in configure_opts_files:
  if configure_opts_file.endswith(".deps"):
    print(f"WARNING: using {all_deps_file} instead of {configure_opts_file}")
    continue
  r = read_configure_opts(configure_opts_file)
  configure_opts.extend_dict(read_configure_opts(configure_opts_file))

make_dir = args.make_dir
if not make_dir:
  opts_names = '+'.join([f.replace('.opts', '') for f in configure_opts_files])
  make_dir = 'make-%s' % opts_names

if not os.path.isdir(make_dir):
  os.makedirs(make_dir)

build_dir = args.build_dir
if not build_dir:
  build_dir = make_dir

output = os.path.join(make_dir, args.output)
print('Writing to %r' % output)

with open(output, 'w') as out:
  out.write('# This Makefile was generated by %s\n' % os.path.basename(sys.argv[0]))

  configure_opts_args = ""
  for f in configure_opts_files:
    if not f.endswith(".deps"):
      configure_opts_args += f' \\\n\t\t{os.path.relpath(f, make_dir)}'

  # convenience: add a regen target that updates the generated makefile itself
  out.write(r'''
default: usrp

#
# Convenience targets for whole networks
#
.PHONY: cn
cn: \
	osmo-ggsn \
	osmo-hlr \
	osmo-iuh \
	osmo-mgw \
	osmo-msc \
	osmo-sgsn \
	osmo-sip-connector \
	osmo-smlc \
	$(NULL)

.PHONY: cn-bsc
cn-bsc: \
	cn \
	osmo-bsc \
	$(NULL)

.PHONY: cn-bsc-nat
cn-bsc-nat: \
  cn \
  mobile \
  osmo-bsc \
  osmo-bsc-nat \
  osmo-bts \
  virtphy \
  $(NULL)

.PHONY: usrp
usrp: \
	cn-bsc \
	osmo-bts \
	osmo-trx \
	$(NULL)

#
# Convenience targets for components in subdirs of repositories
#
.PHONY: mobile
mobile: osmocom-bb_layer23

.PHONY: virtphy
virtphy: osmocom-bb_virtphy

#
# Other convenience targets
#
.PHONY: all_debug
all_debug:
	$(MAKE) --dry-run -d all | grep "is newer than target"
	$(MAKE) all

# regenerate this Makefile, in case the deps or opts changed
.PHONY: regen
regen:
	{script} \
		{configure_opts} \
		--output {makefile} \
		--src-dir {src_dir} \
		--make-dir {make_dir} \
		--build-dir {build_dir} \
		--jobs {jobs} \
		--url "{url}"{push_url}{sudo_make_install}{no_ldconfig}{ldconfig_without_sudo}{make_check}{docker_cmd}{build_debug}{auto_distclean}

'''.format(
    script=os.path.relpath(sys.argv[0], make_dir),
    configure_opts=configure_opts_args,
    make_dir='.',
    makefile=args.output,
    src_dir=os.path.relpath(args.src_dir, make_dir),
    build_dir=os.path.relpath(build_dir, make_dir),
    jobs=args.jobs,
    url=args.url,
    push_url=(" \\\n\t\t--push-url '%s'"%args.push_url) if args.push_url else '',
    sudo_make_install=' \\\n\t\t--sudo-make-install' if args.sudo_make_install else '',
    no_ldconfig=' \\\n\t\t--no-ldconfig' if args.no_ldconfig else '',
    ldconfig_without_sudo=' \\\n\t\t--ldconfig-without-sudo' if args.ldconfig_without_sudo else '',
    make_check='' if args.make_check else " \\\n\t\t--no-make-check",
    docker_cmd=f' \\\n\t\t--docker-cmd "{args.docker_cmd}"' if args.docker_cmd else '',
    build_debug=f' \\\n\t\t--build-debug' if args.build_debug else '',
    auto_distclean=' \\\n\t\t--auto-distclean' if args.auto_distclean else '',
    ))

  # convenience target: clone all repositories first
  out.write('clone: \\\n\t' + ' \\\n\t'.join([ '.make.%s.clone' % p for p, d in projects_deps ]) + '\n\n')

  # convenience target: clean all
  out.write('clean: \\\n\t' + ' \\\n\t'.join([ '%s-clean' % p for p, d in projects_deps ]) + '\n\n')

  # now the actual useful build rules
  out.write('all: clone all-install\n\n')

  out.write('all-install: \\\n\t' + ' \\\n\t'.join([ '.make.%s.install' % p for p, d in projects_deps ]) + '\n\n')

  for proj, deps in projects_deps:
    all_config_opts = []
    all_config_opts.extend(configure_opts.get('ALL') or [])
    all_config_opts.extend(configure_opts.get(proj) or [])
    out.write(gen_make(proj, deps, all_config_opts, args.jobs,
                       make_dir, args.src_dir, build_dir, args.url, args.push_url,
                       args.sudo_make_install, args.no_ldconfig,
                       args.ldconfig_without_sudo, args.make_check))

# vim: expandtab tabstop=2 shiftwidth=2
