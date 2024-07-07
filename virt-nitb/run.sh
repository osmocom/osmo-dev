#!/usr/bin/env bash
#set -x

arg="$1"

SIPCON_SERVER="kamailio"

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
  exec $terminal -title "CN:$title" -e sh -c "$1; echo; while sleep 1; do echo 'q Enter to close'; read q_to_close; if [ \"x\$q_to_close\" = xq ]; then break; fi; done"
}

find_term

asan="$(ls -1 /usr/lib/x86_64-linux-gnu/libasan.so.* | tail -n 1)"
udtrace="/n/git/udtrace/libudtrace.so"
titan="/usr/lib/titan/libttcn3-dynamic.so"

#msc="gdb -ex run --args $(which osmo-msc)"
# To enable udtrace on osmo-msc MNCC socket, use this with adjusted /path/to/udtrace:
# - LD_PRELOAD of titan is needed if udtrace was compiled with titan support.
# - LD_PRELOAD of libasan allows building osmo-msc with the sanitize.opts.
# - the tee saves the stderr logging as well as the udtrace output to new file current_log/osmo-msc.out, since udtrace
#   will not show in osmo-msc.log
msc="LD_PRELOAD=$asan:$udtrace:$titan osmo-msc 2>&1 | tee -a current_log/osmo-msc.out"
#msc="osmo-msc"
mgw4msc="osmo-mgw -c osmo-mgw-for-msc.cfg"
#mgw4bsc="strace osmo-mgw -c osmo-mgw-for-bsc.cfg"
mgw4bsc="osmo-mgw -c osmo-mgw-for-bsc.cfg"
hlr="osmo-hlr"
stp="osmo-stp"
bsc="osmo-bsc"
bts="osmo-bts-virtual -c osmo-bts-virtual.cfg"
virtphy="LD_PRELOAD=$asan virtphy"
ms1="LD_PRELOAD=$asan mobile -c mobile.cfg"
ms2="LD_PRELOAD=$asan mobile -c mobile2.cfg"

if [ "x$SIPCON_SERVER" != "xinternal" ]; then
  sipcon="osmo-sip-connector -c osmo-sip-connector.cfg"

  case "kamailio" in
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
     echo "ERROR: unknown value kamailio for SIPCON_SERVER!"
     exit 1
     ;;
  esac
fi

#sudo tcpdump -i $dev -n -w current_log/$dev.single.pcap -U not port 22 &
#sudo tcpdump -i lo -n -w current_log/lo.single.pcap -U not port 22 &

term "$stp" STP &
sleep .2
term "$hlr" HLR &
sleep .2
term "$mgw4msc" MGW4MSC &
sleep .2
term "$mgw4bsc" MGW4BSC &
sleep .2
term "$msc" MSC &
sleep 2
term "$bsc" BSC &
sleep 2
term "$bts" BTS &
sleep .2
term "$virtphy" virtphy &
sleep .2
term "$ms1" MS1 &
sleep 3
term "$ms2" MS2 &

if [ "x$SIPCON_SERVER" != "xinternal" ]; then
  sleep .2
  term "$sipcon" SIPCON &
  sleep .2
  case "$SIPCON_SERVER" in
    "kamailio") term "$kamailio" KAMAILIO &;;
    "freeswitch") term "./freeswitch/freeswitch.sh" FREESWITCH &;;
  esac
fi

case "x_$arg" in
  "x_call")
    set -x
    sleep 3
    ./call.sh
    sleep 1
    ./audio_frame.sh
    sleep 1
    ./audio_frame.sh
    sleep 1
    ./audio_frame.sh
    sleep 1
    ./hangup.sh
    sleep 1
    ;;
  *)
    if [ -n "$arg" ]; then
      echo "don't know '$arg'"
    fi
    ;;
esac

set +x
echo
echo enter to close
read enter_to_close
echo Closing...
#set -x

killall -2 mobile
sleep 3

if [ "x$SIPCON_SERVER" != "xinternal" ]; then
  kill %11 %12
  # 'killall' seems to work only with the shortened name
  killall osmo-sip-connector
  killall "$SIPCON_SERVER"
fi

kill %1 %2 %3 %4 %5 %6 %7 %8 %9 %10
killall osmo-msc
killall osmo-bsc
killall osmo-mgw
killall osmo-hlr
killall -9 osmo-stp
killall virtphy
killall osmo-bts-virtual
killall mobile

set +e
cp *.cfg "$logdir"/

set +x
echo
echo enter name to save log
read log_name
if [ -n "$log_name" ]; then
  newlogdir="log/$log_name"
else
  newlogdir="autolog/log_$(date +%Y-%m-%d_%H-%M-%S)"
fi
mkdir -p "$(dirname "$newlogdir")"

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
