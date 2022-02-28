#!/usr/bin/env python3.6

import os
import socket

import ftplib
DIR = os.path.dirname(os.path.abspath(__file__))  # default
FILE = "sample1.txt"  # default


class BinaryFTPClient:  # Client initiates file request from server

    _socket: socket

    def __init__(self, filename: str = FILE):
        self.packet = ftplib.PacketData()
        self._socket = None
        filename_path = os.path.join(DIR, filename)
        if os.path.exists(filename_path) and os.path.isfile(filename_path):
            raise ValueError(f"invalid file request: '{filename_path}' already exists.")
        else:
            self.file_request = filename

    def startup(self, host_address=ftplib.HOST, port=ftplib.PORT):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self._socket:
            self._socket.connect((host_address, port))  # Connect to server and send file request

            ftp_request = ftplib.create_packet(self.file_request, action=ftplib.ACTIONS.START_REQUEST)
            self._socket.send(ftp_request)
            while True:
                try:  # Receive data from the server and send packet checksum once entire packet is received
                    data = self._socket.recv(ftplib.BUFFER_SIZE)
                except BlockingIOError:
                    pass
                else:
                    if data:  # Non-zero number of bytes were received
                        self.packet.buffer += data
                        ftplib.process_packet(self.packet)

                        if self.packet.content is not None:
                            action = self.packet.header[ftplib.HEADERS.ACTION]

                            if action == ftplib.ACTIONS.RECEIVE:  # Process received file data
                                self.do_RECEIVE()
                            elif action == ftplib.ACTIONS.END_REQUEST:  # Verify file checksum and exit
                                self.do_END_REQUEST()
                                break
                            else:
                                raise ValueError(f"invalid action '{action}' specified for client")

    def do_RECEIVE(self):
        with open(os.path.join(DIR, 'copy_of_' + self.file_request), 'ab') as f:  # Append received data to file
            f.write(self.packet.content)

        checksum = ftplib.packet_md5sum(self.packet.content)
        confirmation_packet = ftplib.create_packet(checksum, action=ftplib.ACTIONS.CONFIRM)
        self._socket.send(confirmation_packet)

        self.packet.reset()

    def do_END_REQUEST(self):
        file_checksum = ftplib.file_md5sum(self.file_request)
        if file_checksum == ftplib.decode(self.packet.content):
            print(f"Success! '{self.file_request}' has been transferred without incident . . .")
        else:
            raise ValueError('corrupted file: transfer failed: mismatched checksum detected')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Start the FTP client on a specific host/port and request a file.')
    parser.add_argument('-f', '--file',
                        help='The name of the file to request from the server.',
                        default=FILE)
    parser.add_argument('-d', '--dir',
                        help='The directory in which to store the file when received.',
                        default=DIR)
    parser.add_argument('-s', '--server', '--host',
                        help='The IPv4 address of the server host. Defaults to localhost.',
                        default=ftplib.HOST)
    parser.add_argument('-p', '--port', '--server-port',
                        help='The port number of the server host to connect with. Defaults to 64000.',
                        type=int,
                        default=ftplib.PORT)

    args = parser.parse_args()

    if not os.path.exists(args.dir) or not os.path.isdir(args.dir):
        raise ValueError("invalid directory: '{}' does not exist or is not a valid directory.")
    else:
        DIR = args.dir

    ftp_client = BinaryFTPClient(filename=args.file)
    ftp_client.startup(args.server, args.port)
