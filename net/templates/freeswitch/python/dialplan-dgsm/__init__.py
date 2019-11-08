import mslookup


def handler(session, args):
	print('[dialplan-dgsm] handler')
	msisdn = session.getVariable('destination_number')
	print('[dialplan-dgsm] resolving: sip.voice.' + str(msisdn) + '.msisdn')

	result = mslookup.resolve('msisdn', msisdn, 'sip.voice')
	print('[dialplan-dgsm] result: ' + str(result))

	# This example only makes use of IPv4
	if not result["v4"]:
		print("[dialplan-dgsm] no IPv4 result from mslookup")
		self.session.hangup('UNALLOCATED_NUMBER')

	mncc_ip = result["v4"]["ip"]  # osmo-dev defaults: same as ${SIPCON_LOCAL}
	mncc_port = result["v4"]["port"]  # osmo-dev defaults: same as ${SIPCON_LOCAL_PORT}
	dial_str = 'sofia/internal/sip:{}@{}:{}'.format(msisdn, mncc_ip, mncc_port)
	print('[dialplan-dgsm] dial_str: ' + str(dial_str))

	session.execute('bridge', dial_str)


# Freeswitch refuses to load the module without this
def fsapi(session, stream, env, args):
	stream.write(env.serialize())
