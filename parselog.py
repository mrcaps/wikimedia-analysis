"""Parse the output of writelog.sh into info about git commits.
"""
import argparse
import json
import sys

SEP="@@@@@"

def parse_diff(st):
	"""Parse a commit diff from the given string.

	Args:
		st: diff string
	"""
	D_BEGIN = 1
	D_FILES = 2
	D_HEADER = 3
	D_BODY = 4

	state = D_BEGIN

	def add_diff():
		putf = fromfile
		if fromfile != tofile:
			if fromfile == "dev/null":
				putf = tofile
			else:
				putf = fromfile
				#print("WARNING: fromfile!=tofile")
		part["files"][putf]["text"] = curtxt

	part = {"files": dict()}
	fromfile = ""
	tofile = ""
	curtxt = ""
	for l in st.split("\n"):
		if state == D_BEGIN:
			if len(l) > 0:
				state = D_FILES
		if state == D_FILES:
			if len(l) == 0:
				state = D_HEADER
			else:
				(ins, rem, fname) = l.split()
				part["files"][fname] = {
					"ins": ins,
					"rem": rem
				}
		elif state == D_HEADER:
			#expect
			#	index md5..md5
			#	new file
			#	deleted file
			#	new mode
			#	old mode
			#	Binary files
			if l.startswith("---"):
				(_, fromfile) = l.split()
				#XXX: don't assume a/
				fromfile = fromfile[fromfile.find("/")+1:]
			elif l.startswith("+++"):
				(_, tofile) = l.split()
				tofile = tofile[tofile.find("/")+1:]
				state = D_BODY							
		elif state == D_BODY:
			if l.startswith("diff --git"):
				#print "CURTXT", curtxt, "ff", fromfile, "tf", tofile
				add_diff()
				curtxt = ""
				state = D_HEADER
			elif not l.startswith("@@"):
				curtxt += l + "\n"

	#print "CURTXT", curtxt, "ff", fromfile, "tf", tofile
	if len(curtxt) > 0:
		add_diff()

	#/for
	return part	

def parse(fin):
	"""Parse tuples from the given input

	Args:
		fin: file pointer
	"""
	last = None
	field = None
	for l in fin:
		if l.startswith(SEP+SEP):
			if last:
				last["diff"] = parse_diff(last["diff"])
				yield last
			last = dict()
		elif l.startswith(SEP):
			#trim last newline
			if field and field in last:
				last[field] = last[field][:-1]
			field = l.strip()[len(SEP):]
		else:
			if not field in last:
				last[field] = ""
			last[field] += l

def print_times(iput):
	for tup in parse(iput):
		print tup["time"]

def print_files(iput):
	for tup in parse(iput):
		if "diff" in tup:
			for (fname, cont) in tup["diff"]["files"].items():
				print fname

def write_json(iput, fname):
	with open(fname, "w") as fp:
		json.dump(list(parse(iput)), fp, indent=2)

def write_json(iput, fname, filter=lambda x: True):
	changes = []
	for tup in parse(iput):
		if filter(tup):
			changes.append(tup)
	with open(fname, "w") as fp:
		json.dump(changes, fp, indent=2)

def filter_has_file(name):
	"""Filter restricted to only those files with a given name
	"""
	def fn(d):
		if "diff" in d:
			if "files" in d["diff"]:
				if name in d["diff"]["files"]:
					return True
		return False
	return fn

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("mode")
	args = parser.parse_args()

	if args.mode == "filtered":
		write_json(sys.stdin, "filtered-mysql.json",
			filter_has_file("manifests/mysql.pp"))
	elif args.mode == "unfiltered":
		write_json(sys.stdin, "all-changes.json")
	elif args.mode == "print_files":
		print_files(sys.stdin)

	