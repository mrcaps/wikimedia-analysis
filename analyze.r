library(plyr)
library(ggplot2)
library(RColorBrewer)
library(grid)
library(scales)
library(changepoint)

setwd(dirname(sys.frame(1)$ofile))
theme_update(plot.margin = unit(c(0,0,0,0), "cm"))

source("common.r")

datafiles = getdatafiles(c("data"), "*.csv")

if (!exists("indata")) {
  indata = readdata(datafiles)
  badposes = laply(indata, function(x) {nrow(x)})
  badfiles = datafiles$fn[badposes == 0]
  
  #check that everything has the same start time - it doesn't.
  #starts = laply(indata, function(x) { as.numeric(x$t[1]) })
}

for (idxtest in c(seq(2,50000,1000))) {
  toplot = indata[[idxtest]]
  if (FALSE) {
    #investigate the selected data a bit
    ggplot(toplot, aes(x=t, y=v)) + geom_line()
    bydx = data.frame(
      x=seq(1,nrow(toplot),1),
      y=toplot$v
    )
    ggplot(bydx, aes(x, y)) + geom_line()
  }
  
  cpts = findcps(toplot)
  
  ggplot(toplot, aes(x=t, y=v)) + geom_line() + 
    geom_vline(xintercept=as.numeric(cpts$t), linetype=4)
  ggsave(paste("figs/", idxtest, 
             gsub("%20", " ", gsub("/", "-", datafiles$fn[idxtest], fixed=TRUE)), 
             "png", sep="."), width=5, height=4)
}