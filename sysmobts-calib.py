#!/usr/bin/env python3
doc = '''Remotely do a clock calibration of a sysmoBTS.

You need is ssh root access to the BTS, and an antenna connected to the NWL.

Remotely goes through the steps to obtain a OCXO calibration value from netlisten.
- Obtain the current calibration value from /etc/osmocom/osmo-bts-sysmo.cfg.
- Stop the osmo-bts-sysmo.service.
- Do a scan to get the strongest received ARFCN.
- Run n passes of sysmobts-calib (default: 7) to obtain an average calibration val.
- Write this calibration value back to /etc/osmocom/osmo-bts-sysmo.cfg.
- Start osmo-bts-sysmo.service.
'''

import sys
import subprocess
import re
import shlex
import argparse

calib_val_re = re.compile(r'clock-calibration +([0-9]+)')
result_re = re.compile('The calibration value is: ([0-9]*)')

class Globals:
    orig_calib_val = None
    calib_val = None
    bts = 'bts0'
    band = '900'
    arfcn = None

def error(*msgs):
    sys.stderr.write(''.join(str(m) for m in msgs))
    sys.stderr.write('\n')
    exit(1)

def log(*msgs):
    print(''.join(str(m) for m in msgs))

def cmd_to_str(cmd):
    return ' '.join(shlex.quote(c) for c in cmd)

def call_output(*cmd):
    cmd = ('ssh', Globals.bts,) + cmd
    log('+ %s' % cmd_to_str(cmd))
    sys.stdout.flush()
    sys.stderr.flush()
    p = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    o,e = p.communicate()
    return o.decode('utf-8')

def call(*cmd):
    o = call_output(*cmd)
    if o:
        log(o)

def reload_dsp():
    #call('/bin/sh', '-c', r"'cat /lib/firmware/sysmobts-v?.bit > /dev/fpgadl_par0 ; sleep 3s; cat /lib/firmware/sysmobts-v?.out > /dev/dspdl_dm644x_0; sleep 1s'")
    # systemd service contains the DSP reload commands in the ExecStopPost.
    # So starting and stopping the service is the easy way to reload the DSP.
    call('systemctl', 'start', 'osmo-bts-sysmo')
    call('systemctl', 'stop', 'osmo-bts-sysmo')

def get_cfg_calib_val():
    o = call_output('grep', 'clock-calibration', '/etc/osmocom/osmo-bts-sysmo.cfg')
    if not o:
        return None
    o = o.strip()
    m = calib_val_re.match(o)
    if not m:
        return None
    return m.group(1)

def set_cfg_calib_val(calib_val):
    if get_cfg_calib_val() is None:
        call('sed', '-i', "'s/^ instance 0$/&\\n  clock-calibration %s/'" % calib_val, '/etc/osmocom/osmo-bts-sysmo.cfg');
    else:
        call('sed', '-i', "'s/clock-calibration.*$/clock-calibration %s/'" % calib_val, '/etc/osmocom/osmo-bts-sysmo.cfg');

    now = get_cfg_calib_val()
    if now != calib_val:
        print('Failed to set calibration value, set manually in osmo-bts-sysmo.cfg')
        print('phy 0\n instance 0\n  clock-calibration %s' % calib_val)


def ask(*question, valid_answers=('*',)):
    while True:
        print('\n' + '\n  '.join(question))

        answer = sys.stdin.readline().strip()
        for v in valid_answers:
            if v == answer:
                return answer
            if v == '*':
                return answer
            if v == '+' and len(answer):
                return answer

def call_sysmobts_calib(mode, *args):
    o = call_output('sysmobts-calib', '-c', 'ocxo', '-s', 'netlisten', '-b', Globals.band, '-i', Globals.calib_val, '-m', mode, *args)
    log(o)
    reload_dsp()
    return o

def int_be_one(string):
    val = int(string)
    if val < 1:
        raise argparse.ArgumentTypeError('value must be at least 1')
    return val

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument('-b', '--band', dest='band', default=None,
                        help='Which GSM band to scan and calibrate to (850, 900, 1800, 1900)')
    parser.add_argument('-a', '--arfcn', dest='arfcn', default=None,
                        help="Don't scan, directly use this ARFCN to calibrate to")
    parser.add_argument('-i', '--initial-clock-correction', dest='calib_val', default=None,
                        help='Clock calibration value to start out with. If omitted, this is obtained from'
                        ' /etc/osmocom/osmo-bts-sysmo.cfg from the BTS file system.')
    parser.add_argument('-I', '--set-clock-correction', dest='set_calib_val', default=None,
                        help="Don't scan or calibrate, just set the given value in the config file")
    parser.add_argument('-G', '--get-clock-correction', dest='get_calib_val', default=False, action='store_true',
                        help="Don't scan or calibrate, just read the given value in the config file")
    parser.add_argument('-n', '--passes', dest='passes', default=7, type=int_be_one,
                        help="How many times to run sysmobts-calib to obtain a resulting calibration value average")
    parser.add_argument('args', nargs=1, help='Hostname (SSH) to reach the BTS at')

    cmdline = parser.parse_args()

    Globals.bts = cmdline.args[0]
    if cmdline.band:
        Globals.band = cmdline.band

    if cmdline.set_calib_val:
        set_cfg_calib_val(cmdline.set_calib_val)
        exit(0)

    if cmdline.get_calib_val:
        print(get_cfg_calib_val())
        exit(0)

    Globals.orig_calib_val = cmdline.calib_val
    if Globals.orig_calib_val is None:
        Globals.orig_calib_val = get_cfg_calib_val() or '0'
    Globals.calib_val = Globals.orig_calib_val

    print('Starting out with clock calibration value %s' % Globals.calib_val)

    #call('systemctl', 'stop', 'osmo-bts-sysmo')
    reload_dsp()

    if cmdline.arfcn:
        Globals.arfcn = cmdline.arfcn
    else:
        arfcns = call_sysmobts_calib('scan')
        best_arfcn_line = arfcns.splitlines()[-1]
        Globals.arfcn = best_arfcn_line.split(':')[0].split(' ')[-1]
        try:
            int(Globals.arfcn)
        except:
            error('Error while scanning bands')

    print('Using ARFCN %r' % Globals.arfcn)

    collected_values = []

    passes = cmdline.passes
    if passes < 1:
        passes = 1

    for i in range(passes):
        print('\npass %d of %d' % (i+1, passes))
        o = call_sysmobts_calib('calibrate', '-a', Globals.arfcn)
        for m in result_re.finditer(o):
            collected_values.append(int(m.group(1)))

        collected_values = list(sorted(collected_values))
        print(collected_values)
        if not collected_values:
            continue

        best_values = collected_values
        if len(best_values) > 3:
            best_values = best_values[1:-1]

        avg = sum(best_values) / len(best_values)
        Globals.calib_val = str(int(avg))
        print('clock-calibration: started with %s, current=%s' %
              (Globals.orig_calib_val, Globals.calib_val))

    print('RESULT:', Globals.calib_val, ' (was %s)' % Globals.orig_calib_val)

    cfg_calib_val = get_cfg_calib_val()
    if Globals.calib_val != cfg_calib_val:
        a = ask('osmo-bts-sysmo.cfg currently has %s\nmodify osmo-bts-sysmo.cfg to clock-calibration %s? (ok, no)'
                % (cfg_calib_val, Globals.calib_val),
                valid_answers=('ok', 'no', ''))
        if a == 'ok':
            set_cfg_calib_val(Globals.calib_val)
    call('systemctl', 'start', 'osmo-bts-sysmo')
# vim: shiftwidth=4 expandtab tabstop=4
