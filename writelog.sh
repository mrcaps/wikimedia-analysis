#write change log to a SEP-separated format for parselog.py
SEP=@@@@@
cd operations-puppet
git log -p --unified=0 --numstat --format="${SEP}${SEP}%n${SEP}time%n%ct%n${SEP}hash%n%H%n${SEP}subject%n%s%n${SEP}body%n${SEP}diff%n"