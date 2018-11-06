#!/usr/bin/env bash
../fill_config.py --check-stale || ( echo "STALE CONFIGS. Hit enter to continue anyway."; read enter_to_continue )

dev="${ETH_DEV}"
ip2="${PUBLIC_IP2}"
apn="${APN_DEV}"

sudo true || exit 1

if [ -z "$(sudo iptables -L -t nat | grep MASQUERADE)" ]; then
  sudo iptables -t nat -A POSTROUTING -s ${GGSN_NET} -o $dev -j MASQUERADE
fi

if [ "$(sudo cat /proc/sys/net/ipv4/ip_forward)" = "0" ]; then
  sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
fi

if [ -z "$(ip tuntap show | grep $apn)" ]; then
  sudo ip tuntap add dev $apn mode tun user $USER group $USER
  sudo ip addr add ${GGSN_NET} dev $apn
  sudo ip link set $apn up
fi

if [ -z "$(ip addr show | grep "$PUBLIC_IP")" ]; then
  echo "No interface has IP address $PUBLIC_IP! Hit enter to continue anyway."
  read enter_to_continue
fi
if [ -z "$(ip addr show | grep "$ip2")" ]; then
  echo "No interface has IP address $ip2! Hit enter to 'ip addr add $ip2/32 dev $dev'"
  read enter_to_continue
  sudo ip addr add $ip2/32 dev $dev
fi

logdir="current_log"
mkdir -p "$logdir"

find_term() {
  # Find a terminal program and write to the global "terminal" variable
  local programs="urxvt xterm"
  local program
  for program in $programs; do
    terminal="$(which $program)"
    [ -n "$terminal" ] && return
  done

  # No terminal found
  echo "ERROR: Couldn't find terminal program! Looked for: $programs"
  exit 1
}

term() {
  title="$2"
  if [ -z "$title" ]; then
    title="$(basename $@)"
  fi
  exec $terminal -title "CN:$title" -e sh -c "export LD_LIBRARY_PATH='/usr/local/lib'; $1; echo; while true; do echo 'q Enter to close'; read q_to_close; if [ \"x\$q_to_close\" = xq ]; then break; fi; done"
}

find_term

hnbgw="osmo-hnbgw"
msc="gdb -ex run --args $(which osmo-msc)"
gbproxy="osmo-gbproxy"
sgsn="osmo-sgsn"
ggsn="osmo-ggsn"
mgw4msc="osmo-mgw -c osmo-mgw-for-msc.cfg"
#mgw4bsc="gdb -ex run --args osmo-mgw -c osmo-mgw-for-bsc.cfg"
#mgw4bsc="strace osmo-mgw -c osmo-mgw-for-bsc.cfg"
mgw4bsc="osmo-mgw -c osmo-mgw-for-bsc.cfg"
hlr="LD_LIBRARY_PATH=/usr/local/lib gdb -ex run --args osmo-hlr"
stp="osmo-stp"
bsc="LD_LIBRARY_PATH=/usr/local/lib gdb -ex run --args osmo-bsc -c osmo-bsc.cfg"

if [ "${SIPCON_ENABLE}" == "true" ]; then
  sipcon="osmo-sip-connector -c osmo-sip-connector.cfg"
  msc="$msc -M ${MSC_MNCC_SOCKET}"

  # Require kamailio (PATH hack is needed for Debian)
  kamailio="$(PATH="$PATH:/usr/sbin:/sbin" which kamailio)"
  if [ -z "$kamailio" ]; then
    echo "ERROR: kamailio is not installed, but it's required for SIPCON_ENABLE."
    echo "After installing it, make sure that it does *not* run as daemon."
    exit 1
  fi
  kamailio="$kamailio -f kamailio.cfg -D -e -E"
fi

sudo tcpdump -i $dev -n -w current_log/$dev.single.pcap -U not port 22 &
sudo tcpdump -i lo -n -w current_log/lo.single.pcap -U not port 22 &

term "$ggsn" GGSN &
sleep .2
term "$stp" STP &
sleep .2
term "$hlr" HLR &
sleep .2
term "$sgsn" SGSN &
sleep .2
term "$gbproxy" GBPROXY &
sleep .2
term "$mgw4msc" MGW4MSC &
sleep .2
term "$mgw4bsc" MGW4BSC &
sleep .2
term "$msc" MSC &
sleep 2
term "$hnbgw" HNBGW &
sleep .2
term "$bsc" BSC &

if [ "${SIPCON_ENABLE}" == "true" ]; then
  sleep .2
  term "$sipcon" SIPCON &
  sleep .2
  term "$kamailio" KAMAILIO &
fi

#ssh bts rm /tmp/bts.log /tmp/pcu.log
#ssh bts neels/run_remote.sh &

echo enter to close
read enter_to_close
echo Closing...

if [ "${SIPCON_ENABLE}" == "true" ]; then
  kill %13 %14
  killall osmo-sip-connector
  killall kamailio
fi

#ssh bts neels/stop_remote.sh

kill %1 %2 %3 %4 %5 %6 %7 %8 %9 %10 %11 %12
killall osmo-msc
killall osmo-bsc
killall osmo-gbproxy
killall osmo-sgsn
#killall osmo-hnbgw
killall osmo-mgw
killall osmo-hlr
killall -9 osmo-stp
sudo killall tcpdump
killall osmo-ggsn

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