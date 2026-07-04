#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# DHT22 Class Library with lgpio
#
# Modification of Zoltan Szarvas's library with RPI.GPIO.
# https://github.com/szazo/DHT11_Python.git
#
# This class is a refactoring of a library 
# originally written by Zoltan Szarvas using RPi.GPIO,
# converted to use the lgpio library.
#
# To install lgpio,
# (venv) $ pip install lgpio # Recommended
# or
# $ sudo apt-get install python3-lgpio # not recommended
# .
#
# Nov. 19, 2025
# Michiharu Takemoto (takemoto.development@gmail.com)
#
#
# MIT License
# 
# Copyright (c) 2025 Michiharu Takemoto <takemoto.development@gmail.com>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# 


import time
import lgpio
try:
    from .logger_setup import setup_logger
except ImportError:
    from logger_setup import setup_logger

logger = setup_logger(__name__)

class DHT22MissingDataError(Exception):
    pass


class DHT22CRCError(Exception):
    pass


class DHT22:
    'DHT22 sensor reader class for Raspberry Pi using lgpio'

    def __init__(self, gpio):
        self.__gpio = gpio
        self.__h = lgpio.gpiochip_open(0)  # Open gpiochip0
        logger.info("Opened gpiochip0 for DHT22 gpio=%s", gpio)

    def read(self):
        # Set pin as output
        lgpio.gpio_claim_output(self.__h, self.__gpio)
        # send initial high
        self.__send_and_sleep(1, 0.58)  # HIGH

        # pull down to low
        self.__send_and_sleep(0, 0.02)  # LOW

        # change to input using pull up
        #lgpio.gpio_claim_input(self.__h, self.__gpio, lgpio.LGPIO_PULL_UP)
        lgpio.gpio_claim_input(self.__h, self.__gpio, lgpio.SET_PULL_UP)

        # collect data into an array
        data = self.__collect_input()

        # parse lengths of all data pull up periods
        pull_up_lengths = self.__parse_data_pull_up_lengths(data)

        # if bit count mismatch, return error (4 byte data + 1 byte checksum)
        if len(pull_up_lengths) != 40:
            logger.warning("DHT22 missing data gpio=%s bit_count=%s", self.__gpio, len(pull_up_lengths))
            raise DHT22MissingDataError

        # calculate bits from lengths of the pull up periods
        bits = self.__calculate_bits(pull_up_lengths)

        # we have the bits, calculate bytes
        the_bytes = self.__bits_to_bytes(bits)

        # calculate checksum and check (mask to 8-bit)
        checksum = self.__calculate_checksum(the_bytes)
        if the_bytes[4] != checksum:
            logger.warning(
                "DHT22 checksum mismatch gpio=%s expected=%s actual=%s bytes=%s",
                self.__gpio,
                checksum,
                the_bytes[4],
                the_bytes,
            )
            raise DHT22CRCError

        # ok, we have valid data

        # DHT22 data format (5 bytes):
        # the_bytes[0]: humidity high byte
        # the_bytes[1]: humidity low byte
        # the_bytes[2]: temperature high byte
        # the_bytes[3]: temperature low byte
        # the_bytes[4]: checksum

        # Combine humidity and temperature as 16-bit values
        humidity_raw = (the_bytes[0] << 8) + the_bytes[1]
        humidity = float(humidity_raw) / 10.0

        temp_raw = (the_bytes[2] << 8) + the_bytes[3]
        # temperature sign: highest bit set indicates negative
        if (temp_raw & 0x8000) != 0:
            temperature = - float(temp_raw & 0x7FFF) / 10.0
        else:
            temperature = float(temp_raw) / 10.0

        return temperature, humidity, checksum
        
    def __send_and_sleep(self, output, sleep):
        lgpio.gpio_write(self.__h, self.__gpio, output)
        time.sleep(sleep)


    def __collect_input(self):
        # collect the data while unchanged found
        unchanged_count = 0

        # this is used to determine where is the end of the data
        max_unchanged_count = 100

        last = -1
        data = []
        while True:
            current = lgpio.gpio_read(self.__h, self.__gpio)
            data.append(current)
            if last != current:
                unchanged_count = 0
                last = current
            else:
                unchanged_count += 1
                if unchanged_count > max_unchanged_count:
                    break

        return data
    
    def __parse_data_pull_up_lengths(self, data):
        STATE_INIT_PULL_DOWN = 1
        STATE_INIT_PULL_UP = 2
        STATE_DATA_FIRST_PULL_DOWN = 3
        STATE_DATA_PULL_UP = 4
        STATE_DATA_PULL_DOWN = 5

        state = STATE_INIT_PULL_DOWN

        lengths = [] # will contain the lengths of data pull up periods
        current_length = 0 # will contain the length of the previous period

        for i in range(len(data)):

            current = data[i]
            current_length += 1

            if state == STATE_INIT_PULL_DOWN:
                if current == 0:
                    # ok, we got the initial pull down
                    state = STATE_INIT_PULL_UP
                    continue
                else:
                    continue
            if state == STATE_INIT_PULL_UP:
                if current == 1:
                    # ok, we got the initial pull up
                    state = STATE_DATA_FIRST_PULL_DOWN
                    continue
                else:
                    continue
            if state == STATE_DATA_FIRST_PULL_DOWN:
                if current == 0:
                    # we have the initial pull down, the next will be the data pull up
                    state = STATE_DATA_PULL_UP
                    continue
                else:
                    continue
            if state == STATE_DATA_PULL_UP:
                if current == 1:
                    # data pulled up, the length of this pull up will determine whether it is 0 or 1
                    current_length = 0
                    state = STATE_DATA_PULL_DOWN
                    continue
                else:
                    continue
            if state == STATE_DATA_PULL_DOWN:
                if current == 0:
                    # pulled down, we store the length of the previous pull up period
                    lengths.append(current_length)
                    state = STATE_DATA_PULL_UP
                    continue
                else:
                    continue

        return lengths

    def __calculate_bits(self, pull_up_lengths):
        # find shortest and longest period
        shortest_pull_up = 1000
        longest_pull_up = 0

        for i in range(0, len(pull_up_lengths)):
            length = pull_up_lengths[i]
            if length < shortest_pull_up:
                shortest_pull_up = length
            if length > longest_pull_up:
                longest_pull_up = length

        # use the halfway to determine whether the period it is long or short
        halfway = shortest_pull_up + (longest_pull_up - shortest_pull_up) / 2
        bits = []

        for i in range(0, len(pull_up_lengths)):
            bit = False
            if pull_up_lengths[i] > halfway:
                bit = True
            bits.append(bit)

        return bits
    
    def __bits_to_bytes(self, bit_list0):
        bytes = []
        length = len(bit_list0)
        byte_d = 0

        for i in range(0, length):
            byte_d = byte_d << 1
            
            if (1 == bit_list0[i]):
                byte_d = byte_d | 1
            else:
                byte_d = byte_d | 0

            if ((i + 1) % 8 == 0):
                bytes.append(byte_d)
                byte_d = 0

        return bytes

    def __calculate_checksum(self, bytes0):
        checksum = (bytes0[0] & 0xff) + (bytes0[1] & 0xff) + (bytes0[2] & 0xff) + (bytes0[3] & 0xff)
        return checksum & 0xFF
    
    def close(self):
        lgpio.gpiochip_close(self.__h)  # Close gpiochip0
        logger.info("Closed gpiochip0 for DHT22 gpio=%s", self.__gpio)
 

if __name__ == '__main__':
    # read data using gpio 26
    dht22_instance = DHT22(gpio=26)
    logger.info("DHT22 sensor initialized on GPIO26")

    try:
         while True:
            try:
                tempe, hum, check = dht22_instance.read()
                logger.info("DHT22 read success temperature=%.1f humidity=%.1f", tempe, hum)
            except DHT22CRCError:
                logger.warning("DHT22CRCError during standalone read")
            except DHT22MissingDataError:
                logger.warning("DHT22MissingDataError during standalone read")
            except Exception:
                logger.exception("Unexpected DHT22 standalone read error")

            time.sleep(3)

    except KeyboardInterrupt:
        logger.info("Ctrl-C is pressed. Closing DHT22 instance")
        dht22_instance.close()

