import os
import sys
import json
import struct
import hashlib

from typing import Dict, Union
from types import SimpleNamespace
from collections import namedtuple

# Library for implementing any of the necessary File Transfer Protocols used to transfer the binary file.
# Binary File Transfer Protocol:
#     TCP:
#         - in-order data and reliable transmission
#         - timeout/retries should be specified, and requesting specific chunks from the file may be supported
#     Header Specifications:
#         - byteorder: system's network byteorder (endian-ness)
#         - action: 'START-REQUEST' | 'END-REQUEST' | 'CONFIRM' | 'RECEIVE'
#         - content-length: length of packet content
#     Action Specifications:
#         - 'START-REQUEST': initiates file transfer request; packet content is the file's name
#         - 'END-REQUEST': ends file transfer request; packet content is the file's checksum for client verification
#         - 'RECEIVE': meant for the client; packet content is a BUFFER_SIZE large file chunk
#         - 'CONFIRM': meant for the server; packet content is the checksum of
#                      the most recently sent packet content (to be verified server-side)
# References:
#     - https://realpython.com/python-sockets
#     - https://docs.python.org/3/library/socketserver.html
# In this example, the minimal TCP server will send the binary file to a specified client on request.
# The client initiates the connection and sends a request message, followed by processing the server’s response message.
# The server waits for a connection, processes the client’s request message, and then sends a response message

HOST, PORT = '127.0.0.1', 64000  # defaults
BUFFER_SIZE = 4096
PROTO_HEADER_LENGTH = 2  # bytes
ENCODING = 'utf-8'
CONTENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content')

_actions = namedtuple('_ACTIONS_', ['START_REQUEST', 'END_REQUEST', 'CONFIRM', 'RECEIVE'])
ACTIONS = _actions('START-REQUEST', 'END-REQUEST', 'CONFIRM', 'RECEIVE')

_headers = namedtuple('_HEADERS_', ['BYTEORDER', 'CONTENT_LEN', 'ACTION'])
HEADERS = _headers('byteorder', 'content-length', 'action')


class PacketData(SimpleNamespace):
    checksum: str
    header: Dict
    header_len: int
    content: bytearray
    buffer: bytearray

    def __init__(self):
        super(PacketData, self).__init__()
        self.buffer = bytearray()
        self.checksum = None  # updated per-packet, client checks for server-side verification . . .
        self.header_len = None
        self.header = None
        self.content = None

    def reset(self):
        self.content = None
        self.header = None
        self.header_len = None
        self.checksum = None


def process_proto_header(packet: PacketData):
    if len(packet.buffer) >= PROTO_HEADER_LENGTH:
        packet.header_len = struct.unpack(">H", packet.buffer[:PROTO_HEADER_LENGTH])[0]
        packet.buffer = packet.buffer[PROTO_HEADER_LENGTH:]


def process_header(packet: PacketData):
    if len(packet.buffer) >= packet.header_len:
        packet.header = decode(packet.buffer[:packet.header_len])
        if any(hdr not in packet.header for hdr in HEADERS):
            raise ValueError("invalid packet: missing required header")
        if packet.header['action'] not in ACTIONS:
            raise ValueError(f"invalid packet: invalid action specification '{packet.header[HEADERS.ACTION]}'")
        packet.buffer = packet.buffer[packet.header_len:]


def process_content(packet: PacketData):
    content_len = packet.header[HEADERS.CONTENT_LEN]
    if len(packet.buffer) < content_len:
        return
    packet.content = packet.buffer[:content_len]
    packet.buffer = packet.buffer[content_len:]


def process_packet(packet: PacketData):
    if packet.header_len is None:  # process proto-header
        process_proto_header(packet)

    if packet.header_len is not None:  # process packet header
        if packet.header is None:
            process_header(packet)

    if packet.header is not None:  # process packet content
        if packet.content is None:
            process_content(packet)


def encode(packet_data: Union[Dict, str]) -> bytes:
    return json.dumps(packet_data, ensure_ascii=False).encode(encoding=ENCODING)


def decode(packet_data: Union[bytes, bytearray]) -> Dict:
    return json.loads(packet_data.decode(encoding=ENCODING))


def create_packet(packet_content: Union[bytes, bytearray, str], action: str, additional_headers: Dict = None):
    if not isinstance(packet_content, (bytes, bytearray)):
        packet_content = encode(packet_content)

    header = {HEADERS.BYTEORDER: sys.byteorder,  # remove/specify '>' ? - parse/convert to client sys.byteorder ?
              HEADERS.ACTION: action,
              HEADERS.CONTENT_LEN: len(packet_content)}

    if additional_headers is not None:
        header.update(additional_headers)

    packet_header = encode(header)
    proto_header = struct.pack(">H", len(packet_header))
    message = proto_header + packet_header + packet_content
    return message


def packet_md5sum(data: Union[bytes, bytearray]):
    return hashlib.md5(data).hexdigest()


def file_md5sum(filename: str):
    hash_md5 = hashlib.md5()
    with open(os.path.join(CONTENT_DIR, filename), 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
