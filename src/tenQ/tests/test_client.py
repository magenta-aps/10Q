# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
import io
from ftplib import all_errors as all_ftp_errors
from typing import Callable
from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch, Mock

from paramiko.message import Message
from paramiko.pkey import PKey
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    NoValidConnectionsError,
    SSHException,
)

from paramiko.client import SSHClient
from paramiko.rsakey import RSAKey

from tenQ.client import (
    ClientException,
    _get_connection,
    get_file_in_prisme_folder,
    list_prisme_folder,
    put_file_in_prisme_folder,
)

_port = 22

class SSHClientMock(MagicMock):
    def __init__(self, **kwargs):
        super().__init__(spec=SSHClient, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self):
        pass
    
    def connect(self, hostname, username=None, password=None,port=None):
        if hostname and username and password and port:
            return None
        else:
            raise SSHException()

class TestGetConnection(TestCase):
    def test_returns_paramiko_connection(self):
        for known_hosts in (
            [],
            [{
                "hostname": "a_hostname",
                "keytype": "ssh-rsa",
                "key": RSAKey.generate(1024),
            }]
            ):
            with self.subTest(known_hosts=known_hosts):
                # Arrange
                # Act
                # TODO: Mock away the SSHClient and SFTPClient....
                # If Mock/MagicMock ever fucking worked...
                with _get_connection(
                    self._get_mock_settings(known_hosts=known_hosts)
                ) as client:
                    print(dir(client))

    def _get_mock_settings(self, **kwargs) -> dict:
        settings = dict(
            host="host",
            username="username",
            password="password",
            port=_port,
            known_hosts=[],
        )
        settings.update(**kwargs)
        return settings


class ClientTestCase(TestCase):
    mock_settings = None

    def assert_exceptions_are_converted(self, callable: Callable) -> None:
        def raise_connection_exception(*args):
            raise NoValidConnectionsError({"host": _port})

        def raise_credential_exception(*args):
            raise AuthenticationException("message")

        known = (
            # `ftplib` exceptions
            list(all_ftp_errors)
            # `paramiko.ssh_exception` exceptions (base class)
            + [SSHException]
            # `paramiko` exceptions for connection
            + [
                raise_connection_exception,
                raise_credential_exception,
                BadHostKeyException(hostname="a_hostname", got_key=RSAKey.generate(1024), expected_key=RSAKey.generate(1024)),
            ]
        )
        for exception in known:
            with self.subTest(exception=exception):
                with patch("tenQ.client._get_connection", side_effect=exception):
                    with self.assertRaises(ClientException):
                        callable()

    def mocked_client(self, mocked_connection) -> patch:
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mocked_connection
        return patch("tenQ.client._get_connection", return_value=mock_context)


class TestPutFileInPrismeFolder(ClientTestCase):
    def test_handles_known_exceptions(self):
        self.assert_exceptions_are_converted(
            lambda: put_file_in_prisme_folder(self.mock_settings, None, "")
        )

    def test_filename_is_provided_for_file_like_object(self):
        file_like_object = io.BytesIO()
        with self.assertRaises(Exception):
            put_file_in_prisme_folder(
                self.mock_settings,
                file_like_object,
                "folder",
                destination_filename=None,
            )

    def test_source_file_name_or_object_is_type_checked(self):
        with self.mocked_client(MagicMock()):
            with self.assertRaises(TypeError):
                put_file_in_prisme_folder(
                    self.mock_settings,
                    None,
                    "folder",
                )

    def test_upload_using_filename(self):
        client = MagicMock()
        with self.mocked_client(client):
            put_file_in_prisme_folder(self.mock_settings, "filename", "folder")
            client.put.assert_called_once_with(
                "filename", remotepath=ANY, callback=None
            )

    def test_upload_using_file_like_object(self):
        client = MagicMock()
        file_like_object = io.BytesIO()
        with self.mocked_client(client):
            put_file_in_prisme_folder(
                self.mock_settings,
                file_like_object,
                "folder",
                destination_filename="filename",
            )
            client.putfo.assert_called_once_with(
                file_like_object, remotepath=ANY, callback=None
            )


class TestListPrismeFolder(ClientTestCase):
    def test_handles_known_exceptions(self):
        self.assert_exceptions_are_converted(
            lambda: list_prisme_folder(self.mock_settings, "folder")
        )

    def test_lists_folder(self):
        client = MagicMock()
        with self.mocked_client(client):
            list_prisme_folder(self.mock_settings, "folder")
            client.listdir.assert_called_once_with("folder")


class TestGetFileInPrismeFolder(ClientTestCase):
    def test_handles_known_exceptions(self):
        self.assert_exceptions_are_converted(
            lambda: get_file_in_prisme_folder(self.mock_settings, "folder", "filename")
        )

    def test_gets_file(self):
        client = MagicMock()
        buf = MagicMock()
        with self.mocked_client(client):
            with patch("tenQ.client.BytesIO", return_value=buf):
                result = get_file_in_prisme_folder(
                    self.mock_settings, "folder", "filename"
                )
                client.getfo.assert_called_once_with("folder/filename", buf)
                buf.seek.assert_called_once_with(0)
                self.assertEqual(result, buf)
