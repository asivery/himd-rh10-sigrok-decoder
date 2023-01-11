from sigrokdecode import Decoder as DecoderArchetype, OUTPUT_ANN
from enum import Enum
from dataclasses import dataclass
from typing import Callable
import math

@dataclass(frozen = True)
class Command:
    opcode: int
    length: int
    handler: Callable[[any, bytes], None]

def display_command_constlen(*, opcode = None, opcodes = None, length):
    class class_level_decorator:
        def __init__(self, fn):
            self.fn = fn
        def __set_name__(self, owner, name):
            all_opcodes = list(opcodes or [])
            if opcode:
                all_opcodes.append(opcode)
            for op in all_opcodes:
                owner.constant_length_commands[op] = Command(
                    op,
                    length,
                    self.fn
                )
                print(f"[Command Definition]: Added handler for command {hex(op)} - {name}")
    return class_level_decorator

class DecodingState(Enum):
    IDLE, PROLOGUE, DATA = range(3)

class AnnotationType():
    STATE, DEBUG, ASCII, COMMAND, ERROR = range(5)

class Decoder(DecoderArchetype):
    api_version = 3
    id = 'sony_himd'
    name = "Sony MZ-RH10/RH910 Display"
    longname = "Sony MZ-RH10/RH910 Display"
    desc = '';
    license = ''
    inputs = ['spi']
    outputs = ['sony_himd']
    tags = ['']
    options = ()
    annotations = (
        ('info', 'Info'),
        ('debug', 'Debug'),
        ('ascii', 'Ascii'),
        ('commands', 'Commands'),
        ('errors', 'Errors'),
    )
    annotation_rows = (
        ('state', 'States', (AnnotationType.STATE,)),
        ('debug', 'Debug', (AnnotationType.DEBUG,)),
        ('ascii', 'ASCII', (AnnotationType.ASCII,)),
        ('commands', 'Commands', (AnnotationType.COMMAND,)),
        ('errors', 'Errors', (AnnotationType.ERROR,)),
    )
    constant_length_commands = {}
    
    def start(self):
        self.out_ann = self.register(OUTPUT_ANN)
    
    def reset(self):
        # Overall state
        self.state = DecodingState.IDLE
        self.start_of_current_state = None
        
        # Prologue handler state
        self.prologue_bytes_remaining = 0
        
        # Data handler state
        self.data_bytes_remaining = 0
        self.data_bytes_count = 0
        self.data_xor = 0
        self.data_current_command = []
        self.data_current_command_start = 0
        self.data_current_command_end = 0
        self.data_current_command_bytes_remaining = 0
        
        
    def switch_state(self, newState, first_of_new):
        self.put(self.start_of_current_state, first_of_new, self.out_ann,
                 [AnnotationType.STATE, [f"State: {self.state.name}"]])
        self.start_of_current_state = first_of_new
        self.state = newState
        
    def handle_starting_byte(self, b, s, e):
        if b in [ 0x3D, 0x3F, 0xFF, 0x37 ]:
            self.switch_state(DecodingState.PROLOGUE, s)
            self.prologue_bytes_remaining = 3
        else:
            self.switch_state(DecodingState.DATA, s)
            self.data_bytes_count = 0
            self.data_bytes_remaining = 40
            self.data_xor = 0
            self.data_current_command = []
            self.data_current_command_start = 0
            self.data_current_command_end = 0
            self.data_current_command_bytes_remaining = 0
            self.data_current_command_handler = None
            
    def handle_prologue_message(self, b, s, e):
        self.prologue_bytes_remaining -= 1
        if self.prologue_bytes_remaining == 0:
            self.switch_state(DecodingState.IDLE, e)
    
    def handle_data_message(self, b, s, e):
        self.data_xor ^= b
        
        self.data_bytes_remaining -= 1
        if self.data_bytes_remaining == 0:
            if self.data_xor != 0xFF:
                self.put(self.start_of_current_state, e, self.out_ann, [AnnotationType.ERROR, [f"Checksum mismatch! ({hex(self.data_xor)} != 0xFF)"]])
            if self.data_bytes_count > 10:
                self.put(s, e, self.out_ann, [AnnotationType.DEBUG, [f"Debug: Dense packet"]])
            if self.data_current_command_bytes_remaining != 0:
                self.put(self.start_of_current_state, e, self.out_ann, [AnnotationType.ERROR, [f"Packet ended, but current command still has {self.data_current_command_bytes_remaining} bytes remaining!", f"-{self.data_current_command_bytes_remaining}"]])
            self.switch_state(DecodingState.IDLE, e)
            return
        if b:
            self.data_bytes_count += 1
            
        if self.data_current_command_handler and self.data_current_command_bytes_remaining == 0:
            # We've read all the bytes of the current command
            if not self.data_current_command_handler(self, self.data_current_command):
                self.data_current_command = []
                self.data_current_command_handler = None
            
        if not self.data_current_command:
            # No command being processed right now
            if b in Decoder.constant_length_commands:
                # This is our command now
                info = Decoder.constant_length_commands[b]
                
                self.data_current_command_bytes_remaining = info.length
                self.data_current_command_start = s
                self.data_current_command = []
                self.data_current_command_handler = info.handler
            elif b != 0:
                self.data_current_command_start, self.data_current_command_end = s, e
                self.put_command(f"Byte {hex(b)} - not a valid command", "?")
        
        # Command in progress...
        if self.data_current_command_bytes_remaining:
            self.data_current_command_bytes_remaining -= 1
            self.data_current_command.append(b)
            self.data_current_command_end = e
        
            
    
    def decode(self, start, end, data):
        name, value, _ = data
        if name != "DATA":
            return
        
        if value in range(ord(' '), ord('z')):
            self.put(start, end, self.out_ann,
                     [AnnotationType.ASCII, [f"'{chr(value)}'"]])
        
        # Make sure the first sample of the current state is set correctly.
        if self.start_of_current_state is None:
            self.start_of_current_state = start
        
        # If idling, send the byte to the idle state handler, then check the state again
        # the idle state handler itself shouldn't alter the state of any of the two
        # other modes of operation.
        if self.state == DecodingState.IDLE:
            self.handle_starting_byte(value, start, end)
        
        if self.state == DecodingState.PROLOGUE:
            self.handle_prologue_message(value, start, end)
        elif self.state == DecodingState.DATA:
            self.handle_data_message(value, start, end)
            
    def __init__(self): 
        self.reset()
        self.out_ann = None
        
    def put_command(self, *desc):
        self.put(self.data_current_command_start, self.data_current_command_end, self.out_ann,
                 [AnnotationType.COMMAND, [*desc]])
    def put_error(self, *desc):
        self.put(self.data_current_command_start, self.data_current_command_end, self.out_ann,
                 [AnnotationType.ERROR, [*desc]])
    
    def handle_unknown_command(self, data):
        bindump = ' '.join(('0' if x < 0x10 else '') + hex(x)[2:] for x in data)
        self.put_command(f"Command: '{bindump}'", bindump)
    
    @display_command_constlen(opcode = 0x02, length = 0x02)
    def handle_command_02(self, data):
        self.handle_unknown_command(data)
    
    @display_command_constlen(opcode = 0x03, length = 0x02)
    def handle_command_03(self, data):
        self.handle_unknown_command(data)
        
    @display_command_constlen(opcode = 0x04, length = 0x02)
    def handle_command_04(self, data):
        self.handle_unknown_command(data)
    
    @display_command_constlen(opcode = 0x05, length = 0x02)
    def handle_command_05(self, data):
        self.handle_unknown_command(data)
    
    @display_command_constlen(opcode = 0x20, length = 0x02)
    def handle_command_20(self, data):
        # RH910 only
        self.handle_unknown_command(data)
        
    @display_command_constlen(opcode = 0x23, length = 0x02)
    def handle_command_23(self, data):
        self.handle_unknown_command(data)

    @display_command_constlen(opcode = 0x24, length = 0x02)
    def handle_command_24(self, data):
        self.handle_unknown_command(data)

    @display_command_constlen(opcode = 0x50, length = 0x05)
    def handle_command_50(self, data):
        self.handle_unknown_command(data)
        
    @display_command_constlen(opcode = 0x53, length = 0x05)
    def handle_command_53(self, data):
        self.handle_unknown_command(data)
    
    @display_command_constlen(opcode = 0x54, length = 0x05)
    def handle_command_54(self, data):
        self.handle_unknown_command(data)

    @display_command_constlen(opcode = 0x56, length = 0x05)
    def handle_command_56(self, data):
        self.handle_unknown_command(data)
    
    @display_command_constlen(opcode = 0x68, length = 0x05)
    def handle_command_68(self, data):
        self.handle_unknown_command(data)
    
    @display_command_constlen(opcode = 0x6a, length = 0x05)
    def handle_command_6a(self, data):
        self.handle_unknown_command(data)
    
    @display_command_constlen(opcode = 0x6b, length = 0x05)
    def handle_command_6b(self, data):
        self.handle_unknown_command(data)
        
    @display_command_constlen(opcode = 0x91, length = 0x0A)
    def handle_command_91(self, data):
        self.handle_unknown_command(data)
        
    def decode_text_or_error(self, byte_text, encoding):
        if type(byte_text) is not bytes:
            byte_text = bytes(byte_text)
        try:
            return byte_text.decode(encoding)
        except:
            self.put_error("Text decoding error")
            return byte_text.decode(encoding, errors='ignore')

        
    @display_command_constlen(opcodes = range(0xE0, 0xE5), length = 0x04)
    def handle_text_command(self, data):
        # Doesn't work sometimes - text length is miscalculated.
        if len(data) == 4:
            length = data[2] & 0b00011111
            self.data_current_command_bytes_remaining = length
            # The command isn't over!
            return True
        else:
            # What col and row are in reality is unknown
            col = data[0] & 0b1111
            row = int(math.log(data[1], 2))
            encoding = data[3]
            encoding_map = {
                0x05: 'latin1',
                0x84: 'utf16-be',
                0x90: 'sjis',
            }
            special_sjis_sequences = {
                0xFD: {
                    **dict((0x65 + x, f"big {x}") for x in range(10))
                },
                0xFA: {
                    0x55: 'big :'
                },
            }
            
            if encoding not in encoding_map:
                self.put_error(f"Unknown encoding: {hex(encoding)}")
                encoding = 0x05
            
            text_bytes = bytes(data[4:])
            temp_bytes = []
            output_text = ""
            first_seq_byte = None
            for byte in text_bytes:
                if first_seq_byte is None:
                    if byte in special_sjis_sequences:
                        first_seq_byte = byte
                        continue
                    temp_bytes.append(byte)
                else:
                    output_text += self.decode_text_or_error(temp_bytes, encoding_map[encoding])
                    temp_bytes = []
                    
                    namespace = special_sjis_sequences[first_seq_byte]
                    if byte not in namespace:
                        sequence_name = f"{hex(first_seq_byte)[2:]}{hex(byte)[2:]}"
                        self.put_error(f"unknown char in {hex(first_seq_byte)} namespace - {hex(byte)}")
                    else:
                        sequence_name = namespace[byte]
                    output_text += f"<{sequence_name}>"
                    first_seq_byte = None
            output_text += self.decode_text_or_error(temp_bytes, encoding_map[encoding])
                
            self.put_command(
                f"Write '{output_text}' ({encoding_map[encoding]}) in ?{row=}, ?{col=}",
                f"Write '{output_text}' in ?{row=}, ?{col=}",
                f"'{output_text}'"
            )
