#!/usr/bin/env bash

if ! ../fill_config.py --check-stale; then
	echo
	echo "WARNING: STALE CONFIGS - your net configs are older than the templates they should be based on!"
	echo " * Hit enter to continue, and use the stale config files"
	echo " * Hit ^C and run 'make regen' to regenerate your configs"
	read enter_to_continue
fi

dev="${ETH_DEV}"
apn="${APN_DEV}"

sudo true || exit 1

if ! sudo iptables -t nat -C POSTROUTING -s ${GGSN_NET} -o $dev -j MASQUERADE 2>/dev/null; then
  echo "Adding iptables rule for masquerade"
  sudo iptables -t nat -I POSTROUTING -s ${GGSN_NET} -o $dev -j MASQUERADE
fi

if [ "$(sudo cat /proc/sys/net/ipv4/ip_forward)" = "0" ]; then
  sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
fi

if [ -z "$(ip tuntap show | grep $apn)" ]; then
  sudo ip tuntap add dev $apn mode tun user $USER group $USER
  sudo ip addr add ${GGSN_NET} dev $apn
  sudo ip link set $apn up
fi

if [ -z "$(ip addr show | grep "${TO_RAN_IP}")" ]; then
  echo "No interface has IP address ${TO_RAN_IP}! Hit enter to continue anyway."
  read enter_to_continue
fi
if [ -z "$(ip addr show | grep "${TO_RAN_IU_IP}")" ]; then
  echo "No interface has IP address ${TO_RAN_IU_IP}! Hit enter to 'ip addr add ${TO_RAN_IU_IP}/32 dev $dev'"
  read enter_to_continue
  sudo ip addr add ${TO_RAN_IU_IP}/32 dev $dev
fi

logdir="current_log"
piddir="run/pids"
launcherdir="run/launchers"
rm -rf "$launcherdir"
mkdir -p "$logdir" "$piddir" "$launcherdir"

find_term() {
  # Find a terminal program and write to the global "terminal" variable
  local programs="urxvt xterm"

  if [ -z "${TERMINAL}" ]; then
    echo "ERROR: TERMINAL is not defined in your osmo-dev net config file. Please add it."
    exit 1
  fi

  case " $programs " in
    *" ${TERMINAL} "*)
      terminal="${TERMINAL}"

      if command -v "$terminal" >/dev/null; then
        echo "Terminal: ${TERMINAL}"
        return
      fi

      echo "ERROR: Terminal '${TERMINAL}' is configured, but not installed"
      exit 1
      ;;
  esac

  echo "ERROR: Terminal '${TERMINAL}' is not in list of supported terminals ($programs)"
  exit 1
}

pidfiles_must_not_exist() {
  local pidfile

  for pidfile in "$@"; do
    if [ -e "$pidfile" ]; then
      echo
      echo "ERROR: pidfile exists: $pidfile"
      echo
      kill_pids
      exit 1
    fi
  done
}

term() {
  title="$2"
  if [ -z "$title" ]; then
    title="$(basename $@)"
  fi

  local pidfile="$piddir/$title.pid"
  local pidfile_term="$piddir/$title.term.pid"
  pidfiles_must_not_exist "$pidfile" "$pidfile_term"

  local launcher="$launcherdir/$title.sh"

  cat << EOF > "$launcher"
#!/bin/sh

export LD_LIBRARY_PATH='/usr/local/lib'

$1 &
echo \$! > $pidfile
wait

echo

while true; do
  echo 'q Enter to close'
  read q_to_close
  if [ "x\$q_to_close" = xq ]; then
    break
  fi
done
EOF
  chmod +x "$launcher"

  $terminal \
    -title "CN:$title" \
    -e sh -c "$launcher" \
    &

  echo "$!" > "$pidfile_term"
}

kill_pids() {
  local pidfile
  local pid

  for pidfile in "$piddir"/*.pid; do
    if ! [ -e "$pidfile" ]; then
      continue
    fi

    pid="$(cat "$pidfile")"

    echo "killing $(basename "$pidfile") ($pid)"
    sudo kill "$pid"
    rm "$pidfile"
  done
}

find_term
kill_pids

hnbgw="osmo-hnbgw"
msc="gdb -ex run --args $(which osmo-msc)"
# To enable udtrace on osmo-msc MNCC socket, use this with adjusted /path/to/udtrace:
# - LD_LIBRARY_PATH allows linking to titan if udtrace was compiled with titan support.
# - LD_PRELOAD of libasan allows building osmo-msc with the sanitize.opts.
# - the tee saves the stderr logging as well as the udtrace output to new file current_log/osmo-msc.out, since udtrace
#   will not show in osmo-msc.log
#msc="LD_LIBRARY_PATH=/usr/lib/titan LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libasan.so.5:/path/to/udtrace/libudtrace.so osmo-msc 2>&1 | tee -a current_log/osmo-msc.out"
gbproxy="osmo-gbproxy"
sgsn="osmo-sgsn"
ggsn="osmo-ggsn"
mgw4msc="osmo-mgw -c osmo-mgw-for-msc.cfg"
#mgw4bsc="gdb -ex run --args osmo-mgw -c osmo-mgw-for-bsc.cfg"
#mgw4bsc="strace osmo-mgw -c osmo-mgw-for-bsc.cfg"
mgw4bsc="osmo-mgw -c osmo-mgw-for-bsc.cfg"
hlr="LD_LIBRARY_PATH=/usr/local/lib gdb -ex run --args osmo-hlr --db-upgrade"
stp4cn="osmo-stp -c osmo-stp-cn.cfg"
stp4ran="osmo-stp -c osmo-stp-ran.cfg"
bsc="LD_LIBRARY_PATH=/usr/local/lib gdb -ex run --args osmo-bsc -c osmo-bsc.cfg"
bscnat="osmo-bsc-nat"

if [ "x${MSC_MNCC}" != "xinternal" ]; then
  sipcon="osmo-sip-connector -c osmo-sip-connector.cfg"

  case "${PBX_SERVER}" in
    "kamailio")
      # Require kamailio (PATH hack is needed for Debian)
      kamailio="$(PATH="$PATH:/usr/sbin:/sbin" which kamailio)"
      if [ -z "$kamailio" ]; then
        echo "ERROR: kamailio is not installed."
        echo "After installing it, make sure that it does *not* run as daemon."
        exit 1
      fi
      kamailio="$kamailio -f kamailio.cfg -D -e -E"
      ;;
   "freeswitch")
      if [ -z "$(which freeswitch)" ]; then
        echo "ERROR: freeswitch is not installed."
        echo "Guide: https://freeswitch.org/confluence/display/FREESWITCH/Debian+10+Buster"
        echo "After installing it, make sure that it does *not* run as daemon."
        exit 1
      fi
      ;;
   "none")
      ;;
   *)
     echo "ERROR: unknown value ${PBX_SERVER} for SIPCON_SERVER!"
     exit 1
     ;;
  esac
fi

PIDFILE_TCPDUMP_DEV="$piddir/tcpdump.$dev.pid"
PIDFILE_TCPDUMP_LO="$piddir/tcpdump.lo.pid"
pidfiles_must_not_exist "$PIDFILE_TCPDUMP_DEV" "$PIDFILE_TCPDUMP_LO"

sudo tcpdump -i $dev -n -w current_log/$dev.single.pcap -U not port 22 &
echo "$!" > "$PIDFILE_TCPDUMP_DEV"
sudo tcpdump -i lo -n -w current_log/lo.single.pcap -U not port 22 &
echo "$!" > "$PIDFILE_TCPDUMP_LO"

term "$ggsn" GGSN

if [ "${STP_CN_IP}" = "${STP_RAN_IP}" ]; then
  sleep .2
  term "$stp4cn" STP
else
  sleep .2
  term "$stp4cn" STP4CN

  sleep .2
  term "$stp4ran" STP4RAN

  sleep .2
  term "$bscnat" BSCNAT
fi

sleep .2
term "$hlr" HLR

sleep .2
term "$sgsn" SGSN

sleep .2
term "$gbproxy" GBPROXY

sleep .2
term "$mgw4msc" MGW4MSC

sleep .2
term "$mgw4bsc" MGW4BSC

sleep .2
term "$msc" MSC

sleep 2
term "$hnbgw" HNBGW

sleep .2
term "$bsc" BSC

if [ "x${MSC_MNCC}" != "xinternal" ]; then
  sleep .2
  term "$sipcon" SIPCON

  sleep .2
  case "${PBX_SERVER}" in
    "kamailio")
      term "$kamailio" KAMAILIO
      ;;
    "freeswitch")
      term "./freeswitch/freeswitch.sh" FREESWITCH
      ;;
  esac
fi

#ssh bts rm /tmp/bts.log /tmp/pcu.log
#ssh bts neels/run_remote.sh &

echo enter to close
read enter_to_close
echo Closing...

#ssh bts neels/stop_remote.sh

kill_pids

set +e
cp *.cfg "$logdir"/

echo
echo enter name to save log
read log_name
if [ -n "$log_name" ]; then
  newlogdir="log/$log_name"
  #scp "bts:/tmp/{bts,pcu}.log" "bts:neels/osmo-{bts,pcu}.cfg" "$logdir"
else
  newlogdir="autolog/log_$(date +%Y-%m-%d_%H-%M-%S)"
fi
mkdir -p "$(dirname "$newlogdir")"

mergecap -w "$logdir/trace.pcap" "$logdir/"*.single.pcap && rm -f "$logdir/"*.single.pcap

if [ -x "$newlogdir" ]; then
  echo "already exists, move it manually: $newlogdir"
else
  echo mv "$logdir" "$newlogdir"
  mv "$logdir" "$newlogdir"
  mkdir -p "$logdir"
  logdir="$newlogdir"
fi
rm lastlog
ln -s "$logdir" lastlog
