library(plyr)
library(ggplot2)
library(reshape2)
library(RColorBrewer)
library(grid)
library(scales)
library(stringr)
library(rjson)

library(foreach)
library(doParallel)
workers = makeCluster(detectCores(), "PSOCK", useXDR=FALSE)
registerDoParallel(workers)

setwd(dirname(sys.frame(1)$ofile))
theme_update(plot.margin = unit(c(0,0,0,0), "cm"))

source("common.r")

datafiles = getdatafiles(c("timeseries/MySQL%20eqiad", "timeseries/MySQL%20pmtpa"), "*.csv")

#convert ts to a day number
dateno = function(ts) {
  as.numeric(as.Date(ts))
}

if (!exists("indata")) {
  cat("Reading input time series...\n")
  indata = readdata(datafiles)
  
  cat("Computing changepoint test statistics...\n")
  indata = llply(indata, function(l) {
    l$cps = cpprobs(l$data)
    l
  }, .progress="text", .parallel=TRUE, .paropts=list(
    .export=c("cpprobs"),
    .packages=c("bcp")
  ))
  
  indata_minday = laply(head(indata, 1e6), function(l) {
    min(dateno(l$data$t))
  }, .progress="text")
  indata_maxday = laply(head(indata, 1e6), function(l) {
    max(dateno(l$data$t))
  }, .progress="text")
}

if (!exists("configdiffs")) {
  #diff collection server
  collect_server = file.path("/", "172.19.149.233", "share", "wikimedia")
  
  configdiffs = read.csv(file.path(collect_server, "diff-collected.csv"), stringsAsFactors = FALSE)
  configdiffs$t = as.POSIXct(as.POSIXlt(as.numeric(configdiffs$timestamp), origin="1970-01-01"))
  configdiffs$day = dateno(configdiffs$t)
  
  #only look at config diffs within the perf data range
  configdiffs = subset(configdiffs, (day > min(indata_minday)) & (day < max(indata_maxday)))
  
  fcont = paste(readLines(file.path(collect_server, "diff-collected.json")), collapse=" ")
  configdiffmap = fromJSON(fcont)
}

#the source changes
if (!exists("changesource")) {
  fcont = paste(readLines("all-changes.json"), collapse=" ")
  changesource = fromJSON(fcont)
  names(changesource) = laply(changesource, function(c) {c$hash})
}

#Get a sense of where unique commits are
if (FALSE) {
  ddply(configdiffs, .(commithash), function(diffs) {
    cat(length(unique(diffs$diffhash)))
    diffs
  })
  
  ddply(configdiffs, .(commithash), function(diffs) {
    cat("commithash", unique(diffs$commithash), "\n")
    cat("changed-nodes", length(diffs$diffhash), "\n")
    cat("unique-diffs", length(unique(diffs$diffhash)), "\n")
    a = aaply(unique(diffs$diffhash), 1, function(h) {
      length(which(diffs$diffhash == h))
    })
    cat("uniques", a, "\n")
    cat("\n")
    0
  })
}

#plot sample of changepoint probabilities and time series
if (FALSE) {
  tdata = indata[[8000]]
  ggplot(melt(data.frame(
    t=tdata$data$t, 
    timeseries=tdata$data$v, 
    changepoint_probability=tdata$cps$v), id=c("t")), aes(x=t, y=value)) +
    geom_line() +
    facet_wrap(~ variable, ncol=1, scale="free_y") +
    ggtitle(paste(tdata$metric, "on", tdata$node))
}

nodes = unique(configdiffs$node)
ndiffs = 0
if (!exists("correlations")) {
  cat("compute correlation")
  correlations = ddply(configdiffs, .(commithash), function(diffs) {
    #use Pearson's product moment correlation coefficient r (cor.test)
    # previous thought: use something like Jaccard similarity
    
    commit_hash = unique(diffs$commithash)
    commit_day = unique(diffs$day)
    commit_t = unique(diffs$t)
    stopifnot(length(commit_day) == 1)
    stopifnot(length(commit_t) == 1)
    
    #get test statistic across all metrics at this commit
    stats = ldply(indata, function(l) {
      data.frame(
        commithash=commit_hash,
        commitday=commit_day,
        committime=commit_t,
        node=l$node,
        metric=l$metric,
        stat=sum(l$cps$v[abs(dateno(l$cps$t) - commit_day) < 2]),
        ischanged=(l$node %in% diffs$node)
      )
    }, .progress="text")
    
    result = cor.test(stats$stat, as.numeric(stats$ischanged), method="pearson")
    
    stats$statistic = result$statistic
    stats$p.value = result$p.value
    stats$estimate = result$estimate
    
    stats
  }, .parallel=TRUE, .paropts=list(
    .export=c("dateno", "ddply", "ldply", "indata"),
    .packages=c("plyr")
  ))

  #use estimate for sorting: this is the actual correlation
  topcors = arrange(
    ddply(correlations, .(commithash), function(corrs) {
      data.frame(
        commithash=unique(corrs$commithash),
        estimate=unique(corrs$estimate)
      )
    }), -estimate)
  
  n_top_correlations = 10
  correlations_top = subset(correlations, 
                            commithash %in% head(topcors, n_top_correlations)$commithash)
}

sample = arrange(
  subset(correlations, commithash=="fcd0a3a5ffd7a9f9ae91d70cc083f350e6216d3b"),
  -stat)[, c("node", "metric", "stat")]


outdir = file.path("figs", "changemap")

allFiles = dlply(correlations_top, .(commithash), function(corrs) {
  commit_hash = as.character(unique(corrs$commithash))
  strength = floor(unique(corrs$estimate)*10000)
  stopifnot(length(strength) == 1)
  
  changepath = file.path(outdir, paste(strength, commit_hash, sep="-"))
  dir.create(changepath, showWarnings=FALSE, recursive=TRUE)
  
  comsrc = changesource[[commit_hash]]
  cat("Writing plots for", comsrc$hash, "strength=", strength, "\n")
  stopifnot(comsrc$hash == commit_hash)
  
  #write the top n metrics
  n_plot_metrics = 10
  corrs_toplot = head(
    arrange(subset(corrs, ischanged==TRUE), -stat),
    n_plot_metrics)
  
  plots_written = adply(corrs_toplot, 1, function(metric) {
    datadir_unique = unique(metric$datadir)
    fn_unique = unique(metric$fn)
    stopifnot(length(datadir_unique) == 1)
    stopifnot(length(fn_unique) == 1)
    dta = readsingle(file.path(datadir_unique, fn_unique))
    
    fnmod = ""
  
    ggplot(dta, aes(x=t, y=v)) + geom_line() +
      geom_vline(xintercept=as.numeric(corrs$committime), color="red") +
      labs(title=paste(fn_unique, "\n", "change statistic: ", metric$stat, sep="")) +
      theme(plot.title=element_text(size=rel(0.7), hjust=0))
    
    fnmod = paste(gsub("/", "-", fn_unique), "png", sep=".")
    fullfnmod = file.path(changepath, fnmod)
    ggsave(fullfnmod, width=4, height=3)
    
    #also plot the probability data
    ggplot(cpprobs(dta), aes(x=t, y=v)) + geom_line() +
      geom_vline(xintercept=as.numeric(corrs$committime), color="red")
    ggsave(paste(fullfnmod, "prob", "png", sep="."), width=4, height=1)
    
    metric$filepath = fullfnmod
    metric
  }, .progress="text")
  
  #find related diff hashes
  iarr = unique(subset(configdiffs, commithash==commit_hash)$diffhash)
  compiled_diffs = alply(iarr, 1, function(diffhash) {
    configdiffmap[[diffhash]]
  }, .dims=TRUE)
  names(compiled_diffs) = iarr
  
  #nodes for the given diff hashes
  iarr = unique(subset(configdiffs, commithash==commit_hash)$diffhash)
  compiled_diff_nodes = alply(iarr, 1, function(dh) {
    subset(configdiffs, diffhash==dh & commithash==commit_hash)$node
  }, .dims=TRUE)
  names(compiled_diff_nodes) = iarr
  
  mmod = list(
    files = comsrc$diff$files,
    subject = comsrc$subject,
    plots = plots_written$filepath,
    hash = commit_hash,
    compiled = compiled_diffs,
    compiled_nodes = compiled_diff_nodes
  )
  
  fc = file(file.path(changepath, "info.json"))
  writeLines(c(toJSON(mmod)), fc)
  close(fc)
  
  changepath
})

#write out the index
fc = file(file.path("figs", "index.json"))
writeLines(c(toJSON(allFiles)), fc)
close(fc)

stopCluster(workers)