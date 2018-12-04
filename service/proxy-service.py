import sys
import traceback
from flask import Flask, request, Response, send_file
from functools import wraps
import json
import logging
import os
from ftplib import FTP, FTP_TLS, error_perm
from ftp_client import FTPClient, FTPSClient

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
        "You have to login with proper credentials",
        401,
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
        else:
            return abort(400, "Not supported protocal.")
        f_stream = client.get_stream(fpath)
        f_stream.seek(0)
        f_name = fpath.split("/")[-1]
        client.quit()
        return send_file(
            f_stream,
            attachment_filename=f_name,
            as_attachment=True)
    except Exception as e:
        log_exception()
        return abort(500, e)


def abort(response_code, message):
    return Response(
        response=json.dumps({
            "is_success": (response_code == 200),
            "message": message
        }),
        status=response_code,
        content_type="application/json; charset=utf-8")


def fix_path(path):
    slash = "/"
    if path[0:1] != slash:
        path = slash + path
    if path[-1] == slash:
        path = path[0:-1]
    return path


@app.route("/", methods=["GET"])
@app.route("/<path:path>", methods=["GET"])
def get_file2(path=""):
    protocol, host, username, password = get_connection_spec(
        None, request.authorization)
    move_to = request.args.get("move_to")
    ignore_move_to_errors = request.args.get("ignore_move_to_errors",
                                             "").lower() == "1"
    if not (protocol and host):
        return abort(500,
                     "Missing protocol and/or host".format(protocol,
                                                           host))
    if not (username and password):
        return abort(500, "Missing username and/or password")

    session = get_session(protocol, host, username, password)
    try:
        f_path = fix_path(path)
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
                    logger.info(
                        "renamed %s to %s with result %s" % (f_path,
                                                             move_to,
                                                             move_to_result))
                except Exception as e:
                    logger.error("failed to rename %s to %s" % (f_path,
                                                                move_to))
                    if not ignore_move_to_errors:
                        raise e
        else:
            return abort(404, "NOT FOUND")
        return send_file(
            f_stream,
            attachment_filename=f_name,
            as_attachment=True)
    except Exception as e:
        log_exception()
        return abort(500, str(e))
    finally:
        session.quit()


@app.route("/<path:path>", methods=["POST"])
def post_file(path):
    accepted_mimetypes = [
        "text/csv",
        "text/xml",
        "application/xml",
        "application/json"
    ]
    if request.mimetype not in accepted_mimetypes:
        return abort(400, "Mimetype not accepted")
    protocol, host, username, password = get_connection_spec(
        None, request.authorization)
    if not (protocol and host):
        return abort(200,
                     "Missing protocol and/or host".format(protocol,
                                                           host))
    if not (username and password):
        return abort(500, "Missing username and/or password")

    session = get_session(protocol, host, username, password)
    try:
        stream = request.data
        f_stream = session.put(path, stream)
        return abort(200, f_stream)
    except Exception as e:
        log_exception()
        return abort(500, str(e))
    finally:
        session.quit()


if __name__ == "__main__":
    # Set up logging
    format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logger = logging.getLogger("http-ftp-proxy-microservice")

    # Log to stdout
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(logging.Formatter(format_string))
    logger.addHandler(stdout_handler)

    loglevel = os.environ.get("LOGLEVEL", "INFO")
    logger.setLevel(loglevel)

    logger.info("Running on %s://%s@%s with loglevel=%s" % (protocol_env,
                                                            username_env,
                                                            hostname_env,
                                                            loglevel))
    app.run(
        threaded=True,
        debug=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT",
                                5000)))
