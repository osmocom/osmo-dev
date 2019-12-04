import json
import os
import subprocess

script_dir = os.path.dirname(__file__)
timeout_ms = 2000

def query_mslookup(query_str):
	result_line = subprocess.check_output([
		'osmo-mslookup-client', query_str, '-f', 'json'])
	if isinstance(result_line, bytes):
		result_line = result_line.decode('ascii')
	return json.loads(result_line)

def query_mslookup_msisdn(msisdn):
	return query_mslookup('sip.voice.%s.msisdn' % str(msisdn))

def handler(session, args):
	print('[dialplan-dgsm] handler')
	msisdn = session.getVariable('destination_number')
	print('[dialplan-dgsm] resolving: sip.voice.' + str(msisdn) + '.msisdn')

	# Run mslookup.py. In theory, we should be able to import it and call mslookup.resolve() directly, however this
	# has lead to hard-to-debug segfaults when calling it the second time. For now, use a separate python process.
	try:
		result = query_mslookup_msisdn(msisdn)

		print('[dialplan-dgsm] result: ' + str(result))

		# This example only makes use of IPv4
		if not result['v4']:
			print('[dialplan-dgsm] no IPv4 result from mslookup')
			session.hangup('UNALLOCATED_NUMBER')
			return

		sip_ip, sip_port = result['v4']  # osmo-dev defaults: same as ${SIPCON_LOCAL}
		dial_str = 'sofia/internal/sip:{}@{}:{}'.format(msisdn, sip_ip, sip_port)
		print('[dialplan-dgsm] dial_str: ' + str(dial_str))

		session.execute('bridge', dial_str)
	except:
		print('[dialplan-dgsm]: could not resolve MSISDN {} with mslookup.py'.format(msisdn))
		session.hangup('UNALLOCATED_NUMBER')


# Freeswitch refuses to load the module without this
def fsapi(session, stream, env, args):
	stream.write(env.serialize())

if __name__ == '__main__':
	import json
	import sys
	print(json.dumps(query_mslookup(sys.argv[1])))
