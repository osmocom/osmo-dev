#!/bin/sh

stale="0"
for f in *.cfg; do
  f="$(basename "$f")"
  for g in $(find . -maxdepth 2 -name "$f" -or -name "common_logging") ; do
    if [ "$f" -ot "$g" ]; then
      stale="1"
      echo "$f older than $g"
    fi
  done
done

if [ "$stale" = "1" ]; then
  echo "Stale configs. Hit enter to continue anyway."
  read ok_to_continue
fi
