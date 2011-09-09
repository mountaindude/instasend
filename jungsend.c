/* Simple C program that connects to MySQL Database server*/
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <termios.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>
#include <time.h>
#include <string.h>
#include <stddef.h>


//#define BAUDRATE B9600
#define BAUDRATE B57600
#define _POSIX_SOURCE 1 /* POSIX compliant source */
#define FALSE 0
#define TRUE 1

#define FILE_RAW_MESSAGES    "data_raw.dat"
#define FILE_ENERGY          "data_energy.dat"

int keep_looping = TRUE;

unsigned int device_number; //generic data on package
unsigned long seq;

FILE *file;

void sigfun(int sig)
{
    printf("You have pressed Ctrl-C , aborting!");
    keep_looping = FALSE;
    exit(0);
}


int main(int argc, char *argv[]) {
    {
        int fd,c, res;

        unsigned long previous_seq = 0;

        struct termios oldtio,newtio;
        char buf[255];
        char message[255] = "still empty";
        int message_pointer = 0;
        int message_valid = 1;
        struct tm *local;
        time_t t;
	int message_length = 0;

        if(argc != 2)
        {
            printf("Incorrect number of args: usage arduinomonitor <USB port> e.g. /dev/ttyUSB0\n");
            return(-1);
        }

        printf("Installing signal handler...");
        (void) signal(SIGINT, sigfun);
        printf("done\n");

        printf("connecting to port %s\n", argv[1]);

        fd = open(argv[1], O_RDWR | O_NOCTTY );
        if (fd <0) {perror(argv[1]); exit(-1); }

        tcgetattr(fd,&oldtio); /* save current port settings */

        bzero(&newtio, sizeof(newtio));
        newtio.c_cflag = BAUDRATE | CRTSCTS | CS8 | CLOCAL | CREAD;
        newtio.c_iflag = IGNPAR;
        newtio.c_oflag = 0;

        /* set input mode (non-canonical, no echo,...) */
        newtio.c_lflag = 0;

        newtio.c_cc[VTIME]    = 0;   /* inter-character timer unused */
        newtio.c_cc[VMIN]     = 1;   /* blocking read until 1 chars received */

        tcflush(fd, TCIFLUSH);
        tcsetattr(fd,TCSANOW,&newtio);

        t = time(NULL);
        local = localtime(&t);


        printf("about to start listening\n");
        printf("Current time and date: %s", asctime(local));

        int jj;
        while (keep_looping) {       /* loop for input */
            res = read(fd,buf,255);   /* returns after 1 chars have been input */

            int value = 0;
            for ( jj=0 ; jj<res ; jj=jj+1)
            {
//                printf("[%i] - %x\n", jj, buf[jj]);
            }


            if ((buf[0] == 'O')) // and (buf[1] == "K")) == true)
            {
                message[message_pointer] = 0;
                message_pointer = 0;
                //PRINT MESSAGE
                message_valid = 0;
            }

            for ( jj=0 ; jj<res ; jj=jj+1)
            {
                if (buf[jj] == 'E')
                {
                    //PRINT MESSAGE
                    message[message_pointer] = 0;
                    message_pointer++;
                    // printf("B: full message: %s\n", message);
                    message_valid = 0;

                    //process it
                    t = time(NULL);
                    local = localtime(&t);

                    //print to raw data file
                    file = fopen(FILE_RAW_MESSAGES, "a+");
                    fprintf(file, "%s @ %s", message, asctime(local));
                    fclose(file);

                    char *lixo, *devl, *devm, *s0, *s1, *s2, *s3;

                    lixo = strtok (message, " "); //OK
                    lixo = strtok (NULL, " "); //14  - size of package in bytes
                    lixo = strtok (NULL, " "); //1   - rf12 header
                    lixo = strtok (NULL, " "); //1   - house number lsb, set by me in the JeeNode
                    lixo = strtok (NULL, " "); //0   - house number msb
                    devl = strtok (NULL, " "); //1   - device number lsb, set by me in the JeeNode lsb
                    devm = strtok (NULL, " "); //0   - device number msb
                    // 1 - Energy meter
                    // 2 - 
                    // 3 -
                    // 4 -

                    device_number = atoi(devl)+atoi(devm)*256;
                    printf("device number: %i\n", device_number);


                    switch (device_number) {
                        case 1: 
							printf("Electricity energy meter\n");

                            char *flsb, *fmsb, *w0, *w1, *w2, *w3, *kwh0, *kwh1, *kwh2, *kwh3;

                            //specific data for weather station
                            // int freq;
							// long Wtot, kWhtot;
							float freq, Wtot, kWhtot;



                            seq = atoi(s0) + atoi(s1)*256 + atoi(s2)*256*256 + atoi(s3)*256*256*256;

                            if (seq != previous_seq)
                            {
                                previous_seq = seq;

                                freq        = ((float) (atoi(flsb)+atoi(fmsb)*256)) / 10;

								Wtot = ((float) (atoi(w0) + atoi(w1)*256 + atoi(w2)*256*256 + atoi(w3)*256*256*256)) / 10;
								kWhtot = ((float) (atoi(kwh0) + atoi(kwh1)*256 + atoi(kwh2)*256*256 + atoi(kwh3)*256*256*256)) / 10;
                                printf ("seq nr %lu; freqency: %0.1f; effect: %0.1f; energy: %0.1f @ %s\n\n", seq, freq, Wtot, kWhtot, asctime(local));
                            }
							break;
                        default: printf("Unknown message %s\n", message);
                            break;
                    }
                }
                else
                {
                    message[message_pointer] = buf[jj];
                    message_pointer++;
                }
            }           

        }
        tcsetattr(fd,TCSANOW,&oldtio);
        return (0);
    }
}

