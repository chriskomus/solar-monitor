import logging
import libscrc


class Config():
    SEND_ACK  = False
    NEED_POLLING = False
    NOTIFY_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
    NOTIFY_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

class Util():
    '''
    Class for reading and parsing data from Junctek K170F Battery Monitor
    '''
    class Parameters():
        BEGINNING_OF_STREAM = "BB"
        END_OF_STREAM = "EE"
        PARAM_KEYS = {
            "volts": "C0",
            "amps": "C1",
            "watts": "D8",
            "ah_remaining": "D2",
            "mins_remaining": "D6",
        }

    def __init__(self, power_device):
        self.PowerDevice = power_device


    def getValue(self, buf, start, end):
        # Reads "start" -> "end" from "buf" and return the hex-characters in the correct order
        string = buf[start:end + 1]
        # logging.debug(string)
        e = end + 1
        b = end - 1
        string = ""
        while b >= start:
            chrs = buf[b:e]
            # logging.debug(chrs)
            e = b
            b = b - 2
            string += chr(chrs[0]) + chr(chrs[1])
            # logging.debug(string)
        try:
            ret = int(string, 16)
        except Exception as e:
            ret = 0
        return ret


    def notificationUpdate(self, data, char):
        """
        Gets the binary data from the BLE-device and converts it to a byte stream
        """
        value = str(data.hex()).upper()

        if not self.validate(value):
            return False

        print(value)

        # cmdData = ""
        # if data != None and len(data):
        #     i = 0
        #     while i < len(data):
        #         # logging.debug("Revindex {} {} Data: {}".format(i, self.Revindex, data[i]))
        #         # logging.debug("RevBuf begin {}".format(self.RevBuf))
        #         if self.Revindex > 121:
        #             # logging.debug("Revindex  > 121 - parsing done")
        #             self.Revindex = 0
        #             self.end = 0
        #             self.RecvDataType = self.SOI
        #         # if data[i] == 146:
        #             # logging.debug("Data_1 == 146 start of info")
        #             # self.RecvDataType = self.INFO
        #             # self.Revindex = 0
        #         # logging.debug("RecvDataType {} {}".format(i, self.RecvDataType))
        #         if self.RecvDataType == self.SOI:
        #             # logging.debug("RecvDataType == 1 -> SOI")
        #             # logging.debug("Data_1 == {} &255 == {}".format(data[i], data[i] & 255))
        #             if data[i] == 146:
        #                 # logging.debug("Data_1 & 255 == 146 start of info")
        #                 self.RecvDataType = self.INFO
        #                 self.RevBuf[self.Revindex] = data[i]
        #                 self.Revindex = self.Revindex + 1
        #         elif self.RecvDataType == self.INFO:
        #             # logging.debug("RecvDataType == 2 -> INFO")
        #             # logging.debug("Revindex {} Data_1 == {}".format(self.Revindex, data[i]))
        #             self.RevBuf[self.Revindex] = data[i]
        #             self.Revindex = self.Revindex + 1

        #             if data[i] == 12:
        #                 # logging.debug("Data_i == 12 - end: {} Revindex {}".format(self.end, self.Revindex))
        #                 if self.end < 110:
        #                     self.end = self.Revindex
        #                 # if self.Revindex != 121 and self.Revindex != 66 and self.Revindex != 88:
        #                 # else:
        #             # if self.Revindex == 121 or self.Revindex == 66 or self.Revindex == 88:
        #                 if self.Revindex == 121:
        #                     self.RecvDataType = self.EOI
        #             # else:
        #         elif self.RecvDataType == self.EOI:
        #             # logging.debug("RecvDataType == 3 -> EOI")
        #             # logging.debug("Validate Checksum: {}".format(self.validateChecksum(self.RevBuf)))
        #             if self.validateChecksum(self.RevBuf):
        #                 # cmdData = str(self.RevBuf, 1, self.Revindex)
        #                 # logging.debug("{} revindex: {}".format(self.TAG, self.Revindex))
        #                 cmdData = self.RevBuf[1:self.Revindex]
        #                 self.Revindex = 0
        #                 self.end = 0
        #                 self.RecvDataType = self.SOI
        #                 return self.handleMessage(cmdData)
        #             self.Revindex = 0
        #             self.end = 0
        #             self.RecvDataType = self.SOI
        #         i += 1
        # # logging.debug("broadcastUpdate End cmdData: {} RevBuf {}".format(cmdData, self.RevBuf))
        # return False

    def validate(self, bs):
        """
        Validate that the data has a valid start of stream and end of stream,
        and contains at least one known parameter.
        """
        if bs == None:
            logging.warning("Empty BS {}".format(bs))
            return False

        if not bs.startswith(self.Parameters.BEGINNING_OF_STREAM):
            logging.warning("Incorrect beginning of stream: {}".format(bs))
            return False

        if not bs.endswith(self.Parameters.END_OF_STREAM):
            logging.warning("Incorrect end of stream: {}".format(bs))
            return False

        if not [v for v in self.Parameters.PARAM_KEYS.values() if v in bs]:
            logging.debug("No parameters found in stream: {}".format(bs))
            return False

        return True

    def handleMessage(self, message):
        # Accepts a list of hex-characters, and returns the human readable values into the powerDevice object
        logging.debug("handleMessage {}".format(message))
        if message == None or "" == message:
            return False
        # logging.debug("test handleMessage == {}".format(message))
        if len(message) < 38:
            logging.info("len message < 38: {}".format(len(message)))
            return False
        # logging.info("Parsing data from a {}".format(self.DeviceType))

        self.PowerDevice.entities.msg = message
        # if self.DeviceType == '12V100Ah-027':
        self.PowerDevice.entities.mvoltage = self.getValue(message, 0, 7)
        logging.debug("mVoltage: {}".format(self.getValue(message, 0, 7)))
        mcurrent = self.getValue(message, 8, 15)
        if mcurrent > 2147483647:
            mcurrent = mcurrent - 4294967295
        self.PowerDevice.entities.mcurrent = mcurrent
        self.PowerDevice.entities.mcapacity = self.getValue(message, 16, 23)
        self.PowerDevice.entities.charge_cycles = self.getValue(message, 24, 27)
        self.PowerDevice.entities.soc = self.getValue(message, 28, 31)
        self.PowerDevice.entities.temperature = self.getValue(message, 32, 35)
        self.PowerDevice.entities.status = self.getValue(message, 36, 37)
        self.PowerDevice.entities.afestatus = self.getValue(message, 40, 41)
        i = 0
        while i < 16:
            self.PowerDevice.entities.cell_mvoltage = (i + 1, self.getValue(message, (i * 4) + 44, (i * 4) + 47))
            i = i + 1

        return True