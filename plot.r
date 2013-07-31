#Create some basic summary plots for Wikimedia configuration changes
library(plyr)
library(ggplot2)
library(RColorBrewer)
library(grid)
library(scales)

setwd(dirname(sys.frame(1)$ofile))
theme_update(plot.margin = unit(c(0,0,0,0), "cm"))

times = read.csv("times.csv", header=FALSE)

times$date = as.Date(as.POSIXlt(times$V1, origin="1970-01-01"), tz="America/New_York")
ggplot(times, aes(x=date)) + geom_histogram(binwidth=1) + 
  scale_x_date(labels=date_format("%m/%d/%y"), breaks="2 weeks") +
  theme(axis.text.x=element_text(angle=45, hjust=1)) +
  scale_y_continuous("Number of Configuration Changes")
ggsave("figs/config-changes-bydate.pdf", width=15, height=6)

times$days = weekdays(times$date, abbreviate=TRUE)
times$days = factor(times$days, levels=c("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
ggplot(times, aes(x=days)) + geom_histogram(binwidth=1) +
  scale_y_continuous("Number of configuration changes")
ggsave("figs/config-changes-byweekday.pdf", width=4, height=4)

files = read.csv("files.csv", header=FALSE)
files$fno=as.numeric(files$V1)
fhist=hist(files$fno, breaks=nrow(files), plot=FALSE)
counts=data.frame(
  x=seq(1, length(fhist$counts), 1),
  y=sort(fhist$counts, decreasing=TRUE)
)
ggplot(counts, aes(x, y)) + geom_line() + 
  scale_y_log10("Number of Changes") + scale_x_continuous("Configuration File Number")
ggsave("figs/config-changes-byfile.pdf", width=4, height=3)
ggplot(counts, aes(x, y)) + geom_line() + 
  scale_y_log10("Number of Changes") + scale_x_log10("Configuration File Number")
ggsave("figs/config-changes-byfile-logx.pdf", width=4, height=3)

ftable = sort(table(as.character(files$V1)), decreasing=TRUE)
