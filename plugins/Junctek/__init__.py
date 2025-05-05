import logging
import time
from collections import deque


class Config:
    SEND_ACK = False
    NEED_POLLING = False
    NOTIFY_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
    NOTIFY_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"


class Util:
    """
    Class for reading and parsing data from Junctek KF-KG Series Battery Monitor.

    All parameters from the Junctek are in the Parameters().PARAM_KEYS dict.
    Any formatting changes takes place in formatValues()

    User defined settings are in class: UserSettings()
    """

    min_remaining_history = deque()

    class UserSettings:
        # Set your battery capacity here (as an int):
        BATTERY_CAPACITY_AH = 100

        # The Junctek only transmit its charging state when
        # the charging state changes, so set to True to assume battery
        # is charging when the script starts.
        START_SCRIPT_CHARGING = False

    class Parameters:
        BEGINNING_OF_STREAM = "BB"
        END_OF_STREAM = "EE"
        PARAM_KEYS = {
            "voltage": "C0",
            "current": "C1",
            "soc": "D0",
            "dir_of_current": "D1",
            "ah_remaining": "D2",
            "mins_remaining": "D6",
            "power": "D8",
            "temp": "D9",
        }

    def __init__(self, power_device):
        self.PowerDevice = power_device
        self.charging = self.UserSettings().START_SCRIPT_CHARGING

    def notificationUpdate(self, data, char):
        """
        Gets the binary data from the BLE-device and converts it to a byte stream
        """
        bs = str(data.hex()).upper()

        if not self.validate(bs):
            return False

        values = self.getValues(bs)
        formatted_values = self.formatValues(values)
        # logging.debug(formatted_values)
        return self.handleMessage(formatted_values)

    def validate(self, bs):
        """
        Validate that the data has a valid start of stream and end of stream,
        and contains at least one known parameter.
        """
        if bs is None:
            logging.warning("Empty BS {}".format(bs))
            return False

        if not bs.startswith(self.Parameters.BEGINNING_OF_STREAM):
            logging.warning("Incorrect beginning of stream: {}".format(bs))
            return False

        if not bs.endswith(self.Parameters.END_OF_STREAM):
            logging.warning("Incorrect end of stream: {}".format(bs))
            return False

        if not [v for v in self.Parameters.PARAM_KEYS.values() if v in bs]:
            # logging.debug("No parameters found in stream: {}".format(bs))
            return False

        return True

    def getValues(self, bs):
        """
        Get raw values from the bytestream:

        Returns a dict containing any keys in Parameters().PARAM_KEYS
        and raw values found in the bytestream.

        Bytestreams are varying lengths, with hex keys and decimal values, and follow this format:
        [starting byte] [dec value] [hex param key] ... [dec value] [hex param key] ... [checksum] [ending byte]

        The value precedes the hex parameter key.
        ie: 12.32v would be: 1232C0, where 1232=12.32v and C0=voltage param key

        To modify or add new parameters, change Parameters().PARAM_KEYS. This function will grab any new values it
        finds that can be associated with a param key.
        """
        # params = [i for i in self.Parameters().PARAM_KEYS.values()]
        params_keys = list(self.Parameters().PARAM_KEYS.keys())
        params_values = list(self.Parameters().PARAM_KEYS.values())

        # split bs into a list of all values and hex keys
        bs_list = [bs[i : i + 2] for i in range(0, len(bs), 2)]

        # reverse the list so that values come after hex params
        bs_list_rev = list(reversed(bs_list))

        values = {}
        # iterate through the list and if a param is found,
        # add it as a key to the dict. The value for that key is a
        # concatenation of all following elements in the list
        # until a non-numeric element appears. This would either
        # be the next param or the beginning hex value.
        for i in range(len(bs_list_rev) - 1):
            if bs_list_rev[i] in params_values:
                value_str = ""
                j = i + 1
                while j < len(bs_list_rev) and bs_list_rev[j].isdigit():
                    value_str = bs_list_rev[j] + value_str
                    j += 1

                position = params_values.index(bs_list_rev[i])

                key = params_keys[position]
                values[key] = value_str

        return values

    def formatValues(self, values):
        """
        Format the value to the right decimal place, or perform other formatting
        """
        for key, value in list(values.items()):
            if not value.isdigit():
                del values[key]

            val_int = int(value)
            if key == "voltage":
                values[key] = val_int / 100
            elif key == "current":
                values[key] = val_int / 100
            elif key == "dir_of_current":
                if value == "01":
                    self.charging = True
                else:
                    self.charging = False
            elif key == "ah_remaining":
                values[key] = val_int / 1000
            elif key == "mins_remaining":
                values[key] = val_int
            elif key == "power":
                values[key] = val_int / 100
            elif key == "temp":
                values[key] = val_int - 100
            # VERIFY
            elif key == "soc":
                values[key] = val_int * 100

        # Display current as negative numbers if discharging
        if not self.charging:
            if "current" in values:
                values["current"] *= -1
            if "power" in values:
                values["power"] *= -1

        # Calculate SoC
        # if (
        #     isinstance(self.UserSettings().BATTERY_CAPACITY_AH, int)
        #     and "ah_remaining" in values
        # ):
        #     values["soc"] = (
        #         values["ah_remaining"] / self.UserSettings().BATTERY_CAPACITY_AH * 100
        #     )

        # Calculate minutes remaining by taking avg of recent mins_remaining values
        if "mins_remaining" in values:
            now = time.time()
            expiry_seconds = 600

            self.min_remaining_history.append((now, values["mins_remaining"]))

            while (
                self.min_remaining_history
                and now - self.min_remaining_history[0][0] > expiry_seconds
            ):
                self.min_remaining_history.popleft()

            if self.min_remaining_history:
                valid_values = [v for _, v in self.min_remaining_history]
                values["mins_remaining"] = sum(valid_values) / len(valid_values)

        # Append max capacity
        values["max_capacity"] = self.UserSettings().BATTERY_CAPACITY_AH

        return values

    def handleMessage(self, values):
        if not values:
            return False

        if "voltage" in values:
            self.PowerDevice.entities.voltage = values["voltage"]
        if "current" in values:
            self.PowerDevice.entities.current = values["current"]
        if "power" in values:
            self.PowerDevice.entities.power = values["power"]
        if "max_capacity" in values:
            self.PowerDevice.entities.max_capacity = values["max_capacity"]
        if "ah_remaining" in values:
            self.PowerDevice.entities.exp_capacity = values["ah_remaining"]
        if "mins_remaining" in values:
            self.PowerDevice.entities.mins_remaining = values["mins_remaining"]
        if "soc" in values:
            self.PowerDevice.entities.soc = values["soc"]
        if "temp" in values:
            self.PowerDevice.entities.temperature_celsius = values["temp"]

        return True
