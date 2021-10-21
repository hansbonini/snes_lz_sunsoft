from romhacking.common import ROM as GenericROM


class ROM(GenericROM):
    """
        Class to manipulate Super Nintendo / Super Famicom
        ROM files
    """

    def __init__(self, filename, endian=None):
        super(ROM, self).__init__(filename, endian)
