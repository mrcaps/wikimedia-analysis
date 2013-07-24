import logging as log
log.basicConfig(level=log.DEBUG)
import subprocess
import unittest
from distutils import dir_util
import os
import json
import time

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
		retries = 0
		while retries < 4:
			try:
				log.info("Copying patch files from %s to %s" % (self.patchpath, self.repopath))
				dir_util.copy_tree(self.patchpath, self.repopath)
				log.info("Copy success")
				break
			except Exception, e:
				log.error("Patch error:" + str(e))
				##XXX: dumb hack for dir_util.copy_tree error
				os.makedirs(os.path.join(self.repopath, "private", "manifests"))
				time.sleep(0.1)
				retries += 1
		#do the diff patch
		self.diff_patch(timestamp)

	def grep_patch(self, fpath, orig, replace):
		"""Replace the text _orig_ in file 
		with path _fpath_ with _replace_"""
		replaced = None
		if not os.path.exists(fpath):
			log.warning("No file to patch: %s" % (fpath))
			return
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

class Differ(object):
	def __init__(self, repopath="operations-puppet", nodeslist="nodes.csv"):
		"""
		Args:
			repopath: git repository path
			nodeslist: list of nodes, one per line
		"""
		self.repopath = repopath
		self.nodeslist = nodeslist
		self.outpath = "/var/output"
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

	def clean_checkout(self):
		"""Clean up the working copy."""

		try:
			out = subprocess.check_output(
				["git", "clean", "-d", "-f", "-f"], cwd=self.repopath)
			self.checkout(".")
		except subprocess.CalledProcessError, e:
			log.error("Couldn't clean revision %s" % revision)
			log.error("output was %s" % e.output)			

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
				"--no-daemonize", "--debug",
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

	def run_filtered(self, nodes, fcommits, filt):
		"""Run a compile over the given range, evaluating diffs only
		on the filtered commits.

		Args:
			nodes: which nodes to evaluate
			fcommits: file to get commits from
			filt: function(commit) -> [True|False]
		"""
		log.info("Running filtered over |nodes|=%d" % (len(nodes)))

		with open(fcommits, "r") as fp:
			commits = json.load(fp)
		commits.sort(cmp=lambda a, b: int(a["time"]) - int(b["time"]))

		torun = []
		for cdx in xrange(1, len(commits)):
			com = commits[cdx]
			com_prev = commits[cdx-1]
			if filt(com):
				torun.append((com_prev, com))

		for node in nodes:
			for (com_prev, com) in torun:
				com_prev_path = self.get_compiled(com_prev, node)
				com_path = self.get_compiled(com, node)
				self.compute_diff(com_prev_path, com_path)

	def run_single_commit(self, node, fcommits, hash):
		"""Get a diff for a single commit.

		Args:
			node: which node to evaluate
			fcommits: file to get commits from
			hash: the commit hash to evaluate (to last commit)
		"""
		log.info("Computing diff for single commit %s" % hash)

		with open(fcommits, "r") as fp:
			commits = json.load(fp)
		commits.sort(cmp=lambda a, b: int(a["time"]) - int(b["time"]))

		for cdx in xrange(1, len(commits)):
			com = commits[cdx]
			com_prev = commits[cdx-1]
			ts = int(com["time"])
			if com["hash"] == hash:
				com_prev_path = self.get_compiled(com_prev, node, use_cached=False)
				com_path = self.get_compiled(com, node, use_cached=False)
				res = self.compute_diff(com_prev_path, com_path)
				respath = self.__get_diff_path(com_path)
				if res == Differ.DIFF_YES:
					log.info("Computed diff into %s" % (com_path))
					with open(respath, "r") as fp:
						log.info("diff was:\n%s" % (fp.read()))
				else:
					log.info("No diff.")

	def run_bisect(self, nodes, fcommits, tmin, tmax):
		"""Run a compile over the given range, bisecting diff search

		Args:
			nodes: which nodes to evaluate
			fcommits: file to get commits from
			tmin: minimum commit timestamp
			tmax: maximum commit timestamp
		"""

		log.info("Running bisect over |nodes|=%d tmin=%d, tmax=%d" % 
			(len(nodes), tmin, tmax))

		with open(fcommits, "r") as fp:
			commits = json.load(fp)
		
		torun = []
		for com in commits:
			ts = int(com["time"])
			if ts >= tmin and ts <= tmax:
				torun.append(com)

		#sort by time
		torun.sort(cmp=lambda a, b: int(a["time"]) - int(b["time"]))

		for node in nodes:
			self.__cmp_region(torun, node, 0, len(torun)-1)

			#now, we might have spurious diffs from the "edges" of the bisections
			# remove all diffs, then compute from the commits we compiled.
			nodepath = self.get_out_path(node)
			for fn in os.listdir(nodepath):
				if fn.endswith(".diff"):
					os.remove(os.path.join(nodepath, fn))

		#recompute all diffs.
		self.compute_diffs(nodes)

	def __cmp_region(self, commits, node, lodx, hidx):
		log.info("__cmp_region from %d to %d" % (lodx, hidx))
		locom_path = self.get_compiled(commits[lodx], node)
		hicom_path = self.get_compiled(commits[hidx], node)
		print "locomp, hicomp = \n\t%s\n\t%s" % (locom_path, hicom_path)
		#compute the diff
		diff = self.compute_diff(locom_path, hicom_path)
		if diff != Differ.DIFF_NO and hidx > lodx + 1:
			#recurse into lower parts
			midpt = int((lodx + hidx)/2)
			self.__cmp_region(commits, node, lodx, midpt)
			self.__cmp_region(commits, node, midpt, hidx)

	def __node_to_string(self, node):
		(hostname, site) = node
		return "%s.%s.wmnet" % (hostname, site)

	def get_compiled(self, com, node, use_cached=True):
		"""get compiled filename for a given commit and node"""
		try:
			os.makedirs(self.get_out_path(node))
		except:
			pass
		comppath = os.path.join(self.get_out_path(node), self.get_out_file(node, com))
		if not os.path.exists(comppath) or not use_cached:
			log.info("compiling for node=%s @rev=%s..." % (node, str(com["hash"])))
			self.clean_checkout()
			self.checkout(com["hash"])
			log.info("patching...")
			self.patcher.patch(int(com["time"]))
			log.info("compiling into %s" % comppath)
			(hostname, site) = node
			cmpout = self.compile(hostname, site)
			with open(comppath, "w") as fp:
				fp.write(cmpout)
		return comppath

	DIFF_MAYBE = 0
	DIFF_NO = 1
	DIFF_YES = 2

	EXTENSION_DIFF = ".diff"

	def __get_diff_path(self, basepath):
		return basepath + Differ.EXTENSION_DIFF

	def compute_diff(self, patha, pathb):
		"""Compute diffs between commits that were written to patha and pathb.

		Returns:
			True if there is a diff
		"""
		def getjson(fname):
			try:
				with open(fname, "r") as fp:
					js = json.load(fp)
				return js
			except ValueError, e:
				log.error("could not load json for %s: %s" % (fname, e))
				return None

		jsa = getjson(patha)
		jsb = getjson(pathb)

		def write_result(contents):
			with open(self.__get_diff_path(pathb), "w") as fp:
				fp.write(contents)

		if (jsa and not jsb) or (not jsa and jsb):
			write_result('{"error":"unparseable"}\n')
			return Differ.DIFF_YES
		elif jsa and jsb:
			#canonicalize
			diff = json_diff(canonicalize(jsa), canonicalize(jsb))
			if len(diff) > 0:
				log.info("Got diff for commit " + pathb)
				write_result(diff)
				return Differ.DIFF_YES
			else:
				log.info("No diff for commit " + pathb)
				return Differ.DIFF_NO
		elif not jsa and not jsb:
			return Differ.DIFF_MAYBE
		
	def compute_diffs(self, nodes):
		"""Compute all diffs between commits for the given nodes."""
		for node in nodes:
			coms = []
			basepath = self.get_out_path(node)
			for fn in os.listdir(basepath):
				(name, ext) = os.path.splitext(fn)
				if ext.endswith("json"):
					(ts, hash) = name.split("-")
					coms.append((int(ts), hash, os.path.join(basepath, fn)))
			coms.sort()

			nodiffs = 0
			withdiffs = 0

			for dx in range(len(coms)-1):
				ca = coms[dx][2]
				cb = coms[dx+1][2]

				d = self.compute_diff(ca, cb)
				if d == Differ.DIFF_YES:
					withdiffs += 1
				elif d == Differ.DIFF_NO:
					nodiffs += 1

			log.info("%d commits with no diffs, %d commits with diffs on node %s" % (nodiffs, withdiffs, node))

	def collect_diffs(self, nodes, outfile):
		import hashlib
		import csv

		with open(outfile, "w") as outfp:
			writer = csv.writer(outfp)
			writer.writerow(["node", "timestamp", "commithash", "diffhash"])

			"""Collect all diffs into a single output file."""
			for node in nodes:
				basepath = self.get_out_path(node)
				for fn in os.listdir(basepath):
					(base, ext) = os.path.splitext(fn)
					if ext == Differ.EXTENSION_DIFF:
						(base, ext) = os.path.splitext(base)
						(ts, commithash) = base.split("-")
						with open(os.path.join(basepath, fn), "r") as fp:
							contents = fp.read()
						hasher = hashlib.md5()
						hasher.update(contents)
						writer.writerow([
							self.__node_to_string(node), 
							ts, commithash, hasher.hexdigest()])

def canonicalize_basic(js):
	js["data"]["edges"].sort()
	js["data"]["resources"].sort()
	for res in js["data"]["resources"]:
		if "line" in res:
			del res["line"]
	js["data"]["version"] = 1
	return js

def canonicalize(js):
	js["data"]["edges"].sort()
	js["data"]["resources"].sort()

	jsnew = dict()
	jsnew["edges"] = dict()
	for edge in js["data"]["edges"]:
		if not edge["source"] in jsnew["edges"]:
			jsnew["edges"][edge["source"]] = dict()

		target = edge["target"]
		if not target.startswith("Notify["):
			jsnew["edges"][edge["source"]][target] = True

	jsnew["resources"] = dict()
	for res in js["data"]["resources"]:
		if "line" in res:
			del res["line"]
		if "tags" in res:
			newtags = dict()
			for tag in res["tags"]:
				newtags[tag] = True
			res["tags"] = newtags
		if "type" in res and res["type"] != "Notify":
			jsnew["resources"][res["title"]] = res

	return jsnew

def json_diff(jsa, jsb):
	stream = StringIO()
	jsontools.jsondiff(jsa, jsb, stream=stream)
	stream.seek(0)
	return stream.getvalue()
	
class DifferTest(unittest.TestCase):
	def test_checkout(self):
		d = Differ()
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
		d.run_bisect([("db1001", "eqiad")], "filtered-mysql.json", 1367435786, 2000000000)

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
	#compute changes over these nodes
	nodelist = [("db1046", "eqiad")]
	nodelist = list(d.get_nodes())
	try:
		import generate_assignments
		nodelist = generate_assignments.get_my_nodes()
	except:
		log.error("Couldn't get local node list; reverting to manual")
	log.info("my nodes are %s" % (str(nodelist)))

	#run compile
	#d.run_bisect(nodelist, "filtered-mysql.json", 0, 2000000000)

	#run single compile
	#d.run_single_commit(("db1029", "eqiad"), 
	#	"all-changes.json", "2d289497c1298d21c21156e28995956c17adc9f0")

	#run compile filtered
	if False:
		def filter_has_mysql(com):
			return ("diff" in com and "files" in com["diff"] and 
				"manifests/mysql.pp" in com["diff"]["files"].keys())
		d.run_filtered(nodelist, "all-changes.json", filter_has_mysql)

	if True:
		d.run_bisect([("db1046","eqiad")], "all-changes.json", 0, 2000000000)

	if True:
		d.collect_diffs(nodelist, "diff-collected.csv")

if __name__ == "__main__":
	#unittest.main()
	real_run()

	#suite = unittest.TestSuite()
	#suite.addTests(IncTest)
	#unittest.TextTestRunner().run(suite)
