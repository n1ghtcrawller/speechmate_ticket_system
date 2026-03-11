import logging
import paramiko
from io import BytesIO
import os


class SFTPClient:
    def __init__(self, host, port, username, password, directory):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.directory = directory
        self.transport = None
        self.sftp = None

    def connect(self):
        logging.info("Подключаюсь к SFTP...")
        self.transport = paramiko.Transport((self.host, self.port))
        self.transport.connect(username=self.username, password=self.password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        self.sftp.chdir(self.directory)
        logging.info("Удалось подключиться кSFTP.")

    def disconnect(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()
        logging.info("Отключился от SFTP.")

    def list_files(self):
        if not self.sftp:
            raise ConnectionError("SFTP client is not connected.")
        return self.sftp.listdir_attr()

    def download_latest_archive(self):
        if not self.sftp:
            raise ConnectionError("SFTP client is not connected.")

        files = self.list_files()
        archives = [f for f in files if f.filename.endswith(('.zip', '.tar.gz'))]

        if not archives:
            logging.warning("Не нашел архивов.")
            return None, None

        latest_archive = max(archives, key=lambda f: f.st_mtime)
        remote_file_path = latest_archive.filename
        logging.info(f"Скачал последний архив: {remote_file_path}")

        file_obj = BytesIO()
        self.sftp.getfo(remote_file_path, file_obj)
        file_obj.seek(0)

        logging.info(f"Downloaded {remote_file_path} successfully.")
        return remote_file_path, file_obj