import logging as log
log.basicConfig(level=log.DEBUG)
import subprocess
import unittest
from distutils import dir_util
import os

class Patcher(object):
	def __init__(self, repopath, patchpath="patch-full", diffpath="patch-diff"):
		self.repopath = repopath
		self.patchpath = patchpath
		self.diffpath = diffpath

	def patch(self, timestamp):
		#copy over the tree...
		try:
			log.info("Copying patch files")
			dir_util.copy_tree(self.patchpath, self.repopath)
		except Exception, e:
			log.error("Patch error:" + str(e))

	def grep_patch(self, fpath, orig, replace):
		"""Replace the text _orig_ in file 
		with path _fpath_ with _replace_"""
		replaced = None
		with open(fpath, "r") as fp:
			contents = fp.read()
			replaced = contents.replace(orig, replace)
		if replaced:
			with open(fpath, "w") as fp:
				fp.write(replaced)

	def diff_patch(self):
		"""Patch from 'our' diff format

		see patch-diff for examples.
		"""
		for fname in os.listdir(self.diffpath):
			self.__apply_diff(os.path.join(self.diffpath, fname))

	def __apply_diff(self, fpath):
		cur = {
			"file": None,
			"add": "",
			"del": ""
		}

		def run_apply():
			log.info("Patching %s" % cur["file"])

			self.grep_patch(os.path.join(self.repopath, cur["file"]), 
				cur["del"], cur["add"])
			cur["add"] = ""
			cur["del"] = ""
			cur["file"] = None

		with open(fpath, "r") as fp:
			for line in fp:
				line = line.strip()
				if line.startswith("#") or len(line) == 0:
					continue
				elif line.startswith("+"):
					if len(cur["add"]) > 0:
						cur["add"] += "\n"
					cur["add"] += line[1:]
				elif line.startswith("-"):
					if len(cur["del"]) > 0:
						cur["del"] += "\n"
					cur["del"] += line[1:]
				else:
					#we have a title
					if cur["file"]:
						run_apply()
					cur["file"] = line

			run_apply()

class Differ(object):
	def __init__(self, repopath="operations-puppet"):
		self.repopath = repopath
		self.patcher = Patcher(repopath)

	def checkout(self, revision):
		"""Check out at the given revision."""
		out = subprocess.check_output(
			["git", "checkout", revision], cwd=self.repopath)
		#seems to go to stderr?

	def compile(self):
		"""Compile at the current revision."""
		log.info("Compiling...")
		out = subprocess.check_output(["puppet",
			"apply", "manifests/site.pp", "--noop",
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

	def test_patch(self):
		p = Patcher(repopath="operations-puppet")
		p.patch(1369159391)

class IncTest(unittest.TestCase):
	def test_dpatch(self):
		p = Patcher(repopath="operations-puppet")
		p.diff_patch()

if __name__ == "__main__":
	unittest.main()

	#suite = unittest.TestSuite()
	#suite.addTests(IncTest)
	#unittest.TextTestRunner().run(suite)