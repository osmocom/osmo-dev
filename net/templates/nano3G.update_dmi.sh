#!/bin/sh
local_dmi_src="$1"
if [ ! -f "$local_dmi_src" ]; then
	echo "No such file: $local_dmi_src"
	exit 1
fi
mount -o remount,rw /
cp "$local_dmi_src" /etc/init.d/local.dmi
sync
mount -o remount,ro /
