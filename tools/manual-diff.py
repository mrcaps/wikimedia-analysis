import json
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import jsontools

def json_diff(jsa, jsb):
	stream = StringIO()
	jsontools.jsondiff(jsa, jsb, stream=stream)
	stream.seek(0)
	return stream.getvalue()

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

def dodiff(patha, pathb):
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

	print json_diff(canonicalize(jsa), canonicalize(jsb))

if __name__ == "__main__":
	fn1 = "bad2/1322570501-e63672a80741440750229e861f68485719336443.json"
	fn2 = "bad2/1322572946-79130838179ea29af069c94b16d453df30a310cd.json"
	dodiff(fn1, fn2)