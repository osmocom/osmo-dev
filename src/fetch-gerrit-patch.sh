#!/bin/sh
# fetch gerrit patch into new branch named like the patch number.
#
# Usage: go to a git clone and pass a patch number:
#
#   cd osmo-msc
#   P 973
# or
#   P 973/2
#
# Will create new local branches '973_4' (if 4 is the latest patch set)
# or '973_2', respectively.

patch="$1"

if [ -z "$patch" ]; then
  echo "Usage: $0 1234[/5]"
  exit 1
fi

if [ -z "$(echo "$patch" | grep '/')" ]; then
  patch="/$patch/"
fi

if [ -z "$(echo "$patch" | grep '^/')" ]; then
  patch="/$patch"
fi

last_set="$(git ls-remote origin "changes/*" | grep "$patch" | sed 's#.*/\([^/]*\)$#\1 &#' | sort -n | tail -n 1)"
if [ -z "$last_set" ]; then
  echo "Not found: $patch"
  exit 1
fi

change_name="$(echo "$last_set" | sed 's/.*\(refs.*\)/\1/')"
branch_name="$(echo "$change_name" | sed 's#refs/changes/../\([0-9]*\)/\([0-9]*\)#\1_\2#')"

set -x
git fetch origin "$change_name"
git checkout -b "$branch_name" FETCH_HEAD

