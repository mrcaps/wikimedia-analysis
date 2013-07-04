import logging as log
log.basicConfig(level=log.DEBUG)
import subprocess
import unittest

class Differ(object):
	def __init__(self, repopath="operations-puppet"):
		self.repopath = repopath

	def checkout(self, revision):
		"""Check out at the given revision."""
		out = subprocess.check_output(
			["git", "checkout", revision], cwd=self.repopath)
		#seems to go to stderr?

	def compile(self):
		"""Compile at the current revision."""
		out = subprocess.check_output(["puppet",
			"apply" "manifests/site.pp", "--noop",
			"--facts_terminus=facter", "--confdir=.",
			"--templatedir=./templates"], cwd=self.repopath)
		print("compile output")
		print(out)

	
class DifferTest(unittest.TestCase):
	def test_checkout(self):
		d = Differ()
		d.checkout("a9d80defc55ca8e1f5622e21994e457740d24d5e")
		d.checkout("8606d2bb5a62f71adf917bd2f485b393ebe3d961")

	def test_compile(self):
		d = Differ()
		d.checkout("cf985570ff5dcd5170cc8704747785a14364ff71")
		d.compile()

if __name__ == "__main__":
	unittest.main()