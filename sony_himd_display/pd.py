from sigrokdecode import Decoder as DecoderArchetype, OUTPUT_ANN
from enum import Enum
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen = True)
class Command:
    opcode: int
    length: int
    handler: Callable[[any, bytes], None]

def display_command_constlen(opcode, length):
    class class_level_decorator:
        def __init__(self, fn):
            self.fn = fn
        def __set_name__(self, owner, name):
            owner.constant_length_commands[opcode] = Command(
                opcode,
                length,
                self.fn
            )
            setattr(owner, name, self.fn)
    return class_level_decorator

class DecodingState(Enum):
    IDLE = 0
    PROLOGUE = 1
    DATA = 2

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
    )
    annotation_rows = (
        ('state', 'States', (0,)),
        ('debug', 'Debug', (1,)),
        ('ascii', 'ASCII', (2,)),
        ('commands', 'Commands', (3,)),
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
        
        
    def switch_state(self, newState, firstOfNew):
        self.put(self.start_of_current_state, firstOfNew, self.out_ann,
                 [0, [f"State: {self.state.name}"]])
        self.start_of_current_state = firstOfNew
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
                self.put(self.start_of_current_state, e, self.out_ann, [1, [f"Checksum mismatch!"]])
            if self.data_bytes_count > 10:
                self.put(s, e, self.out_ann, [1, [f"Debug: Dense packet"]])
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
                     [2, [f"'{chr(value)}'"]])
        
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
                 [3, [*desc]])
    
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
        
    @display_command_constlen(opcode = 0xE0, length = 0x04)
    def handle_command_e0(self, data):
        # Doesn't work sometimes - text length is miscalculated.
        if len(data) == 4:
            length = data[2] & 0b00001111
            self.data_current_command_bytes_remaining = length
            # The command isn't over!
            return True
        else:
            text = ''.join(chr(x) for x in data[4:])
            self.put_command(f"Continue previous message: '{text}'", f"-'{text}'")
        
    # Length = 0x04 required to read the real length parameter
    @display_command_constlen(opcode = 0xE3, length = 0x04)
    def handle_command_e3(self, data):
        if len(data) == 4:
            length = data[2] & 0b00001111
            self.data_current_command_bytes_remaining = length
            # The command isn't over!
            return True
        else:
            text = ''.join(chr(x) for x in data[4:])
            self.put_command(f"Write '{text}'{' (will continue in the next packet)' if text.endswith('-') else ''}", f"'{text}'")
