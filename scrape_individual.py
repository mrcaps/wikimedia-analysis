import re


import urllib2, urllib
import json
def getpage(loc):
	#data = urllib.urlencode({"k": "v"})
	data = urllib.urlencode({})
	headers = { "User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1468.0 Safari/537.36" }
	print "requesting", loc
	req = urllib2.Request(loc, data, headers)
	try:
		return urllib2.urlopen(req)
	except urllib2.URLError:
		return None

if __name__ == "__main__":
	bugs = {
		1: {
			"long_desc": [
				{"commentid": 250406,
				"thetext": "Jenkins job is https://gerrit.wikimedia.org/r/#/c/68566/ , to be applied, it requires a change to Jenkins Job Builder which I have submitted upstream https://review.openstack.org/#/c/32965/ I have generated the job and added the Zuul triggers https://gerrit.wikimedia.org/r/68563 At least one build succeeded. https://integration.wikimedia.org/ci/job/apps-android-commons-build/ That should be fine for you. If the job works properly we will make it voting (and thus block the change upon jenkins job failure). :)"}
			] 
		}
	}

	gerrit_url = "https://gerrit.wikimedia.org/"
	pat = re.compile(gerrit_url + "r/#/c/(\\d+)/")

	def get_gerrit_change(cid):
		detail = getpage("%sr/changes/%d/detail" % (gerrit_url, cid)).read()
		#)]}' at the beginning of the change
		CRUFT_LENGTH = 4
		return json.loads(detail[4:])

	for (bugid, bug) in bugs.items():
		if "long_desc" in bug:
			for desc in bug["long_desc"]:
				matches = pat.finditer(desc["thetext"])
				for match in matches:
					changeno = int(match.group(1))

					#Gerrit detail json like:
					#	https://gerrit.wikimedia.org/r/changes/67311/detail
					#where 67311 is the change id.
					cont = get_gerrit_change(changeno)
					print cont