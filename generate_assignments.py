from differ import Differ
import socket
import os

def get_my_nodes():
	"""Get nodes assigned to this host for computation
	"""
	if not os.path.exists("/etc/cluster-hosts"):
		raise Exception("No cluster hosts specified")

	#grab list of hosts in cluster, in order
	hosts = []
	with open("/etc/cluster-hosts", "r") as fp:
		for line in fp:
			hosts.append(line.strip())

	d = Differ()
	diffnodes = list(d.get_nodes())
	
	#compute node->host assignments (round-robin)
	assigns = dict()
	dx = 0
	for item in diffnodes:
		assigns[item] = hosts[dx % len(hosts)]
		dx += 1

	myitems = []
	fqdn = socket.getfqdn()
	for (item, host) in assigns.items():
		if host == fqdn:
			myitems.append(item)
	return myitems

if __name__ == "__main__":
	print get_my_nodes()