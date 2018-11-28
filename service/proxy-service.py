import sys
import traceback
from flask import Flask, request, Response, abort, send_file
from functools import wraps
import json
import logging
import os
from io import StringIO, BytesIO
from ftplib import FTP
from ftplib import FTP_TLS
import ssl

app = Flask(__name__)

hostname_env = os.environ.get("HOSTNAME")
username_env = os.environ.get("USERNAME")
password_env = os.environ.get("PASSWORD")
protocol_env = os.environ.get("PROTOCOL")
if protocol_env:
    protocol_env = protocol_env.upper()

def log_exception():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    logger.error(
        traceback.format_exception(exc_type,
                                   exc_value,
                                   exc_traceback))

class MyFTP_TLS(FTP_TLS):
    """Explicit FTPS, with shared TLS session"""
    def ntransfercmd(self, cmd, rest=None):
        conn, size = FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            session = self.sock.session
            if isinstance(self.sock, ssl.SSLSocket):
                session = self.sock.session
            conn = self.context.wrap_socket(conn,
                                            server_hostname=self.host,
                                            session=session)  # this is the fix
        return conn, size


class FTPClient():
    """FTP Client"""
    def __init__(self, user, pwd, ftp_url):
        logger.debug("ftp connecting to {} with {}:{}".format(ftp_url, user, pwd))
        try:
            self.client = FTP(ftp_url)
            self.client.login(user, pwd)
        except Exception as e:
            raise e

    def test(self):
        return self.client.retrlines('LIST')

    def get_stream(self, fpath):
        """return a file stream"""
        r = BytesIO()
        logger.debug("fetching {}".format(fpath))
        self.client.retrbinary('RETR {}'.format(fpath), r.write)
        return r

    def write(self, path, stream, args):
         self.client.storlines('STOR {}'.format(path), BytesIO(stream))

    def get_content(self, fpath):
        """return file as string"""
        resp = self.get_stream(fpath)
        return resp.getvalue()

    def quit(self):
        self.client.quit()


class FTPSClient(FTPClient):
    """FTPS Client"""
    def __init__(self, user, pwd, ftp_url):
        logger.debug("ftps connecting to {} with {}:{}".format(ftp_url, user, pwd))
        try:
            self.client = MyFTP_TLS(ftp_url)
            self.client.login(user, pwd)
            self.client.prot_p()
            self.client.set_pasv(True)
        except Exception as e:
            raise e

def get_session(protocol, host, user, pwd):
    session = None
    if protocol == "FTP":
        session = FTPClient(user, pwd, host)
    elif protocol == "FTPS":
        session = FTPSClient(user, pwd, host)
    return session

def get_connection_spec(varname, auth):
    host = hostname_env
    protocol = protocol_env
    if auth:
        username = auth.username
        password = auth.password
    else:
        username = username_env
        password = password_env

    if varname:
        conn_url = None
        if varname.upper() in os.environ:
            conn_url = os.environ[varname.upper()]
        elif request.args.get(varname):
            conn_url = request.args.get(varname)
        if conn_url.startswith('ftp://'):
            protocol = "FTP"
            host = conn_url[6:]
        elif conn_url.startswith('ftps://'):
            protocol = "FTPS"
            host = conn_url[7:]
    logger.debug("Resolved url to host=%s, protocol= %s" % (host, protocol))
    return protocol, host, username, password

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth:
            return authenticate()
        return f(*args, **kwargs)

    return decorated

@app.route('/<path>/file', methods=['GET'])
@requires_auth
def get_file(path=None):
    fpath = request.args.get('fpath')
    if not fpath:
        return abort(400, "Missing the mandatory parameter.")
    protocol, host, username, password = get_connection_spec(path, request.authorization)
    if not host and not protocol:
        return abort(400, "Cannot find the endpoint url for {}".format(path))
    f_stream = None
    client = None
    try:
        if protocol == "FTP":
            client = FTPClient(username, password, host)
        elif protocol == "FTPS":
            client = FTPSClient(username, password, host)
        else:
            return abort(400, "Not supported protocal.")
        f_stream = client.get_stream(fpath)
        f_stream.seek(0)
        f_name = fpath.split('/')[-1]
        client.quit()
        return send_file(f_stream, attachment_filename=f_name, as_attachment=True)
    except Exception as e:
        log_exception()
        return abort(500, e)

@app.route('/<path:path>', methods=['GET'])
def get_file2(path=None):
    protocol, host, username, password = get_connection_spec(None, request.authorization)
    if not (protocol and host):
        return abort(500, "Missing protocol and/or host".format(protocol, host))
    if not (username and password):
        return abort(500, "Missing username and/or password")
    try:
        session = get_session(protocol, host, username, password)
        f_stream = session.get_stream(path)
        f_stream.seek(0)
        f_name = path.split('/')[-1]
        session.quit()
        return send_file(f_stream, attachment_filename=f_name, as_attachment=True)
    except Exception as e:
        log_exception()
        return abort(500, e)

@app.route('/<path:path>', methods=['POST'])
def post_file(path):
    accepted_mimetypes = ['text/csv', 'text/xml', 'application/xml', 'application/json']
    if request.mimetype not in accepted_mimetypes:
        return abort(400, "Mimetype not accepted")
    protocol, host, username, password = get_connection_spec(None, request.authorization)
    if not (protocol and host):
        return abort(500, "Missing protocol and/or host".format(protocol, host))
    if not (username and password):
        return abort(500, "Missing username and/or password")
    try:
        session = get_session(protocol, host, username, password)
        stream = request.stream
        f_stream = session.write(path, stream.read(), request.args)
        session.quit()
        return Response(response=json.dumps({"is_success":True, "message": "OK"}), content_type='application/json; charset=utf-8')
    except Exception as e:
        log_exception()
        return abort(500, e)

if __name__ == '__main__':
    # Set up logging
    format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logger = logging.getLogger('http-ftp-proxy-microservice')

    # Log to stdout
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(logging.Formatter(format_string))
    logger.addHandler(stdout_handler)

    loglevel = os.environ.get("LOGLEVEL", "INFO")
    if "INFO" == loglevel.upper():
        logger.setLevel(logging.INFO)
    elif "DEBUG" == loglevel.upper():
        logger.setLevel(logging.DEBUG)
    elif "WARN" == loglevel.upper():
        logger.setLevel(logging.WARN)
    elif "ERROR" == loglevel.upper():
        logger.setLevel(logging.ERROR)
    else:
        logger.setlevel(logging.INFO)
        logger.info("Define an unsupported loglevel. Using the default level: INFO.")

    logger.info("Running on %s://%s@%s" % (protocol_env, username_env, hostname_env))
    app.run(threaded=True, debug=True, host='0.0.0.0', port=int(os.environ.get('PORT',5001)))
