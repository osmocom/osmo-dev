It's possible to run TTCN-3 test cases without using Docker.  This directory
contains scripts for starting a testsuite and the related binaries in a tmux
session.  For example, ttcn3-bsc-test.sh does the following:

* Starts osmo-bsc, osmo-stp, and three instances of osmo-bts-omldummy.
* Prepares a command for execuring the test suite.
