from flask import Flask, request, Response, abort, send_file
from functools import wraps
import json
import logger as log
import os
from ftplib import FTP, FTP_TLS, error_perm
from ftp_client import FTPClient, FTPSClient, SFTPClient

app = Flask(__name__)

hostname_env = os.environ.get("HOSTNAME")
username_env = os.environ.get("USERNAME")
password_env = os.environ.get("PASSWORD")
protocol_env = os.environ.get("PROTOCOL")
loglevel_env = os.environ.get("LOGLEVEL", "INFO")

if protocol_env:
    protocol_env = protocol_env.upper()

# Set up logging
logger = log.init_logger("http-ftp-proxy-microservice", loglevel_env)
logger.info("Running on %s://%s@%s with loglevel=%s" %
            (protocol_env, username_env, hostname_env, log.get_level_name(logger.level)))


def get_session(protocol, host, user, pwd):
    session = None
    if protocol == "FTP":
        session = FTPClient(user, pwd, host)
    elif protocol == "FTPS":
        session = FTPSClient(user, pwd, host)
    elif protocol == "SFTP":
        session = SFTPClient(user, pwd, host)
    if loglevel_env == "DBUG": 
        session.set_debuglevel(2)
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
        if conn_url.startswith("ftp://"):
            protocol = "FTP"
            host = conn_url[6:]
        elif conn_url.startswith("ftps://"):
            protocol = "FTPS"
            host = conn_url[7:]
    return protocol, host, username, password


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        "Could not verify your access level for that URL.\n"
        "You have to login with proper credentials", 401,
        {"WWW-Authenticate": "Basic realm=\"Login Required\""})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth:
            return authenticate()
        return f(*args, **kwargs)

    return decorated


@app.route("/<path>/file", methods=["GET"])
@requires_auth
def get_file(path=None):
    """
    this route and method is kept for backward compatibility.
    """
    fpath = request.args.get("fpath")
    if not fpath:
        return abort(400, "Missing the mandatory parameter.")
    protocol, host, username, password = get_connection_spec(
        path, request.authorization)
    if not host and not protocol:
        return abort(400, "Cannot find the endpoint url for {}".format(path))
    f_stream = None
    client = None
    try:
        if protocol == "FTP":
            client = FTPClient(username, password, host)
        elif protocol == "FTPS":
            client = FTPSClient(username, password, host)
        elif protocol == "SFTP":
            client = SFTPClient(username, password, host)
        else:
            return abort(400, "Not supported protocal.")
        f_stream = client.get_stream(fpath)
        f_stream.seek(0)
        f_name = fpath.split("/")[-1]
        client.quit()
        return send_file(f_stream, attachment_filename=f_name, as_attachment=True)
    except Exception as e:
        logger.exception(e)
        return abort(500, e)


def abort(response_code, message):
    return Response(
        response=json.dumps({
            "is_success": (response_code == 200),
            "message": message
        }),
        status=response_code,
        content_type="application/json; charset=utf-8")


def fix_path(path, protocol):
    slash = "/"
    if path[0:1] != slash:
        path = slash + path
    if path[-1] == slash:
        path = path[0:-1]
    if path == "" and protocol == "SFTP":
        path = "."
    return path


@app.route("/", methods=["GET"])
@app.route("/<path:path>", methods=["GET"])
def get_file2(path=""):
    protocol, host, username, password = get_connection_spec(
        None, request.authorization)
    move_to = request.args.get("move_to")
    ignore_move_to_errors = request.args.get("ignore_move_to_errors",
                                             "").lower() == "1"
    ignore_404_errors = request.args.get("ignore_404_errors", "").lower() == "1"
    if not (protocol and host):
        return abort(500, "Missing protocol and/or host".format(
            protocol, host))
    if not (username and password):
        return abort(500, "Missing username and/or password")

    session = None
    try:
        session = get_session(protocol, host, username, password)
        f_path = fix_path(path, protocol)
        f_type = session.get_type(f_path)
        if f_type == "DIR":
            return Response(
                response=json.dumps(session.dir(f_path)),
                content_type="application/json; charset=utf-8")
        elif f_type == "FILE":
            f_stream = session.get_stream(f_path)
            f_stream.seek(0)
            f_name = f_path.split("/")[-1]
            if move_to:
                move_to_result = None
                try:
                    move_to_result = session.rename(f_path, move_to)
                    logger.info("renamed %s to %s with result %s" %
                                (f_path, move_to, move_to_result))
                except Exception as e:
                    logger.error(
                        "failed to rename %s to %s" % (f_path, move_to))
                    if not ignore_move_to_errors:
                        raise e
        else:
            if ignore_404_errors:
                return Response(
                    response=json.dumps([]),
                    status=200,
                    content_type="application/json; charset=utf-8")
            else:
                return abort(404, "NOT FOUND")
        return send_file(
            f_stream, attachment_filename=f_name, as_attachment=True)
    except Exception as e:
        logger.exception(e)
        return abort(500, str(e))
    finally:
        if session:
            session.quit()


@app.route("/<path:path>", methods=["POST"])
def post_file(path):
    accepted_mimetypes = [
        "text/csv", "text/xml", "application/xml", "application/json"
    ]
    if request.mimetype not in accepted_mimetypes:
        return abort(400, "Mimetype not accepted")
    protocol, host, username, password = get_connection_spec(
        None, request.authorization)
    if not (protocol and host):
        return abort(200, "Missing protocol and/or host".format(
            protocol, host))
    if not (username and password):
        return abort(500, "Missing username and/or password")

    session = None
    try:
        session = get_session(protocol, host, username, password)
        stream = request.data
        f_stream = session.put(path, stream)
        return abort(200, f_stream)
    except Exception as e:
        logger.exception(e)
        return abort(500, str(e))
    finally:
        if session:
            session.quit()


if __name__ == "__main__":

    if os.environ.get("WEBFRAMEWORK", "").lower() == "flask":
        app.run(
            threaded=True,
            debug=True,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 5000)))
    else:
        import cherrypy

        app = log.add_access_logger(app, logger)
        cherrypy.tree.graft(app, '/')

        # Set the configuration of the web server to production mode
        cherrypy.config.update({
            'environment': 'production',
            'engine.autoreload_on': False,
            'log.screen': True,
            'server.socket_port': int(os.environ.get("PORT", 5000)),
            'server.socket_host': '0.0.0.0'
        })

        # Start the CherryPy WSGI web server
        cherrypy.engine.start()
        cherrypy.engine.block()
