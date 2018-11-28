#!/usr/bin/env bash

pushd data > /dev/null

hash_local_before=$(sha1sum $(ls -1 test*.json test*.csv test*.xml | sort ) | egrep "^.* " -o | sha1sum)

for file in `ls test*.json test*.csv test*.xml`
do
  curl -X POST http://localhost:5001$1/${file} --data-binary @${file} -H 'content-type:text/csv' -s -o /dev/null
done

for file in `ls test*.json test*.csv test*.xml`
do
  curl -X GET -s "http://localhost:5001$1/${file}" > fetched_${file}
done

hash_local_after=$(sha1sum $(ls -1 fetched_test*.json fetched_test*.csv fetched_test*.xml | sort ) | egrep "^.* " -o | sha1sum)

if [ "$hash_local_after" != "$hash_local_before" ]
then
 printf "tests failed"
else
 printf "tests passed"
fi
popd > /dev/null
