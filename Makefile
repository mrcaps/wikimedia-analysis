filtered-mysql.json:
	./writelog.sh | python parselog.py filtered
all-changes.json:
	./writelog.sh | python parselog.py unfiltered

nodes-db.csv:
	python collect_nodes.py --filter "MySQL*" --output $@
nodes-all.csv:
	python collect_nodes.py --filter "*" --output $@