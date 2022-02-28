#!/usr/bin/env python3.6

import os
import socket

import ftplib


class BinaryFTPServer:  # Server sends binary file specified by client upon request

    packet: ftplib.PacketData
    request: socket
    client_address: int
    _awaiting_confirmation: bool
    _file_offset: int
    _requested_file: str

    def __init__(self):
        self.request = None  # self.request is the TCP socket connected to the client
        self.client_address = None
        self.packet = None
        self._requested_file = None
        self._file_offset = 0
        self._awaiting_confirmation = False

    def startup(self, host_address=ftplib.HOST, port=ftplib.PORT):  # Default: host_address='localhost', port=64000
        self.packet = ftplib.PacketData()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:  # TODO move to init, call sock/self.request close() in __delete__ ?
            sock.bind((host_address, port))
            sock.listen()
            print("listening . . .")
            self.request, self.client_address = sock.accept()
            with self.request:
                print("Connected by: ", self.client_address)
                while True:
                    if self._awaiting_confirmation or self._requested_file is None:  # Need to recv data from client
                        try:
                            data = self.request.recv(ftplib.BUFFER_SIZE)
                        except BlockingIOError:
                            pass
                        else:
                            if data:
                                self.packet.buffer += data
                                ftplib.process_packet(self.packet)

                                if self.packet.content is not None:
                                    action = self.packet.header[ftplib.HEADERS.ACTION]

                                    if action == ftplib.ACTIONS.START_REQUEST:  # Process initial client request
                                        self.do_START_REQUEST()
                                    elif action == ftplib.ACTIONS.CONFIRM:  # Process client confirmation packet
                                        self.do_CONFIRM()
                                    else:
                                        raise ValueError(f"invalid action '{action}' specified for server")
                            else:
                                raise RuntimeError('No FTP packet sent from client')

                    # Wait for confirmation before sending next FTP packet
                    if self._requested_file is not None and not self._awaiting_confirmation:
                        file_data = self._read_file()

                        if not file_data:  # No data left, server has met EOF - 'END-REQUEST'
                            self.do_END_REQUEST()
                            break
                        else:  # Data remains, send it to the client - 'RECEIVE'
                            self.do_RECEIVE(file_data)

    def do_START_REQUEST(self):
        if self._requested_file is None:
            self._requested_file = ftplib.decode(self.packet.content)
            file_path = os.path.join(ftplib.CONTENT_DIR, self._requested_file)
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                raise ValueError(f"invalid request: '{self._requested_file}' does not exist or is not a valid file.")
            self.packet.reset()
        else:
            raise ValueError('invalid packet: file has already been requested')

    def do_END_REQUEST(self):
        file_checksum = ftplib.file_md5sum(self._requested_file)
        ftp_end_packet = ftplib.create_packet(file_checksum, action=ftplib.ACTIONS.END_REQUEST)
        print(f"All '{self._requested_file}' data sent to client; shutting down . . .")
        self._file_offset = 0
        self._requested_file = None
        self.request.send(ftp_end_packet)
        self._awaiting_confirmation = False

    def do_RECEIVE(self, file_chunk: bytes):
        self.packet.checksum = ftplib.packet_md5sum(file_chunk)
        ftp_data_packet = ftplib.create_packet(file_chunk, action=ftplib.ACTIONS.RECEIVE)
        self._awaiting_confirmation = True
        self.request.send(ftp_data_packet)

    def do_CONFIRM(self):
        if self._awaiting_confirmation:
            if self.packet.checksum != ftplib.decode(self.packet.content):
                raise ValueError('corrupted packet: mismatched checksum detected')
            self._awaiting_confirmation = False  # send next packet w/file data . . .
            self.packet.reset()
        else:
            raise ValueError('invalid packet: no verification has been requested')

    def _read_file(self, chunk_size=ftplib.BUFFER_SIZE - ftplib.PROTO_HEADER_LENGTH) -> bytes:
        with open(os.path.join(ftplib.CONTENT_DIR, self._requested_file), 'rb') as f:
            f.seek(self._file_offset)
            file_chunk = f.read(chunk_size)
            self._file_offset = f.tell()
        return file_chunk


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Start the FTP server (echo/LAN) on a specific port.')
    parser.add_argument('--LAN', '--non-local',
                        help='Specifies LAN server with IPv4 address. If not chosen, defaults to loopback/echo server.',
                        action='store_true',
                        default=False)
    parser.add_argument('-p', '--port', '--server-port',
                        help='The port number of the listening server socket. Defaults to 64000.',
                        type=int,
                        default=ftplib.PORT)

    args = parser.parse_args()

    if args.LAN:
        host = socket.gethostbyname(socket.gethostname())
    else:
        host = ftplib.HOST

    ftp_server = BinaryFTPServer()
    ftp_server.startup(host, args.port)
