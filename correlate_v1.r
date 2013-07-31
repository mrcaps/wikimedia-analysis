library(plyr)
library(ggplot2)
library(RColorBrewer)
library(grid)
library(scales)
library(stringr)
library(rjson)

#generate assorted plots
etcplots = FALSE

setwd(dirname(sys.frame(1)$ofile))
theme_update(plot.margin = unit(c(0,0,0,0), "cm"))

source("common.r")

datafiles = getdatafiles(c("data/MySQL%20eqiad", "data/MySQL%20pmtpa"), "*.csv")

if (!exists("indata")) {
  indata = readdata(datafiles)
}

#convert ts to a day number
dateno = function(ts) {
  as.numeric(as.Date(ts))
}

if (!exists("changepoints")) {
  changepoints = ldply(indata, function(series) {
    findcps(series$data)
  }, .progress="text")
  changepoints$day = dateno(changepoints$t)
  min_cptsday = min(changepoints$day)
}

if (!exists("configchg")) {
  fcont = paste(readLines("C:/Docs/wikimedia/filtered-mysql.json"), collapse=" ")
  changejson = fromJSON(fcont)
   configchg = ldply(changejson, function(chg) {
     data.frame(
       t = as.POSIXlt(as.numeric(chg$time), origin="1970-01-01")
     )
   })
   configchg$day = dateno(configchg$t)
   min_configchgday = min(configchg$day)
}

configchangeno = Filter(function(c) {dateno(c$t) > min_cptsday},
  llply(changejson, function(chg) {
    list(
      numbers = llply(chg$diff$files, function(file) {
        #should we try to extract regexes? nah...
        #str_extract_all(file$text, "\\/.*\\/")
        #let's go for numbers instead
        str_extract_all(file$text, "\\d\\d+")
      })[[1]][[1]],
      files = chg$diff$files,
      t = as.POSIXlt(as.numeric(chg$time), origin="1970-01-01"),
      subject = chg$subject,
      hash = chg$hash
    )
  })
)

#for each config change, similarity to changepoints
mapped = laply(configchangeno, function(chg) {
  #gather all other changepoints...
  days = 10
  chg$pts = adply(subset(changepoints, (difftime(t, chg$t) > 0) & (difftime(t, chg$t) < days) ), 1,
        function(cpt) {
          #find text similarity
          similarity = aaply(chg$numbers, 1, function(n) {
            if (length(grep(n, cpt$fn))) {
              1
            } else {
              0
            }
          })
          cpt$sim = sum(similarity)
          cpt
        })
  chg$simsum = sum(chg$pts$sim)
  chg
}, .progress="text")
#sort the output
mapsorted = mapped[order(laply(mapped[, "simsum"], function(x) {x}), decreasing=TRUE), ]


#plot the first few
changemapdir = file.path("figs", "changemap")
unlink(changemapdir, recursive=TRUE)
dir.create(changemapdir, showWarnings=FALSE)
written = alply(head(mapsorted, n=20), 1, function(m) {
  subpath = file.path("figs", "changemap", as.character(m$simsum))
  dir.create(subpath, showWarnings=FALSE)
  
  sumstats = ddply(m$pts, .(datadir, fn), summarize, ss=sum(stat))$ss
  minstat = sort(sumstats, decreasing=TRUE)[10]
  
  plots_written = c()
  if (nrow(m$pts) > 0) {
    plots_written = daply(m$pts, .(datadir, fn), function(pts) {
      datadir_unique = unique(pts$datadir)
      fn_unique = unique(pts$fn)
      stopifnot(length(datadir_unique) == 1)
      stopifnot(length(fn_unique) == 1)
      dta = readsingle(file.path(datadir_unique, fn_unique))
      
      fnmod = ""
      
      if (sum(pts$stat) >= minstat) {
        ggplot(dta, aes(x=t, y=v)) + geom_line() +
          geom_vline(xintercept=as.numeric(m$t), color="red") +
          geom_vline(xintercept=as.numeric(pts$t), linetype=4) +
          geom_vline(xintercept=as.numeric(as.numeric(findcps(dta)$t)), 
                     linetype=4, size=0.3) +
          labs(title=paste(fn_unique)) +
          theme(plot.title=element_text(size=rel(0.7)))
        
        fnmod = paste(gsub("/", "-", fn_unique), "png", sep=".")
        fullfnmod = file.path(subpath, fnmod)
        ggsave(fullfnmod, width=4, height=3)
      }
      
      fullfnmod
    })
  }
  
  mmod = m
  mmod$plots = plots_written
  
  fc = file(file.path(subpath, "info.txt"))
  writeLines(c(
    mmod$hash,
    mmod$subject
  ), fc)
  close(fc)
  fc = file(file.path(subpath, "info.json"))
  writeLines(c(toJSON(mmod)), fc)
  close(fc)
  
  #return the subpath
  subpath
}, .progress="text")

#write out the index of changes
fc = file(file.path("figs", "index.json"))
writeLines(c(toJSON(written)), fc)
close(fc)


if (etcplots) {
  ggplot(data.frame(sim=similarities), aes(x=sim)) + geom_histogram()
}

if (etcplots) {
  #subset of configchg that are within perf data range
  configchg_ss = subset(configchg, day > min_cptsday)
  
  ggplot(subset(changepoints, stat<1e6), aes(x=stat)) + geom_histogram() +
    scale_x_continuous("Test statistic") + scale_y_continuous("Number of configchg")
  ggsave("figs/test-statistic-distribution.pdf", width=4, height=3)
  
  #subset of configchg that have a test statistic larger than X
  cpts_ss = subset(changepoints, stat > 1e6)
  
  #bin changes into day
  ggplot(configchg_ss, aes(x=day)) + 
    geom_histogram(mapping=aes(y=..density..), binwidth=1, fill="red") +
    geom_density() +
    geom_histogram(mapping=aes(y=..density.., x=day), data=cpts_ss, binwidth=1) +
    geom_density()
  ggsave("figs/correlate-change-times-day.pdf", width=6, height=5)
}

kernel = seq(4,0,-1)
