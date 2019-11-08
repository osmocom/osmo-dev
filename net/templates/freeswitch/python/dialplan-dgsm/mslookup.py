#!/usr/bin/env python3
# This can be started standalone for testing (see ./mslookup.py -h)
import argparse
import ctypes
import time

result = None

try:
	lib = ctypes.cdll.LoadLibrary('libosmomslookup.so')
except:
	raise MsLookupException('''
Loading libosmomslookup failed.
If libosmocore was built with address sanitizer, try something like
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libasan.so.5 my_script.py
''')


def init():
	global lib

	for init_component in ['logging', 'dns']:
		name = 'osmo_mslookup_s_init_%s' % init_component
		func = getattr(lib, name)
		assert func()

	if not lib.osmo_mslookup_s_init():
		raise RuntimeError('Initializing mslookup failed (returned False)')


def result_cb(request_handle, v4ip_b, v4port, v6ip_b, v6port, age):
	global result
	v4 = {'ip': v4ip_b.decode('ascii'), 'port': v4port } if v4ip_b else None
	v6 = {'ip': v6ip_b.decode('ascii'), 'port': v6port } if v6ip_b else None
	result = {'v4': v4, 'v6':v6, 'age': age}


# See osmo_mslookup_s_callback_t
C_RESULT_CB_T = ctypes.CFUNCTYPE(None, ctypes.c_uint,
	ctypes.c_char_p, ctypes.c_uint,
	ctypes.c_char_p, ctypes.c_uint,
	ctypes.c_uint)
c_result_cb = C_RESULT_CB_T(result_cb)


def resolve(id_type, id, service, timeout_ms=3000):
	global result

	init()

	request_handle = lib.osmo_mslookup_s_request(ctypes.c_char_p(id_type.encode('ascii')),
						     ctypes.c_char_p(str(id).encode('ascii')),
						     ctypes.c_char_p(service.encode('ascii')),
						     timeout_ms, c_result_cb)
	if not request_handle:
		raise MsLookupException('mslookup.query(by=%r, id=%r, service=%r) failed (returned 0)'
					% (id_type, id, service))

	step_ms = 100
	for i in range(0, timeout_ms + 1000, step_ms):
		lib.osmo_select_main_ctx(0)
		if result:
			return result
		time.sleep(step_ms / 1000)

	lib.osmo_mslookup_s_request_cleanup(request_handle)
	raise RuntimeError('mslookup library did not call the callback!')


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('id', type=int)
	parser.add_argument('-i', '--id-type', default='msisdn', help='default: "msisdn"')
	parser.add_argument('-s', '--service', default='sip.voice', help='default: "sip.voice"')
	parser.add_argument('-t', '--timeout', type=int, default='100', help='in milliseconds, default: 100')
	args = parser.parse_args()

	result = resolve(args.id_type, args.id, args.service, args.timeout)
	print('Result: ' + str(result))


if __name__ == '__main__':
	main()
