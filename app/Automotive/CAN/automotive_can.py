from scapy.all import *
import can
import can.interfaces.vector
class CANFrame:
    def __init__(self, flags, identifier, length, reserved, data):
        self.flags = flags
        self.identifier = identifier
        self.length = length
        self.reserved = reserved
        self.data = data

    def __repr__(self):
        return (f"CANFrame(flags={self.flags}, identifier={self.identifier}, "
                f"length={self.length}, reserved={self.reserved}, data={self.data})")

    def to_bytes(self):
        # Convert the CAN frame to bytes for transmission
        frame = bytearray()
        frame.append(self.flags)
        frame.extend(self.identifier.to_bytes(4, 'big'))
        frame.append(self.length)
        frame.extend(self.reserved.to_bytes(2, 'big'))
        frame.extend(self.data)
        return bytes(frame)

    @classmethod
    def from_bytes(cls, frame_bytes):
        # Create a CAN frame from bytes
        flags = frame_bytes[0]
        identifier = int.from_bytes(frame_bytes[1:5], 'big')
        length = frame_bytes[5]
        reserved = int.from_bytes(frame_bytes[6:8], 'big')
        data = frame_bytes[8:]
        return cls(flags, identifier, length, reserved, data)

# Example usage
frame = CANFrame(flags=0x01, identifier=0x123, length=8, reserved=0x00, data=b'\x01\x02\x03\x04\x05\x06\x07\x08')
print(frame)
print(frame.to_bytes())


def CANFuzz(type, channel, flags, identifier, length, reserved, data):
    load_layer("can")
    if type == "cansocket":
        load_contrib('cansocket')
        socket = CANSocket(channel= channel)
        packet = CAN(flags=flags, identifier=identifier, length=length, reserved=reserved, data=data)
        socket.send(packet)
        rx_packet = socket.recv()

        socket.sr1(packet, timeout=1)


    elif type == "vector":
        conf.contribs['CANSocket'] = {'use-python-can' : True}
        load_contrib('cansocket')
        socket = CANSocket("vcan0")
        #socket = CANSocket(bustype='vector', channel=0, bitrate=1000000)
        packet = CAN(flags=flags, identifier=identifier, length= length, reserved = reserved, data=data)
        packet.show()

    else:
        print ("error")

CANFuzz(type="cansocket" ,channel="vcan0", flags="extended", identifier=0x10010000, length=8, reserved=0x00, data=b'\x01\x02\x03\x04\x05\x06\x07\x08')
