#!/usr/bin/python

##################################################
# AFEDRI Lightweight recording
# Title: afedrec.py
# Author: k3it
# Generated: Fri Aug  24 2012
# Version: 2.1
##################################################

from socket import *
from optparse import OptionParser
import wave
import sys
import struct
import time
import datetime
import threading
import Queue
import string
import math


class afedri(object):
        """
        class definition for the Afedri SDR-NET
        """
        def __init__(self,sdr_address="0.0.0.0", sdr_port=50000):
                if sdr_address == "0.0.0.0":
                        __sdr_address,self.sdr_port = self.__discover_afedri()
                else:
                        __sdr_address = sdr_address
                        self.sdr_port = sdr_port
                        
                self.s = socket(AF_INET, SOCK_STREAM)
                try:
                        self.s.connect((__sdr_address,self.sdr_port))
                        #print "Established control connection with AFEDRI"
                except:
                        print "Error connecting to SDR"
                        sys.exit()

        def set_center_freq(self,target_freq):
                __next_freq = target_freq
                __next_freq = struct.pack("<q",__next_freq)
                __set_freq_cmd = "\x0a\x00\x20\x00\x00" + __next_freq[:5]
                self.s.send(__set_freq_cmd)
                __data = self.s.recv(10)
                __freq = __data[5:] + "\0" * 3
                __freq = struct.unpack("<q",__freq)[0]
                return  __freq


        def set_samp_rate(self,target_samprate):
                __samp_rate = target_samprate
                __samp_rate = struct.pack("<q",__samp_rate)
                __set_rate_cmd = "\x09\x00\xB8\x00\x00" + __samp_rate[:4]
                self.s.send(__set_rate_cmd)
                __data = self.s.recv(9)
                __samp = __data[5:] + "\0" * 4
                __samp = struct.unpack("<q",__samp)[0]
                return  __samp


        def set_gain(self,target_gain):
                __gain = target_gain
                # special afedri calculation for the gain byte
                __gain = ((__gain+10)/3 << 3) + 1
                __set_gain_cmd = "\x06\x00\x38\x00\x00" + struct.pack("B",__gain)
                self.s.send(__set_gain_cmd)
                __data = self.s.recv(6)
                __rf_gain = -10 + 3 * (struct.unpack("B",__data[5:6])[0]>>3)
                return __rf_gain

        def get_gain(self):
                """
                NOT IMPLEMENTED IN AFEDRI?. DON'T USE
                """
                __get_gain_cmd = "\x05\x20\x38\x00\x00"
                self.s.send(__get_gain_cmd)
                __data = self.s.recv(6)
                __rf_gain = -10 + 3 * (struct.unpack("B",__data[5:])[0]>>3)
                return __rf_gain

        def get_fe_clock(self):
                __get_lword_cmd = "\x09\xE0\x02\x55\x00\x00\x00\x00\x00"
                __get_hword_cmd = "\x09\xE0\x02\x55\x01\x00\x00\x00\x00"
                self.s.send(__get_lword_cmd)
                __data_l = self.s.recv(9)
                self.s.send(__get_hword_cmd)
                __data_h = self.s.recv(9)
                __fe_clock = struct.unpack("<H",__data_l[4:6])[0] + (struct.unpack("<H",__data_h[4:6])[0]<<16)
                return __fe_clock

        def start_capture(self):
                #start 16-bit contiguous capture, complex numbers
                __start_cmd="\x08\x00\x18\x00\x80\x02\x00\x00"
                self.s.send(__start_cmd)
                __data = self.s.recv(8)
                return __data

        def stop_capture(self):
                __stop_cmd="\x08\x00\x18\x00\x00\x01\x00\x00"
                self.s.send(__stop_cmd)
                __data = self.s.recv(8)
                return __data

        def __discover_afedri(self):
                # attempt to find AFEDRI SDR on the network
                # using AE4JY Simple Network Discovery Protocol
                
                __DISCOVER_SERVER_PORT=48321      # PC client Tx port, SDR Server Rx Port 
                __DISCOVER_CLIENT_PORT=48322      # PC client Rx port, SDR Server Tx Port 

                __data="\x38\x00\x5a\xa5"         # magic discovery packet
                __data=__data.ljust(56,"\x00")    # pad with zeroes
                
                self.s = socket(AF_INET, SOCK_DGRAM)
                self.s.bind(('', 0))
                self.s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
                
                self.sin = socket(AF_INET, SOCK_DGRAM)
                self.sin.bind(('', __DISCOVER_CLIENT_PORT))

                #exception if no response to broadcast
                self.sin.settimeout(1)


                self.s.sendto(__data, ('<broadcast>',__DISCOVER_SERVER_PORT))
                try:
                        __msg=self.sin.recv(256,0)
                        __devname=__msg[5:20]
                        __sn=__msg[21:36]
                        __ip=inet_ntoa(__msg[40:36:-1])
                        __port=struct.unpack("<H",__msg[53:55])[0]
                        self.s.close()
                        self.sin.close()
                        print "found ", __devname, __sn, __ip, __port
                        return (__ip,__port)
                except timeout:
                        print "No response from AFEDRI on the LAN"
                        sys.exit()
               

        def __del__(self):
                self.stop_capture()
                self.s.close()



class wave_file:
        """
        class definition for the WAV file object
        """
        def __init__(self,duration,samp_rate,LO,BASENAME):
                #construct auxi chunk
                #Chunk id
                __auxi = "auxi"
                #fixed auxi chunk size 164 bytes
                __auxi += struct.pack("<I",164)
                #starttime/endtime
                self.create_time=time.time()
                now=datetime.datetime.utcnow()
                finish=now + datetime.timedelta(seconds=duration)

                weekday = (now.weekday()+2)%7
                if weekday == 0:
                        weekday=7

                finish_weekday=(finish.weekday()+2)%7
                if finish_weekday == 0:
                        finish_weekday=7

                __auxi += struct.pack("<8H",now.year,now.month,weekday,now.day,
                                    now.hour,now.minute,now.second,int(now.microsecond/1000))
                __auxi += struct.pack("<8H",finish.year,finish.month,finish_weekday,finish.day,
                                    finish.hour,finish.minute,finish.second,int(finish.microsecond/1000))
                #LO
                __auxi += struct.pack("<I",LO)
                #unused fields
                __auxi += struct.pack("<8I",0,0,0,0,0,0,0,0)
                #next filename, leave blank for now
                __auxi += string.ljust('',96,'\x00')

                self.wavfile = BASENAME + "_"
                self.wavfile += str(now.year)
                self.wavfile += str(now.month).zfill(2)
                self.wavfile += str(now.day).zfill(2)
                self.wavfile += "_"
                self.wavfile += str(now.hour).zfill(2)
                self.wavfile += str(now.minute).zfill(2)
                self.wavfile += str(now.second).zfill(2)
                self.wavfile += "Z_"
                self.wavfile += str(int(LO/1000))
                self.wavfile += "kHz_RF.wav"

                # get ready to write wave file
                try:
                        self.f = open(self.wavfile,'wb')
                        self.w = wave.open(self.f,"wb")
                except:
                        print "unable to open WAV file for writing"
                        sys.exit()

        

                #16 bit complex samples 
                self.w.setparams((2, 2, samp_rate, 1, 'NONE', 'not compressed'))
                self.w.close()
                #write auxi chank and get ready to receive samples
                self.f.seek(36,0)
                self.f.write(__auxi)
                self.f.write("data\x00\x00\x00\x00")
                # return wav file name if all is OK
                

        def write(self,data):
                self.f.write(data)
                return self.f.tell()

        def close_wave(self,nextfilename=''):
                __nextfilename = string.ljust(nextfilename,96,'\x00')
                #update data chunk counter
                __datachunksize=struct.pack("<I",self.f.tell()-216)
                __riffchunksize=struct.pack("<I",self.f.tell()-8)

                # calculate the "lossless" capture size
                data_size_target = (time.time()-self.create_time)*samp_rate*4
                data_size_real = self.f.tell()-216
                framescaptured = 100*data_size_real/data_size_target

                # update overall file length header
                self.f.seek(4,0)
                self.f.write(__riffchunksize)
                # update next filename for split files (HDSDR only?)
                self.f.seek(112,0)
                self.f.write(__nextfilename)
                # update wav data chunk length header
                self.f.seek(212,0)
                self.f.write(__datachunksize)
                self.f.close()

                #return percentage of captured udp packets
                return int(framescaptured)

#        def __del__(self):
#                self.close_wave('')
        


usage = "usage: %prog [OPTION]... BASE_FILE_NAME"
parser = OptionParser(usage=usage)
parser.add_option("-s", "--sample-rate", type="int", default=192231,
                  help="sampling rate in Hz [default=%default]")
parser.add_option("-c", "--lo-freq", type="int", default=10000000, 
                  help="SDR center frequency [default=%default]")
parser.add_option("-t", "--duration", type="int", default=60,
                  help="duration of the recording in seconds [default=%default]")
parser.add_option("-W", "--file-size", type="int", default=1000,
                  help="WAV file split size in MB [default=%default]")
parser.add_option("-g", "--gain", type="int",
                  help="Set VGA gain in dB")
parser.add_option("-i", "--ip", default="0.0.0.0",
                  help="IP address of the Afedri")
parser.add_option("-p", "--port", type="int", default=5000 ,
                  help="Port number of the Afedri")


(options,args) = parser.parse_args()
if len(args) == 0:
        parser.error("Specify the WAV file prefix(basename)")
elif len(args) > 1:
        parser.error("Too many arguments.. use -h for help")

BASENAME = args[0]
                     
samp_rate=options.sample_rate
LO=options.lo_freq
duration=options.duration
MAX_SIZE=options.file_size*1048576

print "AFEDRI RF Recorder v2.1b, 2012 k3it\n"
#create an afedri object
a=afedri(sdr_address=options.ip, sdr_port=options.port)

# verify and correct sampling rate according to the main clock speed
# Alex Trushkin code 4z5lv:
fe_main_clock_freq = a.get_fe_clock()
tmp_div = fe_main_clock_freq / (4 * samp_rate)
floor_div = math.floor(tmp_div)
if (tmp_div - floor_div >= 0.5):
        floor_div += 1
if floor_div < 15:
        floor_div = 15
        #print "Warning: Max supported sampling rate is", math.floor(fe_main_clock_freq / (4 * floor_div))
elif floor_div > 625:
        floor_div = 625
        #print "Warning: Min supported sampling rate is", math.floor(fe_main_clock_freq / (4 * floor_div))
                                                                    
dSR =  fe_main_clock_freq / (4 * floor_div)
floor_SR = math.floor(dSR)
if (dSR - floor_SR >= 0.5):
        floor_SR += 1
if floor_SR != samp_rate:
        print "Warning: invalid sample rate selected for the AFEDRI main clock (", fe_main_clock_freq, "Hz )"
        print "         setting to the next valid value", samp_rate, " => ", floor_SR
        samp_rate = floor_SR
        
if options.gain:
        if 35 < options.gain or options.gain < -10:
                parser.error ("gain must be between -10 and +35db")
        else:
                gain = a.set_gain(options.gain)
                if gain != options.gain:
                        print "Warrning: invalid VGA gain selected, setting to the next valid value"
                print "Setting Gain to:", gain, "db"


#store port number for UDP stream
MYPORT = a.sdr_port

print "Setting LO to:", a.set_center_freq(LO)
print "Setting Sampling Rate to:", a.set_samp_rate(samp_rate)

        
#write to disk in a separate worker thread
def writer():
        global f
        bytes_written=216
        while True:
                #open a new file if we reached max size
                if bytes_written >= MAX_SIZE:
                        new_f=wave_file(duration-time.time()+start_time,samp_rate,LO,BASENAME)
                        if f.close_wave(new_f.wavfile) < 90:
                                print "WARNING: Looks like we have dropped over 10% of samples.." 
                        del f
                        f=new_f
                        print "\nstarting a new file: ", f.wavfile
                __data = ''.join(q.get())
                bytes_written=f.write(__data)
                sys.stdout.write('.')
                q.task_done()
        
 
                

# Receive UDP packets transmitted by a broadcasting service

s = socket(AF_INET, SOCK_DGRAM)
try:
        s.bind(('', MYPORT))
except:
        print "Error connecting to the UDP stream."

q = Queue.Queue()


#start writer thread


t = threading.Thread(target=writer)
t.daemon = True
t.start()

#sys.stdout.write('starting capture:...')
a.start_capture()
start_time=time.time()

#create the first wave file
f=wave_file(duration,samp_rate,LO,BASENAME)
print "Wrting to: ", f.wavfile

while (time.time()-start_time < duration):
        data=[]
        #process 1k packets at a time to use queue more efficiently
        for i in range(1024):
                data.append(s.recv(1028)[4:])
        q.put(data)

a.stop_capture()

#wait till the entire queue is drained to disk
q.join()
if f.close_wave('') < 90:
        print "WARNING: Looks like we have dropped over 10% of samples" 


s.close()

sys.exit()











