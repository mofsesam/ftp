from io import StringIO, BytesIO
from ftplib import FTP, FTP_TLS, error_perm
import logging
import ssl
import os
import paramiko
import stat

loglevel_env = os.environ.get("LOGLEVEL", "INFO")

logger = logging.getLogger("http-ftp-proxy-microservice")
paramikologger = logging.getLogger("paramiko")
paramikologger.setLevel(loglevel_env)
paramikologger.addHandler(logging.StreamHandler())
class MyFTP_TLS(FTP_TLS):
    """Explicit FTPS, with shared TLS session"""

    def ntransfercmd(self, cmd, rest=None):
        conn, size = FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            session = self.sock.session
            if isinstance(self.sock, ssl.SSLSocket):
                session = self.sock.session
            conn = self.context.wrap_socket(
                conn, server_hostname=self.host,
                session=session)  # this is the fix
        return conn, size


class FTPClient():
    """FTP Client"""

    def __init__(self, user, pwd, ftp_url):
        logger.debug("ftp connecting to {} with {}".format(ftp_url, user))
        try:
            self.client = FTP(ftp_url)
            self.client.login(user, pwd)
        except Exception as e:
            raise e

    def test(self):
        return self.client.retrlines("LIST")

    def get_stream(self, fpath):
        """return a file stream"""
        r = BytesIO()
        logger.debug("fetching {}".format(fpath))
        self.client.retrbinary("RETR {}".format(fpath), r.write)
        return r

    def put(self, fpath, stream):
        return self.client.storbinary("STOR {}".format(fpath), BytesIO(stream))

    def get_content(self, fpath):
        """return file as string"""
        resp = self.get_stream(fpath)
        return resp.getvalue()

    def rename(self, fromname, toname):
        return self.client.rename(fromname, toname)

    def get_type(self, fpath):
        """
        Dont rely on LIST output due to diversity of result formats.
        DIR, if "cd {path}"  command works
        FILE, if "ls {path}" command works
        None, otherwise
        """
        type = None
        pwd = self.client.pwd()
        try:
            cwd = self.client.cwd(fpath)
            type = "DIR"
        except error_perm as e:
            ls_lines = []
            self.client.retrlines("LIST {}".format(fpath), ls_lines.append)
            if len(ls_lines) == 1:
                type = "FILE"
        finally:
            self.client.cwd(pwd)
        return type

    def dir(self, fpath):
        listing_retrieved = []
        listing_2return = []
        self.client.retrlines("NLST {}".format(fpath),
                              listing_retrieved.append)
        for file in listing_retrieved:
            type = self.get_type(file)
            listing_2return.append({
                "filename": file,
                "type": self.get_type(file)
            })
            if type == "DIR":
                listing_2return += self.dir(file)
        return listing_2return

    def quit(self):
        self.client.quit()

    def set_debuglevel(self,level: int):
        self.client.set_debuglevel(level)


class FTPSClient(FTPClient):
    """FTPS Client"""

    def __init__(self, user, pwd, ftp_url):
        logger.debug("ftps connecting to {} with {}".format(ftp_url, user))
        try:
            self.client = MyFTP_TLS(ftp_url)
            self.client.login(user, pwd)
            self.client.prot_p()
            self.client.set_pasv(True)
        except Exception as e:
            raise e


class SFTPClient():
    """SFTP Client"""

    def __init__(self, user, pwd, ftp_url):
        logger.debug("sftp connecting to {} with {}".format(ftp_url, user))
        try:
            self.transport = paramiko.Transport((ftp_url, 22))
            self.transport.connect(username=user, password=pwd)
            self.client = paramiko.SFTPClient.from_transport(self.transport)
        except Exception as e:
            raise e

    def get_stream(self, fpath):
        """return file as string"""
        r = BytesIO()
        resp = self.client.getfo(fpath, r)
        return r

    def put(self, fpath, stream):
        resp = self.client.putfo(BytesIO(stream), fpath)
        return str(resp)

    def get_type(self, fpath):
        type = None
        file_stat = None
        try:
            file_stat = self.client.stat(fpath).st_mode
            if stat.S_ISDIR(file_stat):
                type = "DIR"
            else:
                type = "FILE"
        except Exception as e:
            if fpath == "":
                type = "DIR"
            else:
                type = None
        return type

    def dir(self, fpath):
        listing_2return = []
        listing_retrieved = []
        try:
            listing_retrieved = self.client.listdir(fpath)
        except IOError as e:
            None
        if fpath == ".":
            dir_path = ""
        else:
            dir_path = fpath + "/"
        for file in listing_retrieved:
            full_path = dir_path + file
            type = self.get_type(full_path)
            listing_2return.append({"filename": full_path, "type": type})
            if type == "DIR":
                listing_2return += self.dir(full_path)
        return listing_2return

    def rename(self, fromname, toname):
        self.client.rename(fromname, toname)

    def quit(self):
        self.client.close()
    
    def set_debuglevel(self,level: int):
        pass # Use sepperat logger and os env LOGLEVEL

