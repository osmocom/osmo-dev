#!/usr/bin/env python3
# Copyright 2025 sysmocom - s.f.m.c. GmbH
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shlex
import subprocess

osmo_dev_path = os.path.realpath(os.path.join(__file__, "../../"))


def run_cmd(cmd, *args, **kwargs):
    print(f"+ {cmd}")
    return subprocess.run(cmd, check=True, *args, **kwargs)


def run_make_regen_2x(cwd):
    """The "make regen" command regenerates the Makefile. Ensure that this
    works twice in a row."""
    run_cmd(["make", "regen"], cwd=cwd)
    run_cmd(["make", "regen"], cwd=cwd)


def put_gen_makefile_into_tmp_path(tmp_path):
    """Ensure running gen_makefile.py -m=<relative path> works as expected."""
    run_cmd(f"cp -v *.* {shlex.quote(str(tmp_path))}", cwd=osmo_dev_path, shell=True)
    run_cmd(["ln", "-s", os.path.join(osmo_dev_path, "src"), os.path.join(tmp_path, "src")])


def test_make_libosmocore_autoconf(tmp_path):
    run_cmd(["./gen_makefile.py", "default.opts", "iu.opts", "no_dahdi.opts", "-m", tmp_path], cwd=osmo_dev_path)
    run_cmd(["make", ".make.libosmocore.autoconf"], cwd=tmp_path)
    run_make_regen_2x(tmp_path)


def test_make_libosmocore_autoconf_src_copy(tmp_path):
    run_cmd(["./gen_makefile.py", "-m", tmp_path, "--autoreconf-in-src-copy"], cwd=osmo_dev_path)
    run_cmd(["make", ".make.libosmocore.autoconf"], cwd=tmp_path)
    run_make_regen_2x(tmp_path)


def test_make_libosmocore_autoconf_relative_makedir(tmp_path):
    put_gen_makefile_into_tmp_path(tmp_path)
    run_cmd(["./gen_makefile.py", "-m", "make"], cwd=tmp_path)
    make_path = os.path.join(tmp_path, "make")
    run_cmd(["make", ".make.libosmocore.autoconf"], cwd=make_path)
    run_make_regen_2x(make_path)


def test_make_libosmocore_autoconf_relative_makedir_src_copy(tmp_path):
    put_gen_makefile_into_tmp_path(tmp_path)
    run_cmd(["./gen_makefile.py", "-m", "make", "--autoreconf-in-src-copy"], cwd=tmp_path)
    make_path = os.path.join(tmp_path, "make")
    run_cmd(["make", ".make.libosmocore.autoconf"], cwd=make_path)
    run_make_regen_2x(make_path)


def test_make_open5gs_configure(tmp_path):
    run_cmd(["./gen_makefile.py", "-m", tmp_path], cwd=osmo_dev_path)
    run_cmd(["make", ".make.open5gs.configure"], cwd=tmp_path)
    run_make_regen_2x(tmp_path)


def test_make_open5gs_configure_src_copy(tmp_path):
    run_cmd(["./gen_makefile.py", "-m", tmp_path, "--autoreconf-in-src-copy"], cwd=osmo_dev_path)
    run_cmd(["make", ".make.open5gs.configure"], cwd=tmp_path)
    run_make_regen_2x(tmp_path)


def test_gen_makefile_with_targets_arg(tmp_path):
    run_cmd(["./gen_makefile.py", "-m", tmp_path, "--targets", "trxcon,osmo-mgw,simtrace2_host"], cwd=osmo_dev_path)
    run_cmd("grep -q '^osmocom-bb_trxcon_files :=' Makefile", cwd=tmp_path, shell=True)
    run_cmd("grep -q '^osmo-mgw_files :=' Makefile", cwd=tmp_path, shell=True)
    run_cmd("grep -q '^libosmocore_files :=' Makefile", cwd=tmp_path, shell=True)
    run_cmd("grep -q '^simtrace2_files :=' Makefile", cwd=tmp_path, shell=True)
    run_cmd("! grep -q '^osmo-bts_files :=' Makefile", cwd=tmp_path, shell=True)
    run_cmd("! grep -q '^osmo-s1gw_files :=' Makefile", cwd=tmp_path, shell=True)
    run_cmd("! grep -q '^open5gs_files :=' Makefile", cwd=tmp_path, shell=True)
    run_make_regen_2x(tmp_path)
