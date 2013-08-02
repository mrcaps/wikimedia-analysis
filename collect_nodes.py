"""Collect node names from timeseries data into nodes.csv

"""

import argparse
import glob
import os
import logging as log
log.basicConfig(level=log.DEBUG)

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--filter", 
		help="glob pattern to match for cluster directories",
		default="*")
	parser.add_argument("--output", 
		help="output file name",
		default="nodes.csv")
	args = parser.parse_args()

	with open(args.output, "w") as fp:
		for subpath in glob.iglob(os.path.join("timeseries", args.filter)):
			log.info("Accepting directory %s" % (subpath))
			for nodename in os.listdir(subpath):
				nodepath = os.path.join(subpath, nodename)
				if os.path.isdir(nodepath):
					fp.write(nodename)
					fp.write("\n")