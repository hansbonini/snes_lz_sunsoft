import io
import struct
import codecs

from os import SEEK_SET, SEEK_CUR, SEEK_END
from PIL import Image


class TBL(io.StringIO):
    """
        Class to manipulate generic TBL files
        and transform them into python encoding
    """
    char_to_byte = {}
    byte_to_char = {}
    bits = 8
    name = 'tbl'

    def __init__(self, filename, name):
        try:
            self.raw = open(filename, 'r').read()
        except FileNotFoundError:
            print('[ERROR] Unable to found file')
            exit(0)
        super(TBL, self).__init__(self.raw)
        for line in self.raw.split('\n'):
            key, value = line.split('=')
            key = int(key, 16)
            self.byte_to_char[key] = value
            self.char_to_byte[value] = key
        self.name = name
        codecs.register(self.register)

    def decode(self, _bytes):
        s = ''
        readed = 0
        for byte in _bytes:
            search = 0
            found = 0
            _cursor = 0
            _buffer = [byte for byte in _bytes]
            del _buffer[0:readed]
            if len(_buffer) > 0:
                while _cursor < len(_buffer):
                    search = (search << 8) | _buffer[_cursor]
                    _cursor += 1
                    if search in self.byte_to_char:
                        s += self.byte_to_char[search]
                        found = 1
                        readed += _cursor
                if not found:
                    s += '[${:02X}]'.format(_buffer[0])
                    readed += 1
        return (s, len(_bytes))

    def encode(self, s):
        pass

    def register(self, _):
        return codecs.CodecInfo(self.encode, self.decode, name=self.name)


class ROM(io.BytesIO):
    """
        Class to manipulate generic ROM files
    """

    CURSOR = 0
    SIZE = 0
    ENDIAN = '@'

    def __init__(self, filename, endian=None):
        try:
            self.raw = open(filename, 'rb').read()
        except FileNotFoundError:
            print('[ERROR] Unable to found file')
            exit(0)
        super(ROM, self).__init__(self.raw)
        self.SIZE = len(self.raw)
        if endian == 'big':
            self.ENDIAN = '>'
        if endian == 'little':
            self.ENDIAN = '<'

    def read_8(self):
        self.seek(self.CURSOR, SEEK_SET)
        readed = struct.unpack(self.ENDIAN+'B', self.read(1))[0]
        self.CURSOR += 1
        return readed

    def read_16(self):
        self.seek(self.CURSOR, SEEK_SET)
        readed = struct.unpack(self.ENDIAN+'H', self.read(2))[0]
        self.CURSOR += 2
        return readed

    def read_32(self):
        self.seek(self.CURSOR, SEEK_SET)
        readed = struct.unpack(self.ENDIAN+'I', self.read(4))[0]
        self.CURSOR += 4
        return readed

    def read_str(self, length=1):
        self.seek(self.CURSOR, SEEK_SET)
        readed = struct.unpack(self.ENDIAN+str(length) +
                               's', self.read(length))[0]
        self.CURSOR += length
        return readed

    def read_ascii_str(self, length=1):
        readed = self.read_str(length)
        return readed.decode('ascii')

    def read_sjis_str(self, length=1):
        readed = self.read_str(length)
        return readed.decode('sjis')

    def read_utf8_str(self, length=1):
        readed = self.read_str(length)
        return readed.decode('utf-8')

    def read_utf16_str(self, length=1):
        readed = self.read_str(length*2)
        return readed.decode('utf-16be')

    def read_str_from_tbl(self, length=1, tbl_name='name'):
        readed = self.read_str(length)
        return readed.decode(tbl_name)

    def set_offset(self, offset=0):
        self.CURSOR = offset
        self.seek(self.CURSOR, SEEK_SET)

    def get_offset(self):
        return self.tell()

    def search_bytes(self, byte_sequence=b''):
        return byte_sequence in self.raw


class RingBuffer:
    """
        Class to manage a Ring Buffer, also known as:
        circular buffer, circular queue or cyclic buffer.

        A ring buffer is a common implementation of a queue.
        It is popular because circular queues are easy to implement.
        While a ring buffer is represented as a circle,
        in the underlying code, a ring buffer is linear.
        A ring buffer exists as a fixed-length array.     
    """
    MAX_WINDOW_SIZE = 0
    MASK = 0
    CURSOR = 0
    BYTE_FILL = 0

    def __init__(self, max_window_size=0x1024, start_offset=0, fill_byte=0x0):
        self.MAX_WINDOW_SIZE = max_window_size
        self.MASK = self.MAX_WINDOW_SIZE-1
        self.CURSOR = start_offset
        self.BYTE_FILL = fill_byte
        self._buffer = bytearray([self.BYTE_FILL]*self.MAX_WINDOW_SIZE)

    def append(self, byte):
        self._buffer[self.CURSOR] = byte
        self.CURSOR = (self.CURSOR+1) % self.MAX_WINDOW_SIZE

    def set(self, offset, byte):
        self._buffer[offset % self.MAX_WINDOW_SIZE] = byte

    def get(self, offset):
        return self._buffer[offset % self.MAX_WINDOW_SIZE]


class BitArray:
    """
        Class to manipulate bits as array
    """
    ENDIAN_TYPE = 'big'
    CURSOR = 0
    _buffer = []
    output = bytearray()

    def __init__(self, input_data=None, endian='big'):
        self.ENDIAN_TYPE = endian
        # If input data is a bytearra
        # transform them into a list of bits
        if input_data:
            for byte in input_data:
                bitstring = "{:08b}".format(byte)
                for bit in range(len(bitstring)):
                    self.append(bitstring[bit])

    def append(self, bit):
        self._buffer.append(int(bit))

    def read(self, length=1):
        bits = self._buffer[self.CURSOR:self.CURSOR+length]
        self.CURSOR += length
        return bits

    def read_int(self, length=1):
        bits = self.read(length)
        value = 0
        for bit in bits:
            value = (value << 1) | bit
        return value


class Compression:
    """
        Base class to manage compressions
    """
    _buffer = bytearray()
    signature = None

    def __init__(self, input_data):
        self.DATA = input_data

    def decompress(self, offset=0):
        pass

    def compress(self, offset=0):
        pass


class LZSS(Compression):
    """
        Base class to manipulate LZSS Compressions
    """

    _window = RingBuffer()
    MAX_LENGTH = 0x40
    MIN_LENGTH = 0x3
    LOOKAHEAD = 0b1111

    def __init__(self, input_data):
        super(LZSS, self).__init__(input_data)

    def append(self, value):
        self._buffer.append(value)
        self._window.append(value)
        return 1

    def append_from_zeroes(self, length=0):
        count = 0
        for i in range(length):
            tmp = 0x00
            count += self.append(tmp)
        return count

    def append_from_data(self, length=0):
        count = 0
        for i in range(length):
            tmp = self.DATA.read_8()
            count += self.append(tmp)
        return count

    def append_from_data_padded(self, length=0):
        count = 0
        offset = self.DATA.tell()
        for i in range(length):
            tmp = self.DATA.read_8()
            self.DATA.read_8()
            count += self.append(tmp)
        print(self.DATA.tell())
        self.DATA.seek(offset, 0)
        for i in range(length):
            self.DATA.read_8()
            tmp = self.DATA.read_8()
            count += self.append(tmp)
        print(self.DATA.tell())
        return count

    def append_from_data_rle(self, length=0):
        count = 0
        tmp = self.DATA.read_8()
        for i in range(length):
            count += self.append(tmp)
        return count

    def append_from_window(self, length=0, offset=0):
        count = 0
        for i in range(length):
            tmp = self._window.get(offset+i)
            count += self.append(tmp)
        return count

    # Original
    def find_matches(self):
        valid_window_range = []
        best_match_index = -1
        best_match_length = -1
        start_data_offset = self.DATA.CURSOR
        start_window_offset = (self._window.CURSOR -
                               self.LOOKAHEAD) & self._window.MASK
        current_window_offset = self._window.CURSOR
        end_data_offset = min(
            self.DATA.CURSOR+self.LOOKAHEAD, self.DATA.SIZE-1)
        mask = self._window.MASK
        for i in range(self.LOOKAHEAD):
            valid_window_range.append((start_window_offset+i) & mask)
        for window_offset in valid_window_range:
            length = 0
            temp_window = self._window._buffer.copy()
            while (((start_data_offset + length) < end_data_offset) and length < self.LOOKAHEAD) and temp_window[(window_offset+length) & mask] == self.DATA.raw[start_data_offset+length]:
                temp_window[(current_window_offset+length) &
                            mask] = self.DATA.raw[start_data_offset+length]
                length += 1
            if length > best_match_length:
                best_match_length = length
                best_match_index = window_offset
        if best_match_index > 0 and best_match_length > 0:
            return (best_match_index, best_match_length)
        return None

    # Optimized
    def find_matches_optimized(self):
        matches = []
        temp_window = self._window._buffer.copy()
        for i in range(self.DATA.CURSOR, min(self.DATA.CURSOR+self.LOOKAHEAD+self.MIN_LENGTH+0x1, self.DATA.SIZE-1)):
            last_ocurrence = 0
            search = self.DATA.raw[self.DATA.CURSOR:i]
            invalided = [(self._window.CURSOR+len(search)+1) & self._window.MASK]
            for x in range(len(search)):
                temp_window[(self._window.CURSOR+x) &
                            self._window.MASK] = search[x]
            possible_chains = temp_window.count(search)
            # Probe all possible chains
            for probed_chains in range(possible_chains):
                index = temp_window.find(search, last_ocurrence)
                last_ocurrence = index
                match = b''
                for x in range(len(search)):
                    match += self._window.get(index+x).to_bytes(1, 'big')
                if match == search and index and not index in invalided:
                    matches.append((index, len(match)))
        if len(matches) > 0:
            best_match = self.get_best_match(matches)
            return best_match
        return None

    def get_best_match(self, matches):
        matches.sort(key=lambda y: y[0])
        matches.sort(key=lambda y: y[1])
        return matches[-1]


class Palette:
    colors = []
    CURSOR = 0

    def __init__(self, input_data):
        self.DATA = input_data
        self.SIZE = len(self.DATA)
        while self.CURSOR < self.SIZE:
            color = self.DATA[self.CURSOR] << 8 | self.DATA[self.CURSOR+1]
            R, G, B, A = self.bpp_4_bgra_to_rgba(color)
            self.colors.append((R, G, B, A))
            self.CURSOR += 2

    def bpp_4_bgra_to_rgba(self, value):
        A = ((value >> 12) & 0xF)
        B = ((value >> 8) & 0xF)
        G = ((value >> 4) & 0xF)
        R = (value & 0xF)
        A = 0xF-A
        R, G, B, A = self.rgba_4_to_8(R, G, B, A)
        print("{:02x} {:02x} {:02x} {:02x}".format(R, G, B, A))
        return R, G, B, A

    def rgba_4_to_8(self, R, G, B, A):
        R = R << 4 | R
        G = G << 4 | G
        B = B << 4 | B
        A = A << 4 | A
        return R, G, B, A


class Tiles:
    """
        Class to manipulate tiles
    """

    _buffer = []
    palette = None
    CURSOR = 0
    SIZE = 0

    def __init__(self, input_data, palette=None):
        self.DATA = input_data
        self.SIZE = len(self.DATA)
        self.palette = palette

    def createRGBImage(self, filename, width=None):
        size = self.get_size(width)
        self.image = Image.new('RGBA', size)
        self._buffer = self.image.load()
        NIBBLE = 0
        while NIBBLE < (self.SIZE*2):
            col = NIBBLE % 8
            line = (NIBBLE // 8) % 8
            tile = (NIBBLE // 64)
            x = col + ((tile * 8) % size[0])
            y = line + ((tile * 8) // size[1]) * 8
            if NIBBLE & 0x1:
                pixel = self.DATA[self.CURSOR] >> 4
            else:
                pixel = self.DATA[self.CURSOR] & 0xF
            if self.palette:
                self._buffer[x, y] = self.palette.colors[pixel]
            else:
                R, G, B, A = self.bpp_4_bgra_to_rgba(pixel)
                self._buffer[x, y] = (R, G, B, A)
            self.CURSOR = NIBBLE//2
            NIBBLE += 1
        self.save(filename)

    def bpp_4_bgra_to_rgba(self, value):
        B = ((value >> 3) & 0x1)
        G = ((value >> 2) & 0x1)
        R = ((value >> 1) & 0x1)
        A = (value & 0x1)
        R, G, B, A = self.rgba_4_to_32(R, G, B, A)
        return R, G, B, A

    def rgba_4_to_32(self, R, G, B, A):
        for i in range(7):
            R = R << 1 | R
            G = G << 1 | G
            B = B << 1 | B
            A = A << 1 | A
        return R, G, B, A

    def get_size(self, width=None):
        if width is None:
            size = self.SIZE
            if size < 10240:
                width = 32
            elif 10240 <= size <= (10240 * 3):
                width = 64
            elif 10240 <= size <= (10240 * 6):
                width = 128
            elif 10240 <= size <= (10240 * 10):
                width = 256
            elif 10240 <= size <= (10240 * 20):
                width = 384
            elif 10240 <= size <= (10240 * 50):
                width = 512
            elif 10240 <= size <= (10240 * 100):
                width = 768
            else:
                width = 1024
            height = (size // width) + 1
        else:
            width = math.sqrt(self.SIZE)+1
            height = width
        return 16*8, 16*8

    def save(self, filename):
        try:
            self.image.save(filename)
        except Exception as err:
            print(err)
