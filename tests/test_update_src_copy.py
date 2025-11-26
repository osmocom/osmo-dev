#!/usr/bin/env python3
# Copyright 2025 sysmocom - s.f.m.c. GmbH
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import subprocess

osmo_dev_path = os.path.realpath(os.path.join(__file__, "../../"))
script = os.path.join(osmo_dev_path, "src/_update_src_copy.sh")


def run_cmd(cmd, *args, **kwargs):
    print(f"+ {cmd}")
    return subprocess.run(cmd, check=True, *args, **kwargs)


def test_update_git_dir(tmp_path):
    proj = "testproj"
    src_dir = os.path.join(tmp_path, "src")
    proj_dir = os.path.join(src_dir, proj)
    make_dir = os.path.join(tmp_path, "make")
    dest_dir_proj = os.path.join(make_dir, "src_copy", proj)

    run_cmd(["mkdir", "-p", proj_dir, make_dir])

    # Create git repo
    os.chdir(proj_dir)
    run_cmd(["git", "init", "."])
    run_cmd(["git", "config", "user.email", "osmo-dev@test"])
    run_cmd(["git", "config", "user.name", "osmo-dev-test"])

    # Make initial commit
    run_cmd(["touch", "1.c", "2.c", "3.c"])
    run_cmd("echo '*.o' >.gitignore", shell=True)
    run_cmd(["git", "add", "-A"])
    run_cmd(["git", "commit", "-m", "initial"])

    # Make uncommitted changes
    run_cmd(["touch", "1.o", "4.c", "5.c"])
    run_cmd(["rm", "1.c", "2.c"])

    # Stage half of the changes
    run_cmd(["git", "add", "1.c", "4.c"])

    # Run _update_src_copy.sh
    os.chdir(make_dir)
    time_start = "1"
    run_cmd(["sh", "-ex", script, src_dir, proj, time_start])
    assert sorted(os.listdir(dest_dir_proj)) == [
        ".gitignore",
        "3.c",
        "4.c",
        "5.c",
    ]

    # Commit changes
    os.chdir(proj_dir)
    run_cmd(["git", "add", "-A"])
    run_cmd(["git", "commit", "-m", "test"])

    # Run _update_src_copy.sh again (this time LIST_DELETED is empty)
    os.chdir(make_dir)
    time_start = "2"
    run_cmd(["sh", "-ex", script, src_dir, proj, time_start])
    assert sorted(os.listdir(dest_dir_proj)) == [
        ".gitignore",
        "3.c",
        "4.c",
        "5.c",
    ]
