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
import shlex

topdir = os.path.dirname(os.path.realpath(__file__))
all_deps_file = os.path.join(topdir, "all.deps")
all_urls_file = os.path.join(topdir, "all.urls")
all_buildsystems_file = os.path.join(topdir, "all.buildsystems")
parser = argparse.ArgumentParser(epilog=__doc__, formatter_class=argparse.RawTextHelpFormatter)

convenience_targets = {
  # Whole networks
  "cn": [
    "osmo-ggsn",
    "osmo-hlr",
    "osmo-iuh",
    "osmo-mgw",
    "osmo-sgsn",
    "osmo-sip-connector",
    "osmo-smlc",
  ],
  "cn-bsc": [
    "cn",
    "osmo-bsc",
  ],
  "cn-bsc-nat": [
    "cn",
    "mobile",
    "osmo-bsc",
    "osmo-bsc-nat",
    "osmo-bts",
    "virtphy",
  ],
  "usrp": [
    "cn-bsc",
    "osmo-bts",
    "osmo-trx",
  ],
  # Components in subdirs of repositories
  "mobile": ["osmocom-bb_layer23"],
  "trxcon": ["osmocom-bb_trxcon"],
  "virtphy": ["osmocom-bb_virtphy"],
}

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

parser.add_argument('-g', '--build-debug', dest='build_debug', default=False, action='store_true',
    help='''set 'CFLAGS=-g' when calling src/configure''')

parser.add_argument('-i', '--install-prefix', default='/usr/local',
                    help='''install there instead of /usr/local''')

parser.add_argument('-A', '--autoreconf-in-src-copy', action='store_true',
                    help="run autoreconf in a copy of the source dir, avoids 'run make distclean' errors")

parser.add_argument('--targets',
                    help="comma separated list of high-level targets to build instead of all targets")

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
      self.extend(k, v)

def read_projects_deps(path):
  'Read deps config and return a dict of {project_name: which-other-to-build-first, …}.'
  ret = {}
  for line in open(path):
    line = line.strip()
    if not line or line.startswith('#'):
      continue
    tokens = line.split()
    ret[tokens[0]] = tokens[1:]
  return ret

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
  return read_projects_deps(path)

def gen_convenience_targets():
  ret = ""
  for short, full in convenience_targets.items():
    if ret:
      ret += "\n"
    ret += f".PHONY: {short}\n"
    ret += f"{short}: {' '.join(full)}\n"
  return ret

def filter_projects_deps_targets():
  if not args.targets:
    return projects_deps

  ret = {}
  for target in args.targets.split(","):
    # .make.osmocom-bb.clone -> osmocom-bb
    if target.startswith(".make."):
      target = target.split(".")[2]

    current_targets = [target]
    if target in convenience_targets:
      current_targets = convenience_targets[target]

    for target in current_targets:
      # Add target + all dependencies to ret
      queue = [target]
      while queue:
        project = queue.pop()
        if project not in projects_deps:
          print()
          print(f"ERROR: filter_projects_deps_targets: can't find project {project} in projects_deps!")
          print()
          sys.exit(1)

        # simtrace2_host -> simtrace2
        if "_" in project:
          project_main = project.split("_")[0]
          if project_main in projects_deps and project_main not in ret:
            queue += [project_main]

        deps = projects_deps[project]
        ret[project] = deps

        for dep in deps:
          if dep not in ret:
            queue += [dep]

  return ret

def gen_makefile_clone(proj, src, src_proj, update_src_copy_cmd):
  if proj == "osmocom-bb_layer23":
    return f'''
.make.{proj}.clone: .make.osmocom-bb.clone
  @echo "\\n\\n\\n===== $@\\n"
  test -L {src_proj} || ln -s osmocom-bb/src/host/layer23 {src_proj}
  {update_src_copy_cmd}
  touch $@
  '''

  if proj == "osmocom-bb_virtphy":
    return f'''
.make.{proj}.clone: .make.osmocom-bb.clone
  @echo "\\n\\n\\n===== $@\\n"
  test -L {src_proj} || ln -s osmocom-bb/src/host/virt_phy {src_proj}
  {update_src_copy_cmd}
  touch $@
  '''

  if proj == "osmocom-bb_trxcon":
    return f'''
.make.{proj}.clone: .make.osmocom-bb.clone
  @echo "\\n\\n\\n===== $@\\n"
  test -L {src_proj} || ln -s osmocom-bb/src/host/trxcon {src_proj}
  {update_src_copy_cmd}
  touch $@
  '''

  if proj == "simtrace2_host":
    return f'''
.make.{proj}.clone: .make.simtrace2.clone
  @echo "\\n\\n\\n===== $@\\n"
  test -L {src_proj} || ln -s simtrace2/host {src_proj}
  {update_src_copy_cmd}
  touch $@
  '''

  if proj in projects_urls:
    url = projects_urls[proj]
    cmd_set_push_url = "true"
  else:
    url = f"{args.url}/{proj}"
    push_url = f"{args.push_url or args.url}/{proj}"
    cmd_set_push_url = f'git -C "{src}/{proj}" remote set-url --push origin "{push_url}"'

  cmd_clone = f'git -C {src} clone --recurse-submodules "{url}" "{proj}"'

  return f'''
.make.{proj}.clone:
  @echo "\\n\\n\\n===== $@\\n"

  @if ! [ -e {src}/ ]; then \\
    if [ -L {src} ]; then \\
      echo "ERROR: broken symlink: {src}"; \\
      exit 1; \\
    fi; \\
    set -x; \\
    mkdir -p {src}; \\
  fi

  @if ! [ -e {src_proj}/ ]; then \\
    if [ -L {src_proj} ]; then \\
      echo "ERROR: broken symlink: {src_proj}"; \\
      exit 1; \\
    fi; \\
    set -x; \\
    ( {cmd_clone} && {cmd_set_push_url} ); \\
  fi

  {update_src_copy_cmd}
  sync
  touch $@
  '''

def gen_makefile_autoconf(proj, src_proj, src_proj_copy, update_src_copy_cmd):
  buildsystem = projects_buildsystems.get(proj, "autotools")

  if buildsystem == "autotools":
    return f'''
.make.{proj}.autoconf: .make.{proj}.clone {src_proj}/configure.ac
  @echo "\\n\\n\\n===== $@\\n"
  {update_src_copy_cmd}
  -rm -f {src_proj_copy}/.version
  cd {src_proj_copy}; autoreconf -fi
  sync
  touch $@
    '''
  elif buildsystem in ["meson", "erlang"]:
    return ""
  else:
    assert False, f"unknown buildsystem: {buildsystem}"


def gen_makefile_configure(proj, deps_installed, build_proj,
                           cflags, build_to_src, configure_opts,
                           update_src_copy_cmd):
  buildsystem = projects_buildsystems.get(proj, "autotools")
  if buildsystem == "autotools":
    return f'''
.make.{proj}.configure: .make.{proj}.autoconf {deps_installed} $({proj}_configure_files)
  @echo "\\n\\n\\n===== $@\\n"
  {update_src_copy_cmd}
  -chmod -R ug+w {build_proj}
  -rm -rf {build_proj}
  mkdir -p {build_proj}
  cd {build_proj}; {cflags}{build_to_src}/configure \\
    --prefix {shlex.quote(args.install_prefix)} \\
    {configure_opts}
  sync
  touch $@
    '''
  elif buildsystem == "meson":
    return f'''
.make.{proj}.configure: .make.{proj}.clone {deps_installed} $({proj}_configure_files)
  @echo "\\n\\n\\n===== $@\\n"
  -chmod -R ug+w {build_proj}
  -rm -rf {build_proj}
  mkdir -p {build_proj}
  cd {build_proj}; {cflags}meson setup {build_to_src} . \\
    --prefix {shlex.quote(args.install_prefix)}
  sync
  touch $@
    '''
  elif buildsystem == "erlang":
    return ""
  else:
    assert False, f"unknown buildsystem: {buildsystem}"

def gen_makefile_build(proj, build_proj, src_proj, update_src_copy_cmd):
  buildsystem = projects_buildsystems.get(proj, "autotools")
  check = "check" if args.make_check else ""

  if buildsystem == "autotools":
    return f'''
.make.{proj}.build: .make.{proj}.configure $({proj}_files)
  @echo "\\n\\n\\n===== $@\\n"
  {update_src_copy_cmd}
  $(MAKE) -C {build_proj} -j {args.jobs} {check}
  sync
  touch $@
    '''
  elif buildsystem == "meson":
    test_line = ""
    # TODO: currently tests don't pass in this env
    # if check:
    #   test_line = f"meson test -C {build_proj} -v"
    return f'''
.make.{proj}.build: .make.{proj}.configure $({proj}_files)
  @echo "\\n\\n\\n===== $@\\n"
  meson compile -C {build_proj} -j {args.jobs}
  {test_line}
  sync
  touch $@
    '''
  elif buildsystem == "erlang":
    return f'''
.make.{proj}.build: $({proj}_files)
  @echo "\\n\\n\\n===== $@\\n"
  set -x && \\
    export REBAR_BASE_DIR="$$PWD/{build_proj}" && \\
    mkdir -p "$$REBAR_BASE_DIR" && \\
    $(MAKE) -C {src_proj} build {check}
  sync
  touch $@
    '''
  else:
    assert False, f"unknown buildsystem: {buildsystem}"

def gen_makefile_install(proj, build_proj, src_proj):
  no_ldconfig = '#' if args.no_ldconfig else ''
  sudo_ldconfig = '' if args.ldconfig_without_sudo else 'sudo '
  sudo_make_install = "sudo " if args.sudo_make_install else ""
  buildsystem = projects_buildsystems.get(proj, "autotools")
  if buildsystem == "autotools":
    return f'''
.make.{proj}.install: .make.{proj}.build
  @echo "\\n\\n\\n===== $@\\n"
  {sudo_make_install}$(MAKE) -C {build_proj} install
  {no_ldconfig}{sudo_ldconfig}ldconfig
  sync
  touch $@
    '''
  elif buildsystem == "meson":
    return f'''
.make.{proj}.install: .make.{proj}.build
  @echo "\\n\\n\\n===== $@\\n"
  {sudo_make_install}ninja -C {build_proj} install
  {no_ldconfig}{sudo_ldconfig}ldconfig
  sync
  touch $@
    '''
  elif buildsystem == "erlang":
    # Use the "install" target if it exists, otherwise fall back to installing
    # files generated by escriptize in default/bin. The fallback method can be
    # removed once osmo-epdg has an install target.
    return f'''
.make.{proj}.install: .make.{proj}.build
  @echo "\\n\\n\\n===== $@\\n"
  set -ex; \\
    if grep -q "^install:" {shlex.quote(src_proj)}/Makefile; then \\
      {sudo_make_install}$(MAKE) \\
        -C {shlex.quote(src_proj)} \\
        install \\
        DESTDIR={shlex.quote(args.install_prefix)} \\
        REBAR_BASE_DIR="$$PWD"/{shlex.quote(build_proj)}; \\
    else \\
      for i in {build_proj}/default/bin/*; do \\
        install -v -Dm755 "$$i" -t {shlex.quote(args.install_prefix)}/bin/; \\
      done; \\
    fi
  sync
  touch $@
    '''
  else:
    assert False, f"unknown buildsystem: {buildsystem}"

def gen_makefile_reinstall(proj, deps_reinstall, build_proj):
  sudo_make_install = "sudo " if args.sudo_make_install else ""
  return f'''
.PHONY: {proj}-reinstall
{proj}-reinstall: {deps_reinstall}
  {sudo_make_install}$(MAKE) -C {build_proj} install
  '''

def gen_makefile_clean(proj, build_proj):
  return f'''
.PHONY: {proj}-clean
{proj}-clean:
  @echo "\\n\\n\\n===== $@\\n"
  -chmod -R ug+w {build_proj}
  -rm -rf {build_proj}
  -rm -rf .make.{proj}.*
  '''

def is_src_copy_needed(proj):
  if not args.autoreconf_in_src_copy:
    return False

  # The rsync workaround to not write to the source dir during "autoreconf -fi"
  # is only needed for autotools based projects
  buildsystem = projects_buildsystems.get(proj, "autotools")
  if buildsystem != "autotools":
    return False

  return True

def gen_update_src_copy_cmd(proj, src_dir, make_dir):
  if not is_src_copy_needed(proj):
    return ""

  src_dir_script = os.path.join(topdir, "src")
  src_dir_script = os.path.relpath(src_dir_script, make_dir)

  ret = "@sh -e "
  ret += os.path.join(src_dir_script, "_update_src_copy.sh")
  ret += f" {shlex.quote(src_dir)}"
  ret += f" {shlex.quote(proj)}"
  ret += " $(TIME_START)"
  return ret

def gen_src_proj_copy(src_proj, make_dir, proj):
  if not is_src_copy_needed(proj):
    return src_proj
  return os.path.join(make_dir, "src_copy", proj)

def gen_make(proj, deps, configure_opts, make_dir, src_dir, build_dir):
  src_proj = os.path.join(src_dir, proj)
  src_proj_copy = gen_src_proj_copy(src_proj, make_dir, proj)

  build_proj = os.path.join(build_dir, proj)
  build_to_src = os.path.relpath(src_proj_copy, build_proj)
  build_proj = os.path.relpath(build_proj, make_dir)

  if configure_opts:
    configure_opts_str = ' '.join(configure_opts)
  else:
    configure_opts_str = ''

  deps_installed = ' '.join(['.make.%s.install' % d for d in deps])
  deps_reinstall = ' '.join(['%s-reinstall' %d for d in deps])
  cflags = 'CFLAGS=-g ' if args.build_debug else ''
  update_src_copy_cmd = gen_update_src_copy_cmd(proj, src_dir, make_dir)

  return f'''
### {proj} ###

{proj}_configure_files := $(shell find -L {src_proj} \\
    -name "Makefile.am" \\
    -or -name "*.in" \\
    -and -not -name "Makefile.in" \\
    -and -not -name "config.h.in" 2>/dev/null)
{proj}_files := $(shell find -L {src_proj} \\
    \\( \\
      -name "*.[hc]" \\
      -or -name "*.py" \\
      -or -name "*.cpp" \\
      -or -name "*.tpl" \\
      -or -name "*.map" \\
      -or -name "*.erl" \\
    \\) \\
    -and -not -name "config.h" 2>/dev/null)

{gen_makefile_clone(proj,
                    src_dir,
                    src_proj,
                    update_src_copy_cmd)}

{gen_makefile_autoconf(proj,
                       src_proj,
                       src_proj_copy,
                       update_src_copy_cmd)}

{gen_makefile_configure(proj,
                        deps_installed,
                        build_proj,
                        cflags,
                        build_to_src,
                        configure_opts_str,
                        update_src_copy_cmd)}

{gen_makefile_build(proj,
                    build_proj,
                    src_proj_copy,
                    update_src_copy_cmd)}

{gen_makefile_install(proj,
                      build_proj,
                      src_proj)}

{gen_makefile_reinstall(proj,
                        deps_reinstall,
                        build_proj)}

{gen_makefile_clean(proj, build_proj)}

.PHONY: {proj}
{proj}: .make.{proj}.install
'''

projects_deps = read_projects_deps(all_deps_file)
projects_deps = filter_projects_deps_targets()
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

make_dir = os.path.abspath(make_dir)
src_dir = os.path.abspath(args.src_dir)

if not os.path.isdir(make_dir):
  os.makedirs(make_dir)

build_dir = args.build_dir
if not build_dir:
  build_dir = make_dir

content = '# This Makefile was generated by %s\n' % os.path.basename(sys.argv[0])

configure_opts_args = ""
for f in configure_opts_files:
  if not f.endswith(".deps"):
    configure_opts_args += f' \\\n\t\t{os.path.relpath(f, make_dir)}'

# convenience: add a regen target that updates the generated makefile itself
content += f'''
default: usrp

#
# Convenience targets (whole networks, components in subdirs)
#
{gen_convenience_targets()}
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
  {os.path.relpath(sys.argv[0], make_dir)} \\
    {configure_opts_args} \\
    --output {args.output} \\
    --src-dir {os.path.relpath(args.src_dir, make_dir)} \\
    --make-dir . \\
    --build-dir {os.path.relpath(build_dir, make_dir)} \\
    --jobs {args.jobs} \\
    --url "{args.url}" \\
'''

if args.push_url:
  content += f"    --push-url {shlex.quote(args.push_url)} \\\n"
if args.sudo_make_install:
  content += "    --sudo-make-install \\\n"
if args.no_ldconfig:
  content += "    --no-ldconfig \\\n"
if args.ldconfig_without_sudo:
  content += "    --ldconfig-without-sudo \\\n"
if not args.make_check:
  content += "    --no-make-check \\\n"
if args.build_debug:
  content += "    --build-debug \\\n"
if args.autoreconf_in_src_copy:
  content += "    --autoreconf-in-src-copy \\\n"
if args.targets:
  content += f"    --targets={shlex.quote(args.targets)} \\\n"
content += "    $(NULL)\n"

if args.autoreconf_in_src_copy:
  content += """

# --autoreconf-in-src-copy: get current time to avoid running rsync more than
# once within this Makefile per project
TIME_START := $(shell date +%s%N)

"""

# convenience target: clone all repositories first
content += 'clone: \\\n\t' + ' \\\n\t'.join([ '.make.%s.clone' % p for p, d in projects_deps.items() ]) + '\n\n'

# convenience target: clean all
content += 'clean: \\\n\t' + ' \\\n\t'.join([ '%s-clean' % p for p, d in projects_deps.items() ]) + '\n\n'

# now the actual useful build rules
content += 'all: clone all-install\n\n'

content += 'all-install: \\\n\t' + ' \\\n\t'.join([ '.make.%s.install' % p for p, d in projects_deps.items() ]) + '\n\n'

for proj, deps in projects_deps.items():
  all_config_opts = []
  all_config_opts.extend(configure_opts.get('ALL') or [])
  all_config_opts.extend(configure_opts.get(proj) or [])
  content += gen_make(proj, deps, all_config_opts, make_dir, src_dir, build_dir)

# Replace spaces with tabs to avoid the common pitfall of inserting spaces
# instead of tabs by accident into the Makefile (as the python code is indented
# with spaces), which results in a broken Makefile.
content = content.replace("  ", "	")

output = os.path.join(make_dir, args.output)
print('Writing to %r' % output)

with open(output, 'w') as out:
  out.write(content)

# vim: expandtab tabstop=2 shiftwidth=2
