"""Scrape a set of Ganglia pages for underlying raw data."""
import bs4
from bs4 import BeautifulSoup
import urllib
import urllib2
import sys
import unittest
import os
import time
import random

import logging as log
log.basicConfig(level=log.INFO)

def getpage(loc):
	#data = urllib.urlencode({"k": "v"})
	data = urllib.urlencode({})
	headers = { "User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1468.0 Safari/537.36" }
	req = urllib2.Request(loc, data, headers)
	try:
		return urllib2.urlopen(req)
	except urllib2.URLError:
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

if __name__ == "__main__":
	#unittest.main()

	run_downloader()