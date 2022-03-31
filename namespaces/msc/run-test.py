#!/usr/bin/env python3.8

from collections import defaultdict
from datetime import datetime
from functools import partial
from genericpath import exists
from ipaddress import IPv4Interface, IPv6Interface
from json import dump, load
import shutil
import signal
import stat
import subprocess
import os
from dataclasses import dataclass,  asdict, field, fields, is_dataclass
import sys
import tempfile
import time
from typing import List, get_args, overload
import argparse

conf = "bsc"

parser = argparse.ArgumentParser()
parser.add_argument('--test-to-run', type=str, help='optionally run only one test')
parser.add_argument('--supersecretarg', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--gui', action='store_true', help='byobu session')
parser.add_argument('--ws', action='store_true', help='run wireshark on br0 after exit')
parser.add_argument('--run-all-tests', action='store_true', help='run all tests except .control')
parser.add_argument('--parallel', type=int, default=4, help='parallel tests to run if all')
args = parser.parse_args()

if (args.test_to_run is not None) and (not args.supersecretarg):
    print(f"###test_to_run has been set (value is {args.test_to_run})")

if (args.ws is not False) :
    print(f"###ws has been set (value is {args.ws})")
# asdict is slower than using __dict__.copy() for the dataclass


@dataclass(frozen=True, eq=True)
class if_addr:
    """holds all information for a if addr"""
    ip4: IPv4Interface = None
    ip6: IPv6Interface = None
    bridge: str = None


@dataclass(frozen=True, eq=True)
class NetNS_info:
    """holds all information for a netns"""
    name: str = None
    interfaces: List[if_addr] = field(default_factory=list)
    cmd: str = None


@dataclass(frozen=True, eq=True)
class Test_to_run(NetNS_info):
    """holds all information for a netns"""
    #name: str = None
    #interfaces: List[if_addr] = field(default_factory=list)
    #cmd: str = None
    test_binary: str = None
    cfgfile: str = None


@dataclass(frozen=True, eq=True)
class glob_data():
    install_prefix: str
    titandir: str
    workdir: str
    testdir: str


@dataclass(frozen=True, eq=True)
class Topc:
    global_data: glob_data
    interfaces: List[NetNS_info] = field(default_factory=list)
    test_to_run: Test_to_run = None



if conf == "nat_notest":
    global_data = defaultdict(str)
    global_data["install_prefix"] = os.path.expanduser("~/osmo/bscnat/install")
    global_data["titandir"] = os.path.expanduser("~/osmo/titan")
    global_data["workdir"] = os.getcwd()+'/workdir'
    global_data["testdir"] = os.path.expanduser("~/osmo/bscnat/osmo-ttcn3-hacks/msc")
    networkcfg = [
        NetNS_info("gbernd",
                   interfaces=[if_addr(ip4='172.0.0.9/16', bridge='br0')],
                   cmd='nc -l -u -k -p 4729'),  # >/dev/null 2> netcat.stderr &'),
        NetNS_info("stp-cn",
                   interfaces=[if_addr(ip4='172.0.0.122/16', bridge='br0')],
                   cmd='osmo-stp -c ./osmo-stp-cn.cfg'),
        NetNS_info("stp-ran",
                   interfaces=[if_addr(ip4='172.0.0.123/16', bridge='br0')],
                   cmd='osmo-stp -c ./osmo-stp-ran.cfg'),
        NetNS_info("nat",
                   interfaces=[if_addr(ip4='172.0.0.222/16', bridge='br0'),
                               if_addr(ip4='172.0.0.223/16', bridge='br0')],
                   cmd='osmo-bsc-nat -c ./osmo-bsc-nat.cfg'),
        NetNS_info("hlr",
                   interfaces=[if_addr(ip4='172.0.0.5/16', bridge='br0')],
                   cmd=f"osmo-hlr -c ./osmo-hlr.cfg"),
        NetNS_info("msc",
                   interfaces=[if_addr(ip4='172.0.0.33/16', bridge='br0')],
                   cmd='osmo-msc -c ./osmo-msc.cfg'),
        NetNS_info("bsc-0",
                   interfaces=[if_addr(ip4='172.0.0.3/16', bridge='br0')],
                   cmd='osmo-bsc -c ./osmo-bsc-0.cfg'),
        #        nsc("bsc-1",
        #            interfaces=[if_addr(ip4='172.0.0.10/16', bridge='br0')],
        #            cmd='osmo-bsc -c ./osmo-bsc-1.cfg'),
        #        nsc("mgw4bsc1",
        #            interfaces=[if_addr(ip4='172.0.0.11/16', bridge='br0')],
        #            cmd='osmo-mgw -c osmo-mgw-for-bsc-1.cfg'),
        #        nsc("mgw4msc",
        #            interfaces=[if_addr(ip4='172.0.0.6/16', bridge='br0')],
        #            cmd='osmo-mgw -c osmo-mgw-for-msc.cfg'),
        #        nsc("mgw4bscnat",
        #            interfaces=[if_addr(ip4='172.0.0.12/16', bridge='br0')],
        #            cmd='osmo-mgw -c osmo-mgw-for-bsc-nat.cfg'),
    ]


# automated mapping of bridgedict['brname'] = ["intf0", "intf1", "intfn"...]
bridgedict = defaultdict(list)


def dict_to_dc(dclass: dataclass, data: dict):
    """ recursively builds dataclass from dict """
    if is_dataclass(dclass):
        tmpset = {}
        dfd = fields(dclass)
        for f in dfd:
            val = dict_to_dc(f.type, data[f.name])
            tmpset.update({f.name: val})
        return dclass(**tmpset)
    else:
        #FIXME fails for IPv4Interface -> ends up as str?
        if isinstance(data, list):  # list kinda thingy?
            l = []
            arg = get_args(dclass)[0]  # no mixed types in our list..
            for f in data:
                to_append = dict_to_dc(arg, f)
                l.append(to_append)
            return l

        return data


def dc_to_json(arg: dict, fname: str):
    with open(fname, "w") as outfile:
        dump(arg, outfile, default=lambda o: o.__dict__, indent=4)


def json_to_dc(fname: str):
    with open(fname, "r") as infile:
        data = load(infile)
        return dict_to_dc(Topc, data)


#dc_to_json(networkcfg, "foo.json")
networkcfg = json_to_dc("foo.json")
#assert loaded == networkcfg


# check naming, ns_ + name + num
for idx, entry in enumerate(networkcfg.interfaces):
    d = entry.__dict__
    if len(d['name']) > 15-1-2:
        print(f"config error! nettwork '{d['name']}' name too long, must be at most 15-1-2 chars!")
        os._exit(0)


def run_cmds_helper(cmds, vars=None, ignore=False):
    if isinstance(cmds, str):
        cmds = {cmds}
    for line in cmds:
        if line == "":
            continue
        try:
            torun = line.format(**vars)
        except TypeError:
            torun = line
        try:
            subprocess.check_call(torun, shell=True)
        except subprocess.CalledProcessError:
            if not ignore:
                return
            else:
                print(f"failed cmd: {torun}")
                raise

# ldd should show full so  path for standard clang install if compiled with san, so no env necessary.


def prep_env():
    env_vars = {
        #        'CC': "clang-12 -fembed-bitcode -fuse-ld=lld -Wno-unused-command-line-argument",
        'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1',
        #        'ASANPATH': str(os.path.dirname(subprocess.check_output('clang-12 -print-file-name=libclang_rt.asan-x86_64.so', shell=True)), "utf-8"),
        'PYTHONPATH': "{install_prefix}/python:{install_prefix}/lib/python3.8/site-packages:{install_prefix}/lib64/python3.8/site-packages:{install_prefix}/lib/python3.8/dist-packages:{install_prefix}/lib64/python3.8/dist-packages:{install_prefix}/lib/python3/site-packages:{install_prefix}/lib64/python3/site-packages:{install_prefix}/lib/python3/dist-packages:{install_prefix}/lib64/python3/dist-packages",
        'PKG_CONFIG_PATH': "{install_prefix}/lib/pkgconfig:{install_prefix}/lib64/pkgconfig",
        'LIBRARY_PATH': "{install_prefix}/lib:{install_prefix}/lib64/",
        'LD_LIBRARY_PATH': "$ASANPATH:{install_prefix}/lib:{install_prefix}/lib64/:{titandir}/lib:{titandir}/lib/titan:{testdir}",
        'PATH': "{install_prefix}/bin:{titandir}/titan/:{titandir}/bin/",
        'TTCN3_DIR': "{titandir}",
        'TAG': '7b1600f8b13f95baf7ff52935a96a0ec',
        'SLEEP_BEFORE_RESPAWN': "1",
        'HISTFILE': f"{os.getcwd()+os.sep}.history"
        # ENVLINE="env TAG=7b1600f8b13f95baf7ff52935a96a0ec ASAN_OPTIONS=$ASAN_OPTIONS PYTHONPATH=$PYTHONPATH PKG_CONFIG_PATH=$PKG_CONFIG_PATH LIBRARY_PATH=$LIBRARY_PATH LD_LIBRARY_PATH=$LD_LIBRARY_PATH PATH=$PATH"

    }

    # expand ~ paths
    confdict = networkcfg.global_data.__dict__.copy()
    for k, v in confdict.items():
        confdict[k] = os.path.expanduser(v)

    for k, v in env_vars.items():
        ok = os.environ.get(k)
        ok = ':'+ok if ok is not None else ""
        val = v or ''
        try:
            val = v.format(**confdict)
        except:
            val = v
        # print(k+"="+val+ok)
        os.environ[k] = val+ok


def netns_init(vars):
    cmds = [
        # "ip netns add {nsname}",

        # magic path that makes persistent unshared namespaces usable by ip netns
        "mkdir -p /run/netns",
        "touch /run/netns/{nsname}",
        "unshare --mount --uts --ipc --pid --fork --user --map-root-user --mount-proc --net=/run/netns/{nsname} echo created {nsname}...",
        # nsenter --net=/var/run/netns/"${nsname}" ip link set lo up
        "ip netns exec {nsname} ip link set lo up",
    ]
    run_cmds_helper(cmds, vars)


def netns_add(vars):
    cmd = [
        "ip link add {localifname} type veth peer name {remoteifname}",
        "ip link set {localifname} up",
        "ip link set {remoteifname} netns {nsname}",

        "ip netns exec {nsname} ip link set {remoteifname} up",
        "ip netns exec {nsname} ip addr add {ip4} dev {remoteifname}",
        "ip netns exec {nsname} ip -6 addr add {ip6} dev {remoteifname} nodad" if vars['ip6'] is not None else "",
    ]
    run_cmds_helper(cmd, vars)


def prep_all_netns():

    total_if_list = networkcfg.interfaces + [networkcfg.test_to_run]
    # print(total_if_list)

    for idx, entry in enumerate(total_if_list):
        d = entry.__dict__.copy()
        d['nsname'] = "ns_{}".format(d['name'])  # str(idx))
        netns_init(d)

        for idx2, ifn in enumerate(d['interfaces']):
            d['localifname'] = "veth_{}{}".format(d['name'], str(idx2))
            d['remoteifname'] = "ceth_{}{}".format(d['name'], str(idx2))

            # lazy
            d['ip4'] = ifn.ip4
            d['ip6'] = ifn.ip6

            if ifn.bridge is not None:
                bridgedict[ifn.bridge].append(d['localifname'])
            netns_add(d)

    for brname, ifnamelist in bridgedict.items():
        run_cmds_helper(f"ip link add {brname} type bridge")  # stp_state 0 ageing_time 0 forward_delay 0")
        run_cmds_helper(f"ip link set {brname} up")
        for ifname in ifnamelist:
            run_cmds_helper(f"ip link set {ifname} master {brname}")
    run_cmds_helper(f"ip -all netns")
    run_cmds_helper(f"ip link")


def prepare_ns_mounts():
    cmds = [
        # 'mount -t proc none /proc', # done by --mount-proc
        'mount -t sysfs none /sys',

        # check cat /proc/1/mountinfo for shared, priv, ...
        # in host:
        # 28 1 8:5 / / rw,relatime shared:1 - ext4 /dev/sda5 rw,errors=remount-ro
        # 24 28 0:22 / /proc rw,nosuid,nodev,noexec,relatime shared:13 - proc proc rw
        # in ns:
        # 258 244 8:5 / / rw,relatime - ext4 /dev/sda5 rw,errors=remount-ro
        # 403 258 0:22 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw


        # unshare --mount-proc
        # [pid 14178] mount("none", "/", NULL, MS_REC|MS_PRIVATE, NULL) = 0
        # mount mount --make-rprivate /
        # [pid 14178] mount("none", "/proc", NULL, MS_REC|MS_PRIVATE, NULL) = 0
        # mount -t proc none /proc
        # [pid 14178] mount("proc", "/proc", "proc", MS_NOSUID|MS_NODEV|MS_NOEXEC, NULL) = 0
        # mount -t proc proc /proc

        # xterm tries to chown /dev/pts/$n.. to uid:tty-group-id, which it gets from /etc/group, which fails
        # no known fix yet
        # mount -t devpts none /dev/pts -o rw,gid=0,newinstance,ptmxmode=0666,mode=0666,max=1024
        # mount --rbind /dev/pts/ptmx /dev/ptmx -o nosuid,noexec


        # mount -t tmpfs --make-rshared tmpfs /tmp
        # mount -t tmpfs tmpfs /home

        # ip tools needs this to work, we don't care about the host run
        'mount -t tmpfs tmpfs /run',
    ]

    if os.path.exists("/tmp/.X11-unix"):
        cmds2 = [
            # tmp breaks x11, x11 requires workaround by remounting into private dir, then binding back
            f"mkdir -p {networkcfg.global_data.workdir}/.X11-unix",
            f"mount --rbind /tmp/.X11-unix {networkcfg.global_data.workdir}/.X11-unix",
            'mount -t tmpfs none /tmp',
            'mkdir -p /tmp/.X11-unix',
            f"mount --rbind {networkcfg.global_data.workdir}/.X11-unix /tmp/.X11-unix",
            f"umount -l {networkcfg.global_data.workdir}/.X11-unix",
        ]
    else:
        cmds2 = ['mount -t tmpfs none /tmp', ]

    run_cmds_helper(cmds+cmds2)


def fix_hostname():
    run_cmds_helper("hostname testrun")

    to_check = networkcfg.interfaces + [networkcfg.test_to_run]
    addrlist = []
    for _, entry in enumerate(to_check):
        d = entry.__dict__.copy()
        try:
            numifs = len(d['interfaces'])
            for idx, val in enumerate(d['interfaces']):
                idx = idx if numifs > 1 else ''
                addrlist.append(f"{IPv4Interface(val.ip4).ip}\t{d['name']}{idx}") if val.ip4 else ""
                addrlist.append(f"{IPv6Interface(val.ip6).ip}\t{d['name']}{idx}6") if val.ip6 else ""
        except:
            pass

    addrlines = '\n'.join(addrlist)

    my_hosts = f"""
127.0.0.1	localhost
127.1.2.3   testrun

{addrlines}

# The following lines are desirable for IPv6 capable hosts
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
"""
    with open("my_hosts", 'w') as file_:
        file_.write(my_hosts)

    run_cmds_helper("mount my_hosts /etc/hosts --bind")

    wshosts = os.path.expanduser('~/.config/wireshark/hosts')
    if os.path.exists(wshosts):
        print(f"bind mounting {wshosts}..")
        run_cmds_helper(f"mount my_hosts {wshosts} --bind")
    else:
        print(f"{wshosts} does not exist, not bind mounting!")
    print(my_hosts)



class silentsession:
    def new_wnd(self, netnsidx, name, cmd):
        self.new_wnd_nsname(f"ns_{name}", name, cmd)

    def new_wnd_nsname(self, netnsname, name, cmd):
        run_cmds_helper(f"ip netns exec {netnsname} sh -c \"{cmd} > {name}.stdout\" C-m")

    def att(self, sessname=None):
        pass

    def parse_and_run(self, nwconfig):
        for idx, entry in enumerate(nwconfig.interfaces):
            d = entry.__dict__.copy()

            d['cmd'] = d['cmd'] + f"  >> {d['name']}.log 2>&1"

            # last cmd = not in background, but everything else must be in bg
            # if entry == nwconfig.interfaces[-1]:
            #    pass
            # else:
            d['cmd'] = d['cmd'] + " &"

            # if "ttcn3_start" in d['cmd']:
            #    time.sleep(0.5)
            self.new_wnd(idx, d['name'], d['cmd'])
        if nwconfig.test_to_run:
            d = nwconfig.test_to_run.__dict__.copy()
            cfgfile = d['cfgfile'] + (f" {args.test_to_run}" if args.test_to_run is not None else "") + ' '
            tbinpath = nwconfig.global_data.testdir+os.path.sep+d['test_binary'] + ' '
            d['cmd'] = d['cmd'] + ' ' + tbinpath + cfgfile
            d['cmd'] += f"  >> {d['name']}.log 2>&1"
            time.sleep(0.5)
            self.new_wnd(idx, d['name'], d['cmd'])


def get_pids_for_name(name):
    try:
        rv = subprocess.check_output(["pidof", name])
    except:
        return []
    return map(int, rv.split())


class byobusession(silentsession):
    def __init__(self):
        self.sessname = "ttcn3-bsc2"
        run_cmds_helper("tmux list-panes && tmux list-sessions && tmux list-windows")
        run_cmds_helper(f"byobu new-session -s {self.sessname} -d -n 'bernd'")

    def new_wnd_nsname(self, netnsname, name, cmd):
        idxname = self.sessname  # sess+':'+str(idx) if idx != 0 else sess
        run_cmds_helper(f"tmux new-window -a -t {idxname} -n '{name}'", ignore=True)
        run_cmds_helper(f"tmux send -t '{name}' 'ip netns exec {netnsname} sh -c \"{cmd}\"' C-m")

    def att(self, sessname=None):
        sessname = sessname or self.sessname
        run_cmds_helper(f"tmux attach -t {sessname}")

    def parse_and_run(self, nwconfig):
        for idx, entry in enumerate(nwconfig.interfaces):
            d = entry.__dict__.copy()
            # print(d['cmd'])
#            if "ttcn3_start" in d['cmd']:
#                time.sleep(6)#0.2)
            self.new_wnd(idx, d['name'], d['cmd'])
        if nwconfig.test_to_run:
            d = nwconfig.test_to_run.__dict__.copy()

            cfgfile = d['cfgfile'] + (f" {args.test_to_run}" if args.test_to_run is not None else "") + ' '
            tbinpath = nwconfig.global_data.testdir+os.path.sep+d['test_binary'] + ' '
            d['cmd'] = d['cmd'] + ' ' + tbinpath + cfgfile
            time.sleep(0.5)
            self.new_wnd(idx, d['name'], d['cmd'])


def check_debian_userns():
    try:
        with open('/proc/sys/kernel/unprivileged_userns_clone') as f:
            rv = f.read()
            rv = int(rv) if rv.isdigit() else rv
            if rv != 0:
                print("we're on debian and need 'sudo sysctl -w kernel.unprivileged_userns_clone=0' or a mainline/ubuntu kernel!")
                os._exit(0)
    except FileNotFoundError:
        pass  # not debian, we're fine


def unshare_myself():

    # first call from outside
    if not args.supersecretarg:
        pid = os.fork()
        if pid > 0:
            print(f"parent {os.getpid()} waiting for child {pid}")
            sys.stdout.flush()
            os.waitpid(pid, 0)
            os._exit(0)
        else:  # forked self call
            print(f"child {os.getpid()} unsharing itself...")
            arg = "unshare --mount --uts --ipc --net --pid --fork --user --map-root-user --mount-proc /bin/bash -c".split()
            allargs = ' '.join(sys.argv[1:])
            arg += [f'{sys.executable} {__file__} --supersecretarg {allargs}']
            # print(arg)
            sys.stdout.flush()
            os.execvp("unshare", arg)
            print("execvp failed?!")
            os._exit(0)

    print(f"we are in our unprivileged namespace! euid:{os.geteuid()} egid:{os.getegid()}")

    if os.geteuid() != 0 or os.getegid() != 0:
        print(f"...wat? we are not root, exiting!")
        os._exit(0)

    sys.stdout.flush()
    # os._exit(0)


def create_overlayfs():
    return

    # idea:
    # mount --bind -m -n /* mnt/*"
    # mount --move ?

    # overlayfs does not work due to
    # https://github.com/sosy-lab/benchexec/issues/776
    # https://github.com/torvalds/linux/commit/427215d85e8d1476da1a86b8d67aceb485eb3631 "ovl: prevent private clone if bind mount is not allowed"

    run_cmds_helper("mount --make-rprivate /")
    run_cmds_helper("mount --rbind / /")
    run_cmds_helper('mount -t proc none /proc')
    run_cmds_helper('mount -t sysfs none /sys')
    m = "/tmp/mount-point"
    run_cmds_helper(f"mkdir -p '{m}'")
    run_cmds_helper(f"mount -t tmpfs tmpfs '{m}'")
    run_cmds_helper(f"cd '{m}' && mkdir top merge work topdir")
    run_cmds_helper(f"cd '{m}' && mount --rbind '{m}'/topdir / || ls topdir")
    run_cmds_helper(f"cd '{m}' && mount -t overlay overlay -o lowerdir=/,upperdir={m}/top,workdir={m}/work {m}/merge && mount --rbind /dev ./merge/dev")

    oldpwd = os.getcwd()
    os.chroot("merge")

    run_cmds_helper('mount -t proc none /proc')
    run_cmds_helper('mount -t sysfs none /sys')

    run_cmds_helper("touch /foobernd")
    os.chdir(oldpwd)
    os.setgid(0)
    os.setuid(0)

    run_cmds_helper("touch foobart; id; ls -al /; ls -al /home/peta/osmo")
    run_cmds_helper("touch ~/fooboing")
    run_cmds_helper("zsh")

    # run_cmds_helper("id; ls -al .; touch foo")
    os._exit(0)


def kill_tcpdump():
    pids = get_pids_for_name("tcpdump")
    for pid in pids:
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            print(f"already dead: {pid}?")
            continue
        except OSError:
            print(f"fuck: {pid}?")
            continue
        try:
            os.waitpid(pid, os.WSTOPPED)
        except ChildProcessError:
            pass


def exit_cleanup(olddir, test_artifact_storage_location, signum, stack):

    kill_tcpdump()

    def cpy2pass(src, dest):
        """does not choke on sockets..."""
        try:
            shutil.copy2(src, dest)
        except:
            pass

    print(f"data will end up in {test_artifact_storage_location}")
    try:
        shutil.copytree('/tmp', test_artifact_storage_location, copy_function=cpy2pass, dirs_exist_ok=True, symlinks=True, ignore_dangling_symlinks=True)
    except shutil.Error as e:
        pass

    sys.stdout.flush()
    sys.stderr.flush()


def spawn_num_tests(set_of_tests, how_many, oldenv):
    pids_to_wait_For = set()
    while how_many:
        how_many -= 1
        try:
            l = set_of_tests.pop()
        except KeyError:
            continue

        if l.endswith(".control"): # don't run everything.. duh.
            continue

        lcmd = f'{sys.executable} {__file__} --test-to-run {l}'
        print(lcmd)
        fnull = open(os.devnull, 'w') # pipe will fill up and stall, use nothing instead
        process = subprocess.Popen(lcmd, env=oldenv, shell=True, stdout=fnull, stderr=fnull, close_fds=True)
        #my_pid, err = process.communicate()
        #print(err)
        pids_to_wait_For.add(process.pid)
    return pids_to_wait_For

def run_all_tests():

    oldenv = os.environ.copy()
    prep_env()

    cmd = networkcfg.global_data.testdir+os.path.sep+networkcfg.test_to_run.test_binary+" -l"
    
    #os.environ['LD_LIBRARY_PATH'] = os.environ.get('LD_LIBRARY_PATH')+":"+networkcfg.global_data.testdir # ttcn testdir must be in path
    lines = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)  # cmd, shell=True, check=True, capture_output=True, text=True)
    total_tests_to_run = set()
    total_tests_to_run.update(lines.stdout.split())

    if "MSC_Tests" in cmd:
        # remove all iu tests
        filter_to_remove = []
        filterlist = ["TC_iu_"]#, "TC_multi_lu_and_"]
        for i in total_tests_to_run:
            t = [i for y in filterlist if y in i]
            filter_to_remove += t if not None else []

        #print(f"tests to remove: {filter_to_remove}")
        total_tests_to_run.difference_update(filter_to_remove)

    print(f"we have {len(total_tests_to_run)} tests to run, at most {args.parallel} at the same time...")

    num_parallel = args.parallel # 16 = ~ 3GB ram total 
    pids_to_wait_For = spawn_num_tests(total_tests_to_run, num_parallel, oldenv)
    print(pids_to_wait_For)

    print( "%s Waiting for %d processes..." % (datetime.now().strftime('%Y-%m-%d_%H-%M-%S'), len(pids_to_wait_For)))
    while pids_to_wait_For:
        try:
            pid, status = os.wait()
        except ChildProcessError:
            print("looks like we ran out of children?")
            os._exit(0)
        if pid in pids_to_wait_For:
            pids_to_wait_For.remove(pid)
            pids_left = num_parallel-len(pids_to_wait_For)
            to_spawn = max(min(pids_left,num_parallel),0)
            pids_to_wait_For.update(spawn_num_tests(total_tests_to_run, to_spawn, oldenv))
            print( "%s Waiting for %d processes..." % (datetime.now().strftime('%Y-%m-%d_%H-%M-%S'), len(pids_to_wait_For)))
    
    os._exit(0)

if __name__ == "__main__":

    # do not pollute host shell history
    os.environ['HISTFILE'] = f"{os.getcwd()+os.sep}.history"
    check_debian_userns()

    if args.run_all_tests:
        run_all_tests()

    unshare_myself()

    olddir = os.getcwd()
    run_cmds_helper(f"export HOME={olddir}")
    suffix = f"_{args.test_to_run}" if args.test_to_run is not None else ""
    test_artifact_storage_location = tempfile.mkdtemp(dir=olddir, suffix=suffix, prefix=datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
    # if sys.stdout.isatty():
    #    pass
    # else:
    #    stdoutname = args.test_to_run or ""
    #    sys.stdout = open(stdoutname+"_"+os.path.basename(test_artifact_storage_location), 'w')
    #    #sys.stderr = sys.stdout

    create_overlayfs()
    prepare_ns_mounts()
    fix_hostname()
    prep_env()
    prep_all_netns()

    run_cmds_helper("mkdir -p /tmp/unix")

    os.environ['BYOBU_CONFIG_DIR'] = olddir+"/.byobu"

    # put stuff in tmp
    run_cmds_helper("mkdir -p /tmp/trash")
    run_cmds_helper("cp *cfg *default *sh /tmp/trash")
    os.chdir("/tmp/trash")

    for brname, _ in bridgedict.items():
        run_cmds_helper(f"tcpdump -i {brname} -w {brname}.pcapng >> dump.log 2>&1 &")
    time.sleep(0.5)

    # salvage stuck tests on exit to ensure we keep the trash and can figure out what failed
    signal.signal(signal.SIGINT, partial(exit_cleanup, olddir, test_artifact_storage_location))
    signal.signal(signal.SIGTERM, partial(exit_cleanup, olddir, test_artifact_storage_location))

    s = byobusession() if args.gui == True else silentsession()
    s.parse_and_run(networkcfg)
    # s.new_wind(0, "stp", 'osmo-stp -c ./osmo-stp.cfg')
    # s.new_wind(1, "bsc", 'osmo-bsc -c ./osmo-bsc.cfg')
    s.att()

    if args.ws is True:
        print("running ws..")
        kill_tcpdump()
        subprocess.check_call("wireshark br0.pcapng", shell=True)

    # self kill to clean up either way
    os.kill(os.getpid(), signal.SIGINT)


