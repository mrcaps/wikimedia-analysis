#Diff and compilation utils for wikimedia trace

## dirs

### patch-diff/[timestamp-start]-[timestamp-end].json
a patch valid from timestamp-start to timestamp-end

### patch-full/...
content that should be copied in at all times (private password dirs)

### output

json-diff requires
``` 
pip install jsontools
```