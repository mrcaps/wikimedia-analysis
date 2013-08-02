library(changepoint)
library(bcp)

getdatafiles = function(datadirs, scanpattern) {
  # Search for data files to load
  #
  # Args:
  #   datadirs: vector of which 
  #   scanpattern: e.g. *.csv
  #
  # Returns:
  #   data frame with datadir, fn (filename) columns
  files = adply(datadirs, 1, function(datadir) {
    data.frame(
      datadir = datadir,
      fn = list.files(path=datadir, recursive=TRUE, pattern=scanpattern),
      stringsAsFactors=FALSE
    )
  })
  #cut out cpu_report
  files = subset(files, !grepl("cpu_report", fn, fixed=TRUE))
  files
}

readsingle = function(loc) {
  # Read a single data file from location loc
  #
  # Args:
  #   loc: file location
  #
  # Returns:
  #   data frame with t (timestamp) and v (value) columns
  dat = read.csv(loc, col.names=c("t", "v"), sep=",")
  dat$t = strptime(dat$t, "%Y-%m-%dT%H:%M:%S+00:00")
  dat
}

readdata = function(datafiles) {
  # Read a set of datafiles, as produced, for e.g., by getdatafiles
  #
  # Args:
  #   datafiles: data frame of file locations with datadir, fn columns
  #
  # Returns:
  #   list of lists, each with info re: location and data (see readsingle)
  alply(datafiles, 1, function(r) {
    parts = strsplit(r$fn, "/")[[1]]
    list(
      datadir=r$datadir,
      fn=r$fn,
      node=parts[1],
      metric=parts[2],
      data=readsingle(paste(r$datadir, r$fn, sep="/"))
    )
  }, .progress="text")
}

findcps = function(series, method="SegNeigh") {
  # Find changepoints of a time series
  c = data.frame(t=c(), stat=c())
  tryCatch({
    if (method == "SegNeigh") {
      cps = cpt.mean(series$v, Q=10, method="SegNeigh", class=FALSE)
      pts = unique(cps$cps[(nrow(cps$cps)-cps$op.cpts + 1):nrow(cps$cps), 1])
      c = data.frame(
        t = series$t[pts],
        stat = rep(1, length(pts))
      )
    } else if (method == "BinSeg") { 
      cps = binseg.mean.cusum(series$v, Q=10, pen=1)
      pts = cps$cps[1,1:cps$op.cpts]
      stats = cps$cps[2,1:cps$op.cpts]
      c = data.frame(
        t=series$t[pts], #time
        stat=stats #test statistic
      )
    }
  }, error=function(e) {
    #why can't we put c here?
  })
  c
}

test.maketseries = function() {
  vals = c(1,1,1,1,1,1,1,2,2,2,2,2,2,1,1,1,1,1,5,5,5,50,5,5,5)
  c = data.frame(
    t = seq(1, length(vals)),
    v = vals  
  )
  c
}

test.findcps = function() {
  print(findcps(test.maketseries()))
}

#find probabilities of a changepoint at a given location
cpprobs = function(series, method="bcp") {
  if (method=="bcp") {
    #original
    #probs = bcp(series$v)$posterior.prob
    res = bcp(series$v, p0=1e-7, w0=1e-5)
    probs = res$posterior.prob
    
    probs[is.na(probs)] = 0
    data.frame(
      t = series$t,
      v = probs
    )
  }
}

test.cpprobs = function() {
  print(cpprobs(test.maketseries()))
}