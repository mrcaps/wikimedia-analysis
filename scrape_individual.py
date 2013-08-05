if __name__ == "__main__":
	def get_gerrit_change(cid):
		detail = getpage("https://gerrit.wikimedia.org/r/changes/%d/detail" % cid)
		#)]}' at the beginning of the change
		CRUFT_LENGTH = 4
		return json.loads(detail[4:])

	bugs = {
		1: {
			
		}
	}

	for (bugid, bug) in bugs:
		print bugid
		#Gerrit detail json like:
		#	https://gerrit.wikimedia.org/r/changes/67311/detail
		#where 67311 is the change id.