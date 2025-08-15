# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
import os
from contextlib import contextmanager
from ftplib import all_errors as all_ftp_errors
from io import BytesIO, IOBase
from typing import Callable, List

from paramiko.client import SSHClient
from paramiko.sftp_client import SFTPClient
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    NoValidConnectionsError,
    SSHException,
)


class ClientException(Exception):
    pass


# To tunnel to the real ftp server:
# ssh -L 172.17.0.1:2222:sftp.erp.gl:22 [your_username]@10.240.76.76


@contextmanager
def exception_handler():
    """Convert all SFTP-related exceptions to `ClientException` errors"""
    try:
        yield
    except all_ftp_errors as e:
        # Handle `ftplib` exceptions
        raise ClientException(str(e)) from e
    except SSHException as e:
        # Handle `paramiko.ssh_exception` exceptions
        raise ClientException(str(e)) from e
    except (  # handle similar exceptions from Paramiko
        NoValidConnectionsError,
        AuthenticationException,
        BadHostKeyException,
    ) as e:
        raise ClientException(str(e)) from e


@contextmanager
def _get_connection(settings: dict) -> SFTPClient:
    ssh_client = SSHClient()
    ssh_client.load_system_host_keys()

    """
    The old function here is not well understood by the author, and does not seem to
    be in use in any production nor test systems, and has thus been replaced by a
    placeholder statement:

    cnopts = pysftp.CnOpts(settings["known_hosts"])
    if settings["known_hosts"] is None:
        cnopts.hostkeys = None
    """
    if settings["known_hosts"] is None:
        hostkeys = ssh_client.get_host_keys()
        hostkeys.clear()

    ssh_client.connect(
        settings["host"],
        username=settings["username"],
        password=settings["password"],
        port=settings.get("port", 22),
    )
    sftp_client = ssh_client.open_sftp()
    try:
        yield sftp_client
    finally:
        sftp_client.close()
        ssh_client.close()


def put_file_in_prisme_folder(
    settings,
    source_file_name_or_object,
    destination_folder: str,
    destination_filename: str = None,
    callback: Callable[[int, int], None] = None,
):
    if isinstance(source_file_name_or_object, IOBase) and destination_filename is None:
        raise Exception("Must provide a filename when writing file-like object")

    remote_path = (
        f"{destination_folder}/{destination_filename}"
        if destination_filename is not None
        else None
    )

    with exception_handler():
        with _get_connection(settings) as client:
            if isinstance(source_file_name_or_object, str):
                client.put(
                    source_file_name_or_object,
                    remotepath=remote_path,
                    callback=callback,
                )
            elif isinstance(source_file_name_or_object, IOBase):
                client.putfo(
                    source_file_name_or_object,
                    remotepath=remote_path,
                    callback=callback,
                )
            else:
                raise TypeError(
                    f"file_path_or_object (type={type(source_file_name_or_object)}) not recognized"
                )


def list_prisme_folder(settings, folder_name: str) -> List[str]:
    with exception_handler():
        with _get_connection(settings) as client:
            return client.listdir(folder_name)


def get_file_in_prisme_folder(settings, folder_name: str, filename: str):
    with exception_handler():
        with _get_connection(settings) as client:
            buf = BytesIO()
            client.getfo(os.path.join(folder_name, filename), buf)
            buf.seek(0)
            return buf
