# sesam-ftp
[![Build Status](https://travis-ci.org/sesam-community/ftp.svg?branch=master)](https://travis-ci.org/sesam-community/ftp)

sesam Http->Ftp microservice

can be used to
 * download files from FTP via http requests
 * upload xml, csv, json files to FTP via http requests


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

The service listens on port 5001 unless specified otherwise in envvar 'HOST'.

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


##### Alternatively you can use the sevice as a generic service for any ftp server

An example of SESAM system config:

```json
{
  "_id": "sesam-datasource-ftp",
  "type": "system:microservice",
  "connect_timeout": 60,
  "docker": {
    "image": "sesamcommunity/ftp:latest",
    "memory": 64,
    "port": 5000
  },
  "read_timeout": 7200,
  "verify_ssl": false
}
```

#### Running locally in a virtual environment
```
  cd service
  virtualenv --python=python3 venv
  . venv/bin/activate
  pip install -r requirements.txt

  python proxy-service.py
   * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
   * Restarting with stat
   * ...

The service listens on port 5001 unless specified otherwise in envvar 'HOST'.

```
Then you can start using the service

```
curl -X GET http://localhost:5000/ftpurl/file?fpath=test.json&ftp_url=ftp://loaclhost -u myftpuser:myftppassword
curl -X GET http://localhost:5000/ftpurl/file?fpath=test.csv&ftp_url=ftp://loaclhost -u myftpuser:myftppassword
curl -X GET http://localhost:5000/ftpurl/file?fpath=test.xml&ftp_url=ftp://loaclhost -u myftpuser:myftppassword
```
