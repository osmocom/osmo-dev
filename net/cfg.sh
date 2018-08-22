#!/bin/sh
config_file=""
tmpl_dir=""

while test -n "$1"; do
  arg="$1"
  shift

  if [ ! -e "$arg" ]; then
    if [ -e "../$arg"]; then
      arg="../$arg";
    fi
  fi

  if [ -f "$arg" ]; then
    if [ -n "$config_file" ]; then
      echo "Error: more than one config file: '$config_file' and '$arg'"
      exit 2
    fi
    config_file="$arg"
  fi

  if [ -d "$arg" ]; then
    if [ -n "$tmpl_dir" ]; then
      echo "Error: more than one template dir: '$tmpl_dir' and '$arg'"
      exit 2
    fi
    tmpl_dir="$arg"
  fi
done

if [ -z "$config_file" ]; then
  config_file="$(cat .last_config)"
fi

if [ -z "$tmpl_dir" ]; then
  tmpl_dir="$(cat .last_templates)"
fi

set -e
../fill_config.py "$config_file" "$tmpl_dir"

echo "$config_file" > .last_config
echo "$tmpl_dir" > .last_templates
