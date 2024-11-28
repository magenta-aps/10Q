# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
import os
from contextlib import contextmanager
from ftplib import all_errors as all_ftp_errors
from io import BytesIO, IOBase
from typing import Callable, List

import pysftp
from paramiko.ssh_exception import SSHException


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
    except (
        pysftp.ConnectionException,
        pysftp.CredentialException,
        pysftp.HostKeysException,
    ) as e:
        # Handle other exceptions possibly raised by `pysftp.Connection.__init__`
        raise ClientException(str(e)) from e


def _get_connection(settings: dict) -> pysftp.Connection:
    cnopts = pysftp.CnOpts(settings["known_hosts"])
    if settings["known_hosts"] is None:
        cnopts.hostkeys = None

    return pysftp.Connection(
        settings["host"],
        username=settings["username"],
        password=settings["password"],
        port=settings.get("port", 22),
        cnopts=cnopts,
    )


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
