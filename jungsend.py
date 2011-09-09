#!g:\python26\python.exe

# Logger and controller for Insta RX/TX radio module
# (c)2009 Goran Sander <goran.sander@gmail.com>
# Based on miniterm.py by Chris Liechti <cliechti@gmx.net>

# Input characters are sent directly (only LF -> CR/LF/CRLF translation is
# done), received characters are displayed as is (or escaped trough pythons
# repr, useful for debug purposes)


import sys, os, serial, threading, Queue, array, time

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
    def __init__(self, queue_rx, queue_tx, port, baudrate, parity, rtscts, xonxoff, cmd, echo=False, convert_outgoing=CONVERT_CRLF, repr_mode=0):
        self.serial = serial.Serial(port, baudrate, parity=parity, rtscts=rtscts, xonxoff=xonxoff, timeout=0.7)
        self.echo = echo
        self.repr_mode = repr_mode
        self.convert_outgoing = convert_outgoing
        self.newline = NEWLINE_CONVERISON_MAP[self.convert_outgoing]
        self.dtr_state = rtscts      #True
        self.rts_state = rtscts      #True  
        self.cmd = cmd
        self.break_state = False
        self.__queue_rx = queue_rx
        self.__queue_tx = queue_tx

#        self.dump_port_settings()

    def start(self):
        self.alive = True
        # start serial->console thread
        self.receiver_thread = threading.Thread(target=self.reader)
        self.receiver_thread.setDaemon(1)
        self.receiver_thread.start()
        # enter keyboard handling loop
        self.keyboard_thread = threading.Thread(target=self.keyb)
        self.keyboard_thread.setDaemon(1)
        self.keyboard_thread.start()
        # enter console->serial loop
        self.transmitter_thread = threading.Thread(target=self.writer)
        self.transmitter_thread.setDaemon(1)
        self.transmitter_thread.start()

        # Send INSTA command        
        if self.cmd == 'A':
#            self.serial.write(chr(INQ))
            time.sleep(0.1)
#            telegram = '\x55\x16\x00\x40\x01\x00\x00\x00\x00\x00\x53\xAA'
#            telegram = '\x55\x32\cd\xf1\xfa\x00\x00\x00\x00\x00\xc1\xaa'
#            self.serial.write(telegram)
#            self.serial.flush()
#            sys.stdout.write(telegram)
#            sys.stdout.flush()

    def stop(self):
        self.alive = False

    def join(self, transmit_only=False):
#        self.transmitter_thread.join()
        if not transmit_only:
            self.receiver_thread.join()
        self.keyboard_thread.join()

    def dump_port_settings(self):
        sys.stderr.write("\n--- Settings: %s  %s,%s,%s,%s\n" % (
            self.serial.portstr,
            self.serial.baudrate,
            self.serial.bytesize,
            self.serial.parity,
            self.serial.stopbits,
        ))
        sys.stderr.write('--- RTS %s\n' % (self.rts_state and 'active' or 'inactive'))
        sys.stderr.write('--- DTR %s\n' % (self.dtr_state and 'active' or 'inactive'))
        sys.stderr.write('--- BREAK %s\n' % (self.break_state and 'active' or 'inactive'))
        sys.stderr.write('--- software flow control %s\n' % (self.serial.xonxoff and 'active' or 'inactive'))
        sys.stderr.write('--- hardware flow control %s\n' % (self.serial.rtscts and 'active' or 'inactive'))
        sys.stderr.write('--- data escaping: %s\n' % (REPR_MODES[self.repr_mode],))
        sys.stderr.write('--- linefeed: %s\n' % (LF_MODES[self.convert_outgoing],))

    def reader(self):
        """loop and copy serial->console"""
        while self.alive:
#            print(self.serial.inWaiting())
            if self.serial.inWaiting() > 0:
                data = self.serial.read(1)

                sys.stdout.write("\\x%s " % data.encode('hex'))
                if data == INQ:
#                if ord(data) == 0xFA:
                    try:
                        self.serial.write(ACK)
                        self.serial.write(ACK)
#                        self.serial.write(CRLF)
                        print "ACK"
                    except:
                        print "Serial write exception"
                        raise
                    self.serial.flush()
#                    self.__queue_tx.put(RX_ACK)

                sys.stdout.flush()         

                # Enqueue data
#                self.__queue_rx.put(data)

    def writer(self):
        """loop and copy console->serial until EXITCHARCTER character is
           found. when MENUCHARACTER is found, interpret the next key
           locally.
        """
        print "jjj"
        try:
            while True:
                pass
#                print "k"
#                item = self.__queue_tx.get()
#                print len (item)
#                for character in item:
#                self.serial.write(item)
                # Wait for output buffer to drain.
#                self.serial.flush()
        except:
            print "aaa"
            self.alive = False
            raise
        

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
                elif c == 'q':
                    self.dump_port_settings()
                elif c == 's':
                    if self.echo:
                        sys.stdout.write("Sending INQ\r\n")
#                        sys.stdout.write(c)
#                        sys.stdout.write("\r\n")
                        sys.stdout.flush()
                    self.serial.write(chr(INQ))
                    self.serial.flush()
                    time.sleep(0.01)
 #            telegram = '\x55\x16\x00\x40\x01\x00\x00\x00\x00\x00\x53\xAA'
                    telegram = "\x55\x32\xcd\xf1\xfa\x00\x00\x00\x00\x00\xc1\xaa"
                    self.serial.write(telegram)
                    self.serial.flush()
                    sys.stdout.write("_"+telegram+"_")
                    sys.stdout.flush()
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

    parser.add_option("--parity",
        dest = "parity",
        action = "store",
        help = "set parity, one of [N, E, O, S, M], default=N",
        default = 'N'
    )

    parser.add_option("-e", "--echo",
        dest = "echo",
        action = "store_true",
        help = "enable local echo (default off)",
        default = False
    )

    parser.add_option("--rtscts",
        dest = "rtscts",
        action = "store_true",
        help = "enable RTS/CTS flow control (default off)",
        default = False
    )

    parser.add_option("--xonxoff",
        dest = "xonxoff",
        action = "store_true",
        help = "enable software flow control (default off)",
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

    parser.add_option("--rts",
        dest = "rts_state",
        action = "store",
        type = 'int',
        help = "set initial RTS line state (possible values: 0, 1)",
        default = None
    )

    parser.add_option("--dtr",
        dest = "dtr_state",
        action = "store",
        type = 'int',
        help = "set initial DTR line state (possible values: 0, 1)",
        default = None
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

    options.parity = options.parity.upper()
    if options.parity not in 'NEOSM':
        parser.error("invalid parity")

    if options.cr and options.lf:
        parser.error("only one of --cr or --lf can be specified")

    if options.dtr_state is not None and options.rts_state is not None and options.dtr_state == options.rts_state:
        parser.error('--exit-char can not be the same as --menu-char')

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

    queue_rx = Queue.Queue(2048)
    queue_tx = Queue.Queue(2048)

    try:
        miniterm = Miniterm(
            queue_rx,
            queue_tx,
            port,
            baudrate,
            options.parity,
            rtscts=options.rtscts,
            xonxoff=options.xonxoff,
            cmd=options.cmd,
            echo=options.echo,
            convert_outgoing=convert_outgoing,
            repr_mode=options.repr_mode
        )
    except serial.SerialException:
        sys.stderr.write("could not open port %r\n" % port)
        sys.exit(1)

    if not options.quiet:
        sys.stderr.write('--- Miniterm on %s: %d,%s,%s,%s ---\n' % (
            miniterm.serial.portstr,
            miniterm.serial.baudrate,
            miniterm.serial.bytesize,
            miniterm.serial.parity,
            miniterm.serial.stopbits,
        ))
        sys.stderr.write('--- Quit: %s  |  Menu: %s | Help: %s followed by %s ---\n' % (
            key_description(EXITCHARCTER),
            key_description(MENUCHARACTER),
            key_description(MENUCHARACTER),
            key_description('\x08'),
        ))

    if options.dtr_state is not None:
        if not options.quiet:
            sys.stderr.write('--- forcing DTR %s\n' % (options.dtr_state and 'active' or 'inactive'))
        miniterm.serial.setDTR(options.dtr_state)
        miniterm.dtr_state = options.dtr_state
    if options.rts_state is not None:
        if not options.quiet:
            sys.stderr.write('--- forcing RTS %s\n' % (options.rts_state and 'active' or 'inactive'))
        miniterm.serial.setRTS(options.rts_state)
        miniterm.rts_state = options.rts_state

    miniterm.start()
    miniterm.join(True)
    if not options.quiet:
        sys.stderr.write("\n--- exit ---\n")
    miniterm.join()


if __name__ == '__main__':
    main()
