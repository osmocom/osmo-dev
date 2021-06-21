#!/bin/sh
# Look for git repositories in and below the current dir and install the gerrit
# commit-msg hook in each one.
# Tweak the commit hook to always place the 'Change-Id' at the bottom.
# This requires an ~/.ssh/config entry like
#	host go
#	hostname gerrit.osmocom.org
#	port 29418

set -x
base="$PWD"

for r in $(find . -maxdepth 2 -name '.git'); do
  cd "$base/$r"
  if [ ! -f "hooks/commit-msg" ]; then
    scp go:hooks/commit-msg hooks/
  fi
  sed -i 's/if (unprinted /if (0 \&\& unprinted /' hooks/commit-msg
done
