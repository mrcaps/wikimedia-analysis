"""
Scrape things:
 * a set of Ganglia pages for underlying raw data.
 * a set of bugs for parsing out gerrit links
"""

import urllib
try:
	from urllib2 import Request, urlopen, URLError
except:
	from urllib.request import Request, urlopen
	from urllib.error import URLError
import sys
import unittest
import os
import time
import random
import re
import csv
import traceback

#require: easy_install beautifulsoup4
import bs4
from bs4 import BeautifulSoup
#require: easy_install xmltodict
import xmltodict

import json

import logging as log
log.basicConfig(level=log.INFO)

def getpage(loc, data=None, header_override=None):
	#data = urllib.urlencode({"k": "v"})
	headers = {
		"User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1468.0 Safari/537.36",
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
		"Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
		"Accept-Encoding": "none",
		"Accept-Language": "en-US,en;q=0.8",
		"Cache-Control": "max-age=0",
		"Connection": "keep-alive"}
	if header_override is not None:
		for (k, v) in header_override.items():
			headers[k] = v
	req = Request(loc, data, headers)
	try:
		return urlopen(req)
	except (URLError, e):
		log.error("Couldn't open URL %s" % loc)
		log.error(e)
		return None

def readpage(loc):
	pl = getpage(loc)
	if pl is None:
		return None
	else:
		return pl.read()

def readstatic(loc):
	with open(loc, "r") as fp:
		return fp.read()

class RequestTest(unittest.TestCase):
	def test_req(self):
		pth = "http://www.mrcaps.com"
		#pth = "http://ganglia.wikimedia.org/latest/?t=yes&m=cpu_report&r=year&s=by%20name&hc=4&mc=2"
		self.assertTrue( len(readpage(pth)) > 1000 )

	def test_readstatic(self):
		self.assertTrue( len(readstatic("testdata/ganglia-home.html")) > 1000 )

	def test_downloader(self):
		down = Downloader()

		sources = down.extract_sources(readstatic("testdata/ganglia-home.html"))
		hosts = down.extract_nodes(readstatic("testdata/ganglia-nodes.html"))
		csvs = down.extract_csvs(readstatic("testdata/ganglia-node.html"))

def try_makedirs(pth):
	try:
		os.makedirs(pth)
	except:
		pass

def readpage_cache(loc, writeto, usecache, dlsleep=True):
	"""
	Args:
		dlsleep: sleep a random amount before downloading
	"""
	if os.path.exists(writeto) and usecache:
		return readstatic(writeto)
	else:
		log.info("Downloading " + loc)
		try_makedirs(os.path.split(writeto)[0])
		if dlsleep:
			time.sleep(random.random())
		cont = readpage(loc)
		if cont is not None:
			with open(writeto, "w") as fp:
				fp.write(cont)
		return cont

class Downloader(object):
	def __init__(self):
		pass
	
	def run(self, baseurl, outdir, usecache=True):
		def getloc(*parts):
			return os.path.join(*([outdir] + list(parts)))
		
		rootcont = readpage_cache(baseurl, getloc("index.html"), usecache)
		srcs = self.extract_sources(rootcont)

		for src in srcs:
			srccont = readpage_cache(
				self.get_source_url(baseurl, src),
				getloc(src, "index.html"),
				usecache)
			for node in self.extract_nodes(srccont):
				nodecont = readpage_cache(
					self.get_node_url(baseurl, src, node),
					getloc(src, node + ".html"),
					usecache)
				for csvp in self.extract_csvs(nodecont):
					l = csvp.find("m=")
					if l < 0:
						log.warn("Could not find metric in plot csv url")
					mname = csvp[l+2:]
					mname = mname[:mname.find("&")]
					csvc = readpage_cache(
						baseurl + csvp,
						getloc(src, node, mname + ".csv"),
						usecache)

	def parse_tree(self, treecont):
		"""
		Fragile; don't use me.

		Args:
			treecont: content of ganglia tree
		"""
		soup = BeautifulSoup(treecont)
		#fragile!
		links = soup.find_all("table")[1].find_all("a")
		dct = dict()
		for lnk in links:
			dct[lnk.contents[0]] = lnk["href"]
		return dct

	def get_source_url(self, baseurl, source, timerange="year"):
		return "%s/?c=%s&r=%s" % (baseurl, source, timerange)

	def get_node_url(self, baseurl, source, node, timerange="year"):
		return "%s/?c=%s&h=%s&r=%s" % (baseurl, source, node, timerange)

	def extract_sources(self, pagecont):
		"""Get list of sources from the given page content."""
		soup = BeautifulSoup(pagecont)
		sources = soup.find_all("select", attrs={"name": "c"})[0]
		srcvals = []
		for src in sources:
			if type(src) == bs4.element.Tag:
				v = src["value"]
				if v != "":
					srcvals.append(v)
		return srcvals

	def extract_nodes(self, pagecont):
		"""Get node names from the given page content."""
		soup = BeautifulSoup(pagecont)
		hosts = soup.find_all("select", attrs={"name": "h"})[0]
		hostvals = []
		for host in hosts:
			if type(host) == bs4.element.Tag:
				v = host["value"]
				if v != "":
					hostvals.append(v)
		return hostvals

	def extract_csvs(self, pagecont):
		"""Get CSV data links from the given page content."""
		soup = BeautifulSoup(pagecont)
		csvs = soup.find_all("button", attrs={"title": "Export to CSV"})
		hrefs = []
		for lnk in csvs:
			ocl = lnk["onclick"]
			ocl = ocl[ocl.find("'")+1:ocl.rfind("'")]
			if ocl.startswith("./"):
				ocl = ocl[2:]
			hrefs.append(ocl)
		return hrefs

	def extract_metrics(self, pagecont):
		"""Get monitoring metrics from the given page content."""
		soup = BeautifulSoup(pagecont)
		#fragile!
		metrics = soup.find_all(id="metrics-picker")[0]
		metvals = []
		for met in metrics:
			metvals.append(met["value"])
		return metvals

def run_downloader():
	down = Downloader()
	log.info("start download")
	down.run("http://ganglia.wikimedia.org/latest/", "data")
	log.info("done download")

class BugScraper():
	def __init__(self):
		pass

	def run(self, bugzilla_loc, first_bug=1, last_bug=52535, outdir="bugs", outfile="bugs.json"):
		"""Grab list of bugs from bugzilla, dump to outfile.

		Args:
			bugzilla_loc: location of bugzilla main, including trailing forwardslash
			last_bug: last bug id
		"""
		try:
			os.makedirs(outdir)
		except:
			pass
		def get_bug_path(bid):
			return os.path.join(outdir, "%s.json" % (bid))

		for bug in range(first_bug, last_bug):
			log.info("Grab bug %d" % bug)

			bout = get_bug_path(bug)
			if not os.path.exists(bout):
				try:
					dlpage = "%sshow_bug.cgi?ctype=xml&id=%s" % (bugzilla_loc, bug)
					dct = xmltodict.parse(getpage(dlpage).read())
					#write out to separate dir
					with open(bout, "w") as fp:
						json.dump(dct, fp)
				except:
					log.error("Couldn't download bug %d" % bug)
					traceback.print_exc()

				time.sleep(random.random() * 0.1)

		bugs = dict()
		for bug in range(first_bug, last_bug):
			log.info("Collect bug %d" % bug)
			bout = get_bug_path(bug)
			with open(bout, "r") as fp:
				bjs = json.load(fp)
			bugs[bug] = bjs["bugzilla"]["bug"]

		with open(outfile, "w") as fp:
			json.dump(bugs, fp, indent=4)


	def correlate_changeids(self, outdir="bugs/changeids", infile="bugs.json", outfile="bugs-commits.csv"):
		"""For each bug in bugs, determine if it has a gerrit change.
		For those that do, find the gerrit change and get the associated commit.
		Dump those commits to bugs/changeids
		"""

		bugs = None
		with open(infile, "r") as fp:
			bugs = json.load(fp)

		try:
			os.makedirs(outdir)
		except:
			pass
		def get_out_path(bid):
			return os.path.join(outdir, "%s.json" % (bid))

		gerrit_url = "https://gerrit.wikimedia.org/"
		pat = re.compile(gerrit_url + "r/#/c/(\\d+)/")

		def get_gerrit_change_detail(cid):
			url = "%sr/changes/%d/detail" % (gerrit_url, cid)
			detail = getpage(url).read()
			#)]}' at the beginning of the change
			CRUFT_LENGTH = 4
			return json.loads(detail[4:])

		def get_gerrit_change_detail_service(cid):
			"""Get UI change detail for the given change id
			This isn't really guaranteed to keep working, but gives revision hashes.
			(in .result.patchSets[n].revision.id)
			"""
			url = "%sr/gerrit_ui/rpc/ChangeDetailService" % (gerrit_url)
			data = {
				"id": 1,
				"jsonrpc": "2.0",
				"method": "changeDetail",
				"params": [{
					"id": cid
				}]
			}
			data_encoded = bytes(json.dumps(data), "utf-8")
			headers = {
				"Accept": "application/json,application/json,application/jsonrequest",
				"Content-Type": "application/json; charset=UTF-8",
				"Content-Length": len(data_encoded)
			}
			detail = getpage(url, data_encoded, headers).read()
			jsr = json.loads(detail.decode())
			if "result" in jsr:
				return jsr["result"]
			else:
				return None

		collectable = []

		for (bugid, bug) in bugs.items():
			if "long_desc" in bug:
				if isinstance(bug["long_desc"], dict):
					bug["long_desc"] = [bug["long_desc"]]
				for desc in bug["long_desc"]:
					if "thetext" in desc and desc["thetext"] is not None:
						matches = pat.finditer(desc["thetext"])
						for match in matches:
							changeno = int(match.group(1))
							#Gerrit detail json like:
							#	https://gerrit.wikimedia.org/r/changes/67311/detail
							#where 67311 is the change id.
							try:
								outpath = get_out_path(bugid)
								if not os.path.exists(outpath):
									log.info("Collect change id %s" % bugid)
									cont = get_gerrit_change_detail_service(changeno)
									if cont is None:
										continue
									with open(outpath, "w") as fp:
										json.dump(cont, fp)
								collectable.append((bugid, outpath))
							except:
								log.error("Couldn't collect change id %s" % bugid)
								traceback.print_exc()

		#collect change ids
		with open(outfile, "wt") as fp:
			writer = csv.writer(fp)
			writer.writerow(["bug", "revhash"])

			for (bugid, idpath) in collectable:
				with open(idpath, "r") as fp:
					js = json.load(fp)
					for ps in js["patchSets"]:
						writer.writerow([bugid, ps["revision"]["id"].strip()])


def run_bugscraper():
	scrape = BugScraper()
	log.info("start bug scrape")
	#scrape.run("https://bugzilla.wikimedia.org/")
	log.info("done bug scrape")

	log.info("start correlate change ids")
	scrape.correlate_changeids()
	log.info("done correlate change ids")

if __name__ == "__main__":
	#unittest.main()

	if len(sys.argv) <= 1:
		print("Usage: scrape.py [action] where [action] one of:")
		print(" download: download time series data")
		print(" bugscrape: scrape bugs")
		sys.exit(1)

	cmd = sys.argv[1]
	if cmd == "download":
		run_downloader()
	elif cmd == "bugscrape":
		run_bugscraper()