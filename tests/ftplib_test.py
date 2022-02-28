import os
import unittest
import ftplib


class FTPLibraryTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(FTPLibraryTestCase, self).__init__(*args, **kwargs)
        self.filename = "test.png"
        self.packet = ftplib.PacketData()
        self.action = None

    def setUp(self):
        self.assertEqual(0, len(self.packet.buffer))
        self.packet.reset()
        self.assertIsNone(self.packet.checksum)
        self.assertIsNone(self.packet.header)
        self.assertIsNone(self.packet.header_len)
        self.assertIsNone(self.packet.content)

    def packet_testing(self, packet_data):
        self.packet.buffer += packet_data
        ftplib.process_packet(self.packet)
        self.assertIsInstance(packet_data, (bytes, bytearray))

        self.assertIsNone(self.packet.checksum)
        self.assertIsInstance(self.packet.header, dict)
        self.assertIsInstance(self.packet.header_len, int)
        self.assertIsInstance(self.packet.content, bytearray)
        self.assertIsInstance(self.packet.buffer, bytearray)

        self.assertEqual(self.packet.header['action'], self.action)

    def test_start_packet(self):
        self.action = ftplib.ACTIONS.START_REQUEST
        ftp_start_request = ftplib.create_packet(self.filename, self.action)
        self.packet_testing(ftp_start_request)

        # Test Decoding
        self.assertEqual(self.filename, ftplib.decode(self.packet.content))
        self.assertEqual('test.png', ftplib.decode(self.packet.content))

    def test_end_packet(self):
        self.action = ftplib.ACTIONS.END_REQUEST
        file_md5sum = ftplib.file_md5sum(self.filename)
        ftp_end_request = ftplib.create_packet(file_md5sum, self.action)
        self.packet_testing(ftp_end_request)

        self.assertEqual(file_md5sum, ftplib.decode(self.packet.content))

    def test_confirm_and_receive(self):
        self.action = ftplib.ACTIONS.RECEIVE
        with open(os.path.join(ftplib.CONTENT_DIR, self.filename), 'rb') as f:
            f.seek(0)  # beginning of file
            file_data = f.read(ftplib.BUFFER_SIZE - ftplib.PROTO_HEADER_LENGTH)
            file_offset = f.tell()

        ftp_receive = ftplib.create_packet(file_data, self.action)
        self.packet_testing(ftp_receive)

        self.packet.checksum = ftplib.packet_md5sum(file_data)
        self.assertEqual(file_offset, ftplib.BUFFER_SIZE - ftplib.PROTO_HEADER_LENGTH)
        self.assertEqual(file_data, self.packet.content)

        packet_md5sum = ftplib.packet_md5sum(self.packet.content)
        data_md5sum = ftplib.packet_md5sum(file_data)
        self.assertEqual(packet_md5sum, data_md5sum)
        self.assertEqual(packet_md5sum, self.packet.checksum)

        self.setUp()
        self.action = ftplib.ACTIONS.CONFIRM
        ftp_confirm = ftplib.create_packet(packet_md5sum, self.action)
        self.packet_testing(ftp_confirm)

        self.assertEqual(data_md5sum, ftplib.decode(self.packet.content))
        self.assertEqual(packet_md5sum, ftplib.decode(self.packet.content))


if __name__ == '__main__':
    unittest.main()
