from ftplib import all_errors as all_ftp_errors
from io import IOBase
from typing import Callable

import pysftp


class ClientException(Exception):
    pass

# To tunnel to the real ftp server:
# ssh -L 172.17.0.1:2222:sftp.erp.gl:22 [your_username]@10.240.76.76


def put_file_in_prisme_folder(settings, source_file_name_or_object, destination_folder: str, destination_filename: str = None, callback: Callable[[int, int], None] = None):
    try:
        if isinstance(source_file_name_or_object, IOBase) and destination_filename is None:
            raise Exception("Must provide a filename when writing file-like object")
        remote_path = f"{destination_folder}/{destination_filename}" if destination_filename is not None else None
        cnopts = pysftp.CnOpts(settings['known_hosts'])
        if settings['known_hosts'] is None:
            cnopts.hostkeys = None

        with pysftp.Connection(settings['host'], username=settings['username'], password=settings['password'], port=settings.get('port', 22), cnopts=cnopts) as client:
            if type(source_file_name_or_object) == str:
                client.put(source_file_name_or_object, remotepath=remote_path, callback=callback)
            elif isinstance(source_file_name_or_object, IOBase):
                client.putfo(source_file_name_or_object, remotepath=remote_path, callback=callback)
            else:
                raise TypeError(f"file_path_or_object (type={type(source_file_name_or_object)}) not recognized")
    except all_ftp_errors as e:
        raise ClientException(str(e)) from e
