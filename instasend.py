# Sending commands to Insta RX/TX radio module
# Goran Sander <goran.sander@gmail.com>
# Based on miniterm.py by Chris Liechti <cliechti@gmx.net>

#  python instasend.py --port /dev/ttyUSB2 -c a4on


import sys, os, serial, threading, array, time

EXITCHARCTER = '\x1d'   # GS/CTRL+]
MENUCHARACTER = '\x14'  # Menu: CTRL+T


def key_description(character):
    """generate a readable description for a key"""
    ascii_code = ord(character)
    if ascii_code < 32:
        return 'Ctrl+%c' % (ord('@') + ascii_code)
    else:
        return repr(character)

# help text, starts with blank line! it's a function so that the current values
# for the shortcut keys is used and not the value at program start
def get_help_text():
    return """
--- pySerial - miniterm - help
---
--- %(exit)-8s Exit program
--- %(menu)-8s Menu escape key, followed by:
--- Menu keys:
---       %(itself)-8s Send the menu character itself to remote
---       %(exchar)-8s Send the exit character to remote
---       %(info)-8s Show info
---       %(upload)-8s Upload file (prompt will be shown)
--- Toggles:
---       %(rts)s  RTS          %(echo)s  local echo
---       %(dtr)s  DTR          %(break)s  BREAK
---       %(lfm)s  line feed    %(repr)s  Cycle repr mode
---
--- Port settings (%(menu)s followed by the following):
--- 7 8           set data bits
--- n e o s m     change parity (None, Even, Odd, Space, Mark)
--- 1 2 3         set stop bits (1, 2, 1.5)
--- b             change baud rate
--- x X           disable/enable software flow control
--- r R           disable/enable hardware flow control
""" % {
    'exit': key_description(EXITCHARCTER),
    'menu': key_description(MENUCHARACTER),
    'rts': key_description('\x12'),
    'repr': key_description('\x01'),
    'dtr': key_description('\x04'),
    'lfm': key_description('\x0c'),
    'break': key_description('\x02'),
    'echo': key_description('\x05'),
    'info': key_description('\x09'),
    'upload': key_description('\x15'),
    'itself': key_description(MENUCHARACTER),
    'exchar': key_description(EXITCHARCTER),
}

# first choose a platform dependant way to read single characters from the console
global console

if os.name == 'nt':
    import msvcrt
    class Console:
        def __init__(self):
            pass

        def setup(self):
            pass    # Do nothing for 'nt'

        def cleanup(self):
            pass    # Do nothing for 'nt'

        def getkey(self):
            while 1:
                z = msvcrt.getch()
                if z == '\0' or z == '\xe0':    #functions keys
                    msvcrt.getch()
                else:
                    if z == '\r':
                        return '\n'
                    return z

    console = Console()

elif os.name == 'posix':
    import termios, sys, os
    class Console:
        def __init__(self):
            self.fd = sys.stdin.fileno()

        def setup(self):
            self.old = termios.tcgetattr(self.fd)
            new = termios.tcgetattr(self.fd)
            new[3] = new[3] & ~termios.ICANON & ~termios.ECHO & ~termios.ISIG
            new[6][termios.VMIN] = 1
            new[6][termios.VTIME] = 0
            termios.tcsetattr(self.fd, termios.TCSANOW, new)
            #s = ''    # We'll save the characters typed and add them to the pool.

        def getkey(self):
            c = os.read(self.fd, 1)
            return c

        def cleanup(self):
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old)

    console = Console()

    def cleanup_console():
        console.cleanup()

    console.setup()
    sys.exitfunc = cleanup_console      #terminal modes have to be restored on exit...

else:
    raise "Sorry no implementation for your platform (%s) available." % sys.platform


CONVERT_CRLF = 2
CONVERT_CR   = 1
CONVERT_LF   = 0
NEWLINE_CONVERISON_MAP = ('\n', '\r', '\r\n')
LF_MODES = ('LF', 'CR', 'CR/LF')

REPR_MODES = ('raw', 'some control', 'all control', 'hex')

INQ = 0xfa
ACK = 0x05
CRLF = '\r\n' 

class Miniterm:
    def __init__(self, port, baudrate, cmd, echo=False, convert_outgoing=CONVERT_CRLF, repr_mode=0):
        self.serial = serial.Serial(port, baudrate, parity='N', rtscts=False, xonxoff=False, timeout=0.7)

        self.echo = echo
        self.repr_mode = repr_mode
        self.convert_outgoing = convert_outgoing
        self.newline = NEWLINE_CONVERISON_MAP[self.convert_outgoing]
        self.cmd = cmd
        self.break_state = False


    def start(self):
        self.alive = True

        # enter keyboard handling loop
        self.keyboard_thread = threading.Thread(target=self.keyb)
        self.keyboard_thread.setDaemon(1)
        self.keyboard_thread.start()

        # Send INSTA command        
        cmd = self.cmd.lower()
        if self.echo:
            sys.stdout.write("cmd:%s\n" % cmd)
            sys.stdout.write("cmd len:%d\n" % len(cmd))

        telegram = '\x55\x16\x00'
        device = 0;
        
        # add group #
        if cmd[0] == 'a':
            device = 0x00
        elif cmd[0] == 'b':
            device = 0x08
        elif cmd[0] == 'c':
            device = 0x10

        # Add channel #
        channel = int(cmd[1])
  #      sys.stdout.write("channel:%d\n" % channel)
        device = device | (channel - 1)

        # Add on/off
        if cmd[2:4] == "on":
            device = device | 0x40
        elif cmd [2:5] == "off":
            device = device | 0x80

  #      sys.stdout.write("device:%x\n" % device)
           
            
        telegram = telegram + chr(device) + '\x01\x00\x00\x00\x00\x00'
        
        sum = 0
        for i in range(0, len(telegram)):
            sum = sum + ord(telegram[i])
#            sys.stdout.write("i=%d, %x\n" % (i, ord(telegram[i])))
            
 #       sys.stdout.write("sum is:%x\n" % sum)
        sum = sum & 0xff
 #       sys.stdout.write("sum2 is:%x\n" % sum)
        crc = 2**8 - sum
 #       sys.stdout.write("CRC is:%x\n" % crc)

        telegram = telegram + chr(crc) + '\xaa'

        
        if self.echo:
            sys.stdout.write("INQ\n")
        self.serial.write(chr(INQ))
        while self.serial.inWaiting() == 0:
            pass
            
        if self.serial.inWaiting() > 0:
            data = self.serial.read(1)

#            sys.stdout.write("\\x%s " % data.encode('hex'))
            if data == chr(ACK):
                try:
                    if self.echo:
                        sys.stdout.write("ACK\n")
#                    telegram = '\x55\x16\x00\x42\x01\x00\x00\x00\x00\x00\x52\xaa'
# version query
#                    telegram = "\x55\x32\xcd\xf1\xfa\x00\x00\x00\x00\x00\xc1\xaa"
                    self.serial.write(telegram)
                    self.serial.flush()

                    if self.echo:
                        for i in range(0, len(telegram)):
                            sys.stdout.write("i=%d, \\x%x\n" % (i, ord(telegram[i])))
                    sys.stdout.flush()

#                    while self.serial.inWaiting() == 0:
#                        pass

#                    sys.stdout.write("Response:")
#                    while self.serial.inWaiting() > 0:
#                        data = self.serial.read(1)
#                        sys.stdout.write("\\x%s " % data.encode('hex'))
#                    sys.stdout.write("\n\n")
#                    if data == chr(INQ):
#                        sys.stdout.write("Received INQ\n")
#                        self.serial.write(chr(ACK))
#                        self.serial.flush()
#                        sys.stdout.write("Sending ACK\n")
                        
#                        i = 1
#                        while self.serial.inWaiting() == 0:
#                            pass
#                        while self.serial.inWaiting() > 0:
#                            data = self.serial.read(1)
#                            sys.stdout.write("%d:\\x%s " % (i, data.encode('hex')))
#                            i=i+1
#                            sys.stdout.write("\n")
#                        sys.stdout.write("\n")

                except:
                    print "Serial write exception"
                    raise
    
        
        
        
    def stop(self):
        self.alive = False

    def join(self, transmit_only=False):
        pass
#        self.transmitter_thread.join()
#        if not transmit_only:
#            self.receiver_thread.join()
#        self.keyboard_thread.join()


    def keyb(self):
        """loop and copy console->serial until EXITCHARCTER character is
           found. when MENUCHARACTER is found, interpret the next key
           locally.
        """
        try:
            while self.alive:
#                print "bbb" 
                try:
                    c = console.getkey()
                except KeyboardInterrupt:
                    c = '\x03'

                if c == EXITCHARCTER: 
                    self.stop()
                    break                                   # exit app
                elif c == 's':
#                    if self.echo:
                    sys.stdout.write("Sending INQ\r\n")
                elif c == '\n':
                    self.serial.write(self.newline)         # send newline character(s)
                    if self.echo:
                        sys.stdout.write(c)                 # local echo is a real newline in any case
#                        sys.stdout.flush()
                else:
                    self.serial.write(c)                    # send character
                    if self.echo:
                        sys.stdout.write(c)
                        sys.stdout.flush()
        except:
            self.alive = False
            raise
      


def main():
    import optparse

    parser = optparse.OptionParser(
        usage = "%prog [options] [port [baudrate]]",
        description = "Miniterm - A simple terminal program for the serial port."
    )

    parser.add_option("-c", "--cmd",
        dest = "cmd",
        help ="command to send to INSTA transciever",
        default = ""
    )

    parser.add_option("-p", "--port",
        dest = "port",
        help = "port, a number (default 0) or a device name (deprecated option)",
        default = "COM2"
    )

    parser.add_option("-b", "--baud",
        dest = "baudrate",
        action = "store",
        type = 'int',
        help = "set baud rate, default %default",
        default = 9600
    )

    parser.add_option("-e", "--echo",
        dest = "echo",
        action = "store_true",
        help = "enable local echo (default off)",
        default = False
    )

    parser.add_option("--cr",
        dest = "cr",
        action = "store_true",
        help = "do not send CR+LF, send CR only",
        default = False
    )

    parser.add_option("--lf",
        dest = "lf",
        action = "store_true",
        help = "do not send CR+LF, send LF only",
        default = False
    )

    parser.add_option("-D", "--debug",
        dest = "repr_mode",
        action = "count",
        help = """debug received data (escape non-printable chars)
--debug can be given multiple times:
0: just print what is received
1: escape non-printable characters, do newlines as unusual
2: escape non-printable characters, newlines too
3: hex dump everything""",
        default = 0 
    )

    parser.add_option("-q", "--quiet",
        dest = "quiet",
        action = "store_true",
        help = "suppress non error messages",
        default = False
    )

    parser.add_option("--exit-char",
        dest = "exit_char",
       action = "store",
        type = 'int',
        help = "ASCII code of special character that is used to exit the application",
        default = 0x20              # Default 0x1d
    )

    parser.add_option("--menu-char",
        dest = "menu_char",
        action = "store",
        type = 'int',
        help = "ASCII code of special character that is used to control miniterm (menu)",
        default = 0x14
    )

    (options, args) = parser.parse_args()

    if options.cr and options.lf:
        parser.error("only one of --cr or --lf can be specified")

    if options.cmd is "":
        parser.error('Must provide command')

    global EXITCHARCTER, MENUCHARACTER
    EXITCHARCTER = chr(options.exit_char)
    MENUCHARACTER = chr(options.menu_char)

    port = options.port
    baudrate = options.baudrate
    if args:
        if options.port is not None:
            parser.error("no arguments are allowed, options only when --port is given")
        port = args.pop(0)
        if args:
            try:
                baudrate = int(args[0])
            except ValueError:
                parser.error("baud rate must be a number, not %r" % args[0])
            args.pop(0)
        if args:
            parser.error("too many arguments")
    else:
        if port is None: port = 0

    convert_outgoing = CONVERT_CRLF
    if options.cr:
        convert_outgoing = CONVERT_CR
    elif options.lf:
        convert_outgoing = CONVERT_LF

    try:
        miniterm = Miniterm(
            port,
            baudrate,
            cmd=options.cmd,
            echo=options.echo,
            convert_outgoing=convert_outgoing,
            repr_mode=options.repr_mode
        )
    except serial.SerialException:
        sys.stderr.write("could not open port %r\n" % port)
        sys.exit(1)

    if not options.quiet:
        sys.stderr.write('--- InstaSend on %s: %d,%s,%s,%s ---\n' % (
            miniterm.serial.portstr,
            miniterm.serial.baudrate,
            miniterm.serial.bytesize,
            miniterm.serial.parity,
            miniterm.serial.stopbits,
        ))
#        sys.stderr.write('--- Quit: %s  |  Menu: %s | Help: %s followed by %s ---\n' % (
#            key_description(EXITCHARCTER),
#            key_description(MENUCHARACTER),
#            key_description(MENUCHARACTER),
#            key_description('\x08'),
#        ))

    miniterm.start()
    miniterm.join(True)
    if not options.quiet:
        sys.stderr.write("\n--- exit ---\n")
    miniterm.join()
    


if __name__ == '__main__':
    main()
