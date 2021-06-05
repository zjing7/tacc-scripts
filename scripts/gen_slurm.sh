#!/bin/bash

f1=$1 # template slurm batch script
fpre=$2 # prefix for output files
dlist=${@:3} # list of MD dirs
d1s=""
for d1 in $dlist ; do
  if [ ! -f $d1/md.log ] ; then
    d1s="$d1s $d1"
  fi
done

darr=($d1s)
nd=${#darr[@]}

for i in `seq 0 4 $(( $nd - 1 ))` ; do
  j=$(( $i + 4 ))
  d2s="${darr[@]:$i:4}"
  f2=${fpre}.${i}.sh
  sed -e "s#@id#$i#g" -e "s#@inputs#$d2s#g" $f1 > $f2
done

