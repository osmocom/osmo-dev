import json
import os
import subprocess

script_dir = os.path.dirname(__file__)
timeout_ms = 5000

def handler(session, args):
	print('[dialplan-dgsm] handler')
	msisdn = session.getVariable('destination_number')
	print('[dialplan-dgsm] resolving: sip.voice.' + str(msisdn) + '.msisdn')

	# Run mslookup.py. In theory, we should be able to import it and call mslookup.resolve() directly, however this
	# has lead to hard-to-debug segfaults when calling it the second time. For now, use a separate python process.
	result = {}
	try:
		result_json = subprocess.check_output([script_dir + '/mslookup.py', str(msisdn), '-t', str(timeout_ms)])
		result = json.loads(result_json)
	except:
		print('[dialplan-dgsm]: failed to run mslookup.py!')
		session.hangup('UNALLOCATED_NUMBER')

	print('[dialplan-dgsm] result: ' + str(result))

	# This example only makes use of IPv4
	if not result['v4']:
		print('[dialplan-dgsm] no IPv4 result from mslookup')
		session.hangup('UNALLOCATED_NUMBER')
		return

	mncc_ip = result['v4']['ip']  # osmo-dev defaults: same as ${SIPCON_LOCAL}
	mncc_port = result['v4']['port']  # osmo-dev defaults: same as ${SIPCON_LOCAL_PORT}
	dial_str = 'sofia/internal/sip:{}@{}:{}'.format(msisdn, mncc_ip, mncc_port)
	print('[dialplan-dgsm] dial_str: ' + str(dial_str))

	session.execute('bridge', dial_str)


# Freeswitch refuses to load the module without this
def fsapi(session, stream, env, args):
	stream.write(env.serialize())
