#!/bin/bash
s=`grep -A1 failures */*/*xml*log | grep "failures='0'" | wc -l`
f=`grep -A1 failures */*/*xml*log | grep "failures='1'" | wc -l`
echo $s fail=0=success
echo $f fail=1=FAIL

#sort part after reason:
grep "Final verdict" */*/*log | sort -k10 | while read -r line ; do
    if $(echo $line | cut -c 29- | sort | grep -q "fail rea") ; then
        #dirn=$(dirname echo $line | grep -o ".*log")
        echo $line
        #echo $(grep Unimplemented $dirn/\*)
    fi
done

