#!/usr/bin/env bash

dirpath=${1/#\+//\/}
dirpath=${dirpath/%\//}
PORT=5000
pushd data > /dev/null


hash_local_before=$(sha1sum $(ls -1 test*.json test*.csv test*.xml | sort ) | egrep "^.* " -o | sha1sum)

printf "uploading files to $dirpath"
for file in `ls test*.json test*.csv test*.xml`
do
  curl -X POST "http://localhost:${PORT}$dirpath/${file}" --data-binary @${file} -H 'content-type:text/csv' -s -o /dev/null
  printf "..."
done
printf "DONE."

printf "\ndirectory listing after upload:"
curl -X GET -s "http://localhost:$PORT$dirpath/" | jq '.'

printf "downloading files from $dirpath"
for file in `ls test*.json test*.csv test*.xml`
do
  curl -X GET -s "http://localhost:$PORT$dirpath/${file}?move_to=$dirpath/renamed_${file}&ignore_move_to_errors=0" > fetched_${file}
  printf "..."
done
printf "DONE."

printf "\n directory listing after download:\n"
curl -X GET -s "http://localhost:$PORT$dirpath/"  | jq '.'

hash_local_after=$(sha1sum $(ls -1 fetched_test*.json fetched_test*.csv fetched_test*.xml | sort ) | egrep "^.* " -o | sha1sum)

printf "\n\n(files uploaded in the test are not deleted)\n"
if [ "$hash_local_after" != "$hash_local_before" ]
then
 printf "tests FAILED\n"
else
 printf "tests PASSED\n"
fi

popd > /dev/null
