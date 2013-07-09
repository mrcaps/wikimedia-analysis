import logging as log
log.basicConfig(level=log.DEBUG)
import subprocess
import unittest
from distutils import dir_util
import os
import json

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import jsontools

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

	def diff_patch(self, timestamp):
		"""Patch from 'our' diff format
		see patch-diff for examples.

		Args:
			timestamp: when to do the diff
		"""
		for fname in os.listdir(self.diffpath):
			(tstart, tend) = map(int, os.path.splitext(fname)[0].split("-"))
			if tstart < timestamp and timestamp < tend:
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

REV_HEAD = "."

class Differ(object):
	def __init__(self, repopath="operations-puppet", nodeslist="nodes.csv"):
		"""
		Args:
			repopath: git repository path
			nodeslist: list of nodes, one per line
		"""
		self.repopath = repopath
		self.nodeslist = nodeslist
		self.outpath = "output"
		self.patcher = Patcher(repopath)

	def checkout(self, revision):
		"""Check out at the given revision.

		Args:
			revision: the revision to check out, or "." for head
		"""
		try:
			out = subprocess.check_output(
				["git", "checkout", revision], cwd=self.repopath)
		except subprocess.CalledProcessError, e:
			log.error("Couldn't check out revision %s" % revision)
			log.error("output was %s" % e.output)
		#seems to go to stderr?

	def __extract_json(self, out):
		return out[out.index("{\n"):]

	def compile(self, hostname, site):
		"""Compile at the current revision.

		Args:
			hostname like db1001
			site like eqiad
		"""
		log.info("Compiling hostname=%s site=%s" % (hostname, site))
		try:
			cpenv = os.environ.copy()
			cpenv["FACTER_hostname"] = hostname
			cpenv["FACTER_site"] = site
			cpenv["FACTER_operatingsystem"] = "Ubuntu"
			#out = subprocess.check_output(["puppet",
			#	"apply", "manifests/site.pp", "--noop",
			#	"--facts_terminus=facter", "--confdir=.",
			#	"--templatedir=./templates"], cwd=self.repopath, env=cpenv)
			out = subprocess.check_output(["puppet",
				"master", "--facts_terminus=facter",
				"--compile=" + hostname,
				"--confdir=.", "--templatedir=./templates"], 
				cwd=self.repopath, env=cpenv)
			return self.__extract_json(out)
		except subprocess.CalledProcessError, e:
			log.error("Couldn't compile catalog (%s)" % e.cmd)
			log.error("output was %s" % e.output)
			return e.output

	def get_nodes(self):
		"""
		Returns:
			generator of (node, site)
		"""
		with open(self.nodeslist, "r") as fp:
			for line in fp:
				yield tuple(line.split(".")[0:2])

	def get_out_path(self, node):
		return os.path.join(self.outpath, node[0] + "." + node[1] + ".wmnet")

	def get_out_file(self, node, commit):
		return commit["time"] + "-" + commit["hash"] + ".json"

	def run(self, nodes, fcommits, tmin, tmax, skip_existing=True):
		"""Run a compile over the given range.

		Args:
			nodes: which nodes to evaluate
			fcommits: file to get commits from
			tmin: minimum commit timestamp
			tmax: maximum commit timestamp
		"""

		log.info("Running over |nodes|=%d tmin=%d, tmax=%d" % 
			(len(nodes), tmin, tmax))

		with open(fcommits, "r") as fp:
			commits = json.load(fp)
		for com in commits:
			ts = int(com["time"])
			if ts >= tmin and ts <= tmax:
				for node in nodes:
					(hostname, site) = node
					outpath = self.get_out_path(node)
					try:
						os.makedirs(outpath)
					except:
						pass
					comppath = os.path.join(outpath, self.get_out_file(node, com))
					if skip_existing and os.path.exists(comppath):
						log.info("skip existing %s" % comppath)
					else:
						log.info("compiling %s" % comppath)
						cmpout = self.compile(hostname, site)
						with open(comppath, "w") as fp:
							fp.write(cmpout)

	def compute_diffs(self, nodes):
		"""Compute all diffs between commits for the given nodes."""
		for node in nodes:
			coms = []
			basepath = self.get_out_path(node)
			for fn in os.listdir(basepath):
				(ts, hash) = os.path.splitext(fn)[0].split("-")
				coms.append((ts, hash, os.path.join(basepath, fn)))
			coms.sort()

			nodiffs = 0

			for dx in range(len(coms)-1):
				ca = coms[dx][2]
				cb = coms[dx+1][2]
				with open(ca, "r") as fp:
					jsa = json.load(fp)
				with open(cb, "r") as fp:
					jsb = json.load(fp)

				#canonicalize
				diff = json_diff(canonicalize(jsa), canonicalize(jsb))
				if len(diff) > 0:
					log.info("Got diff for commit " + cb)
					with open(cb + ".diff", "w") as fp:
						fp.write(diff)
				else:
					nodiffs += 1

			log.info("%d commits with no diffs on node %s" % (nodiffs, node))

def canonicalize(js):
	js["data"]["edges"].sort()
	js["data"]["resources"].sort()
	js["data"]["version"] = 1

def json_diff(jsa, jsb):
	stream = StringIO()
	jsontools.jsondiff(jsa, jsb, stream=stream)
	stream.seek(0)
	return stream.getvalue()
	
class DifferTest(unittest.TestCase):
	def test_checkout(self):
		d = Differ()
		d.checkout(REV_HEAD)
		d.checkout("a9d80defc55ca8e1f5622e21994e457740d24d5e")
		d.checkout("8606d2bb5a62f71adf917bd2f485b393ebe3d961")

	def test_patch(self):
		p = Patcher(repopath="operations-puppet")
		p.patch(1369159391)

	def test_dpatch(self):
		p = Patcher(repopath="operations-puppet")
		p.diff_patch(1369159391)

	def test_compile(self):
		d = Differ()
		d.checkout("cf985570ff5dcd5170cc8704747785a14364ff71")
		self.test_dpatch()
		d.compile("db1001", "eqiad")

	def test_nodeparse(self):
		d = Differ()
		self.assertTrue(len(list(d.get_nodes())) > 10)
		print list(d.get_nodes())

	def test_run(self):
		d = Differ()
		d.run([("db1001", "eqiad")], "filtered-mysql.json", 1367435786, 2000000000)

	def test_jsondiff(self):
		jsa = json.loads('{"foo": "bar", "zim": "bob", "d": {"nest": [1,2,3]}}')
		jsb = json.loads('{"woo": "baz", "zim": "bob", "d": {"nest": [1,2,5]}}')
		print json_diff(jsa, jsb)

class IncTest(unittest.TestCase):
	def test_compute(self):
		d = Differ()
		d.compute_diffs([("db1001", "eqiad")])

def real_run():
	d = Differ()
	#d.run([("db1001", "eqiad")], "filtered-mysql.json", 0, 2000000000)
	d.run(list(d.get_nodes()), "filtered-mysql.json", 0, 2000000000)

if __name__ == "__main__":
	#unittest.main()
	real_run()

	#suite = unittest.TestSuite()
	#suite.addTests(IncTest)
	#unittest.TextTestRunner().run(suite)