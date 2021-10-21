import struct
import sys

from romhacking.common import BitArray, RingBuffer, Compression, LZSS

class SUNSOFT(LZSS):
    """
        Class to manipulate SUNSOFT Compression

        Games where this compression is found:
        [SNES] Sugoi Hebereke

    """

    def __init__(self, input_data):
        super(SUNSOFT, self).__init__(input_data)

    def decompress(self, offset=0):
        self.DATA.set_offset(offset)
        self.DATA.ENDIAN = '<'
        self._window = RingBuffer(0x1000, 0xFEE, 0x00)
        self._buffer = bytearray()
        compressed_size = self.DATA.read_16()
        while (compressed_size > 0):
            control = self.DATA.read_8()
            compressed_size-=1
            for readed_bits in range(8):
                bit = bool((control >> readed_bits) & 0x1)
                if bit:
                    _readed = self.DATA.read_8()
                    self.append(_readed)
                    compressed_size-=1
                else:
                    low, high = self.DATA.read_8(), self.DATA.read_8()
                    length = (high & 0xF) + 3
                    offset = (low | ((high<<4)&0xF00))
                    self.append_from_window(
                        length, offset)
                    compressed_size-=2
        return self._buffer

    def compress(self):
        self.DATA.ENDIAN = '<'
        self._window = RingBuffer(0x1000, 0xFEE, 0x00)
        self._buffer = bytearray()
        self._output = bytearray()
        self._output.append(0x00)
        self._output.append(0x00)
        self._encoded = 0
        self.LOOKAHEAD = 0b1111
        bitflag = []
        bitcount = 0
        while self._encoded < self.DATA.SIZE:
            current_offset = self.DATA.CURSOR
            if bitcount > 7:
                bitcount, bitflag = self.write_command_bit(bitcount, bitflag)
            match = self.find_matches_optimized()
            if match and match[1] >= 0x3 and self._encoded+match[1] < self.DATA.SIZE:
                bitflag.append(0)
                (index, length) = match
                lzpair1 = (index&0xFF)
                lzpair2 = ((index&0xF00)>>4) | (length-3)
                self._buffer.append(lzpair1)
                self._buffer.append(lzpair2)
                for i in range(0, length):
                    self._window.append(self.DATA.read_8())
                    self._encoded += 1
            else:
                bitflag.append(1)
                _readed = self.DATA.read_8()
                self._buffer.append(_readed)
                self._window.append(_readed)
                self._encoded += 1
            bitcount += 1
        compressed_size = len(self._output)-2
        self._output[0]=compressed_size >> 8
        self._output[1]=compressed_size &0xFF
        return self._output

    def write_command_bit(self, bitcount, bitflag):
        bitflag.reverse()
        self._output.append(int('0b'+''.join(map(str, bitflag)), 2))
        for value in self._buffer:
            self._output.append(value)
        self._buffer = bytearray()
        bitflag = []
        bitcount = 0
        return bitcount, bitflag