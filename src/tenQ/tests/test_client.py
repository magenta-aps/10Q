# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
import io
from ftplib import all_errors as all_ftp_errors
from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch

from paramiko.ssh_exception import SSHException
from pysftp.exceptions import (
    ConnectionException,
    CredentialException,
    HostKeysException,
)

from tenQ.client import ClientException, _get_connection, put_file_in_prisme_folder

_port = 22


class TestGetConnection(TestCase):
    def test_returns_pysftp_connection(self):
        for known_hosts in (None, ["a_hostname"]):
            with self.subTest(known_hosts=known_hosts):
                # Arrange
                mock_cnopts = MagicMock()
                mock_conn = MagicMock()
                with patch("tenQ.client.pysftp.CnOpts", return_value=mock_cnopts):
                    with patch("tenQ.client.pysftp.Connection", new=mock_conn):
                        # Act
                        _get_connection(
                            self._get_mock_settings(known_hosts=known_hosts)
                        )
                        # Assert: `pysftp.CnOpts` is initialized as expected
                        if known_hosts is None:
                            self.assertIsNone(mock_cnopts.hostkeys)
                        # Assert: `pysftp.Connection.__init__` is called as expected
                        mock_conn.assert_called_once_with(
                            "host",
                            username="username",
                            password="password",
                            port=_port,
                            cnopts=ANY,
                        )

    def _get_mock_settings(self, **kwargs) -> dict:
        settings = dict(
            host="host",
            username="username",
            password="password",
            port=_port,
            known_hosts=None,
        )
        settings.update(**kwargs)
        return settings


class TestPutFileInPrismeFolder(TestCase):
    _mock_settings = None

    def test_handles_known_exceptions(self):
        def raise_connection_exception(*args):
            raise ConnectionException("host", _port)

        def raise_credential_exception(*args):
            raise CredentialException("message")

        known = (
            # `ftplib` exceptions
            list(all_ftp_errors)
            # `paramiko.ssh_exception` exceptions (base class)
            + [SSHException]
            # `pysftp.exceptions` exceptions
            + [
                raise_connection_exception,
                raise_credential_exception,
                HostKeysException,
            ]
        )
        for exception in known:
            with self.subTest(exception=exception):
                with patch("tenQ.client._get_connection", side_effect=exception):
                    with self.assertRaises(ClientException):
                        put_file_in_prisme_folder(self._mock_settings, None, "")

    def test_filename_is_provided_for_file_like_object(self):
        file_like_object = io.BytesIO()
        with self.assertRaises(Exception):
            put_file_in_prisme_folder(
                self._mock_settings,
                file_like_object,
                "folder",
                destination_filename=None,
            )

    def test_source_file_name_or_object_is_type_checked(self):
        with self._mocked_client(MagicMock()):
            with self.assertRaises(TypeError):
                put_file_in_prisme_folder(
                    self._mock_settings,
                    None,
                    "folder",
                )

    def test_upload_using_filename(self):
        client = MagicMock()
        with self._mocked_client(client):
            put_file_in_prisme_folder(self._mock_settings, "filename", "folder")
            client.put.assert_called_once_with(
                "filename", remotepath=ANY, callback=None
            )

    def test_upload_using_file_like_object(self):
        client = MagicMock()
        file_like_object = io.BytesIO()
        with self._mocked_client(client):
            put_file_in_prisme_folder(
                self._mock_settings,
                file_like_object,
                "folder",
                destination_filename="filename",
            )
            client.putfo.assert_called_once_with(
                file_like_object, remotepath=ANY, callback=None
            )

    def _mocked_client(self, mocked_connection) -> patch:
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mocked_connection
        return patch("tenQ.client._get_connection", return_value=mock_context)
