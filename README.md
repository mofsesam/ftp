# sesam-ftp
[![Build Status](https://travis-ci.org/sesam-community/ftp.svg?branch=master)](https://travis-ci.org/sesam-community/ftp)

sesam Http->Ftp microservice

can be used to
 * download files from FTP via http requests
 * upload xml, csv, json files to FTP via http requests

### Notes
 * access logs are enabled when loglevel is set to at least 'INFO'


### Query Parameters
| CONFIG_NAME        | DESCRIPTION           | IS_REQUIRED  |DEFAULT_VALUE|
| -------------------|:---------------------:|:------------:|:-----------:|
| move_to | path with filename to which the downloaded file will be moved to. | no | n/a |
| ignore_move_to_errors | set to '1' to ignore errors in 'move to' operation, any other value otherwise  | no | n/a |
| ignore_404_errors | set to '1' so that 404 errors will be retured as 204 so that the pipe does not receive failure | no | n/a |


#### Running locally in a virtual environment
```
  cd service
  printf "PROTOCOL=FTP\nHOSTNAME=myftpserver\nUSERNAME=myftpuser\nPASSWORD=myftppassword\n" > envlist
  set -a
  . envlist

  virtualenv --python=python3 venv
  . venv/bin/activate
  pip install -r requirements.txt

  python proxy-service.py
   * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
   * Restarting with stat
   * ...

The service listens on port 5000 unless specified otherwise in envvar 'HOST'.

```
Then you can start using the service

```
curl -X POST http://localhost:5000/test.json -d @test.json -H 'content-type:application/json'
curl -X POST http://localhost:5000/test.csv --data-binary @test.csv -H 'content-type:text/csv'
curl -X POST http://localhost:5000/test.xml -d @test.xml -H 'content-type:application/xml'

curl -X GET http://localhost:5000/test.json
curl -X GET http://localhost:5000/test.csv
curl -X GET http://localhost:5000/test.xml
```

#### How To use in SESAM

An example of SESAM system config:

```json
{
  "_id": "my-ftp-server",
  "type": "system:microservice",
  "connect_timeout": 60,
  "docker": {
    "environment": {
      "PROTOCOL": "FTP",
      "HOSTNAME": "myftphost",
      "USERNAME": "myftpuser",
      "PASSWORD": "myftppassword",
    },
    "image": "sesamcommunity/ftp:latest",
    "memory": 64,
    "port": 5000
  },
  "read_timeout": 7200,
  "verify_ssl": false
}
```


##### Alternatively you can use the service as a generic service for any ftp server

(DEPRECATED)


An example of system config:

```json
{
  "_id": "sesam-datasource-ftp",
  "type": "system:microservice",
  "connect_timeout": 60,
  "docker": {
    "environment": {
      "sys_id": "ftp://ftp_server_url"
    },
    "image": "sesamcommunity/ftp:latest",
    "memory": 64,
    "port": 5000
  },
  "read_timeout": 7200,
  "verify_ssl": false
}
```

This microservice should receive some http request,
such as "http://sesam-datasource-ftp:5000/{sys_id}/file?fpath={fpath}".

{sys_id} should be an environment variable that contains the ftp server url.
If you dont want to define {sys_id} in the environment variables.
You also can use this url pattern "http://sesam-datasource-ftp:5000/{sys_id}/file?fpath={fpath}&sys_id=ftp://ftp_server_url".
