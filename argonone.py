import smbus
import RPi.GPIO as GPIO
import yaml

import os
import psutil
import subprocess
import time

CONFIG_FILE = "config.yaml"
# CONFIG_FILE = "/etc/argonone/config.yaml"

class Config:
    def __init__(self, config_file):
        self.config = yaml.load(open(config_file, "r"), Loader=yaml.SafeLoader)
        self.validate()

        self.config["temperature"].sort(key=lambda x: x["start_temp"], reverse=True)
        print(self.config)

    def validate(self):
        if not "mode" in self.config:
            raise ValueError("missing field 'mode' in the config file")
        if not self.config["mode"] in ["balanced", "quiet", "performance"]:
            raise ValueError("value of 'mode' must be 'balanced', 'quiet', or 'performance'")

class PiHardware:
    FAN_SPEED_BUS_ADDRESS = 0x1a

    def __init__(self):
        if GPIO.RPI_REVISION in [2, 3]:
            self.bus = smbus.SMBus(1)
        else:
            self.bus = smbus.SMBus(0)
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

    def temperature(self):
        return max(self.cpu_temperature(), self.gpu_temperature())

    def cpu_temperature(self):
        temperatures = psutil.sensors_temperatures()
        if not 'cpu_thermal' in temperatures:
            return None
        return temperatures['cpu_thermal'][0].current

    def gpu_temperature(self):
        output = subprocess.check_output(['vcgencmd', 'measure_temp'], encoding='utf-8')
        return float(output.replace('temp=', '').replace('\'C\n', ''))
    
    def set_fan_speed(self, percent):
        self.bus.write_byte(self.FAN_SPEED_BUS_ADDRESS, percent)


def start_fan_service(pi, config):
    print(pi.cpu_temperature())
    print(pi.gpu_temperature())
    print(pi.temperature())
    pi.set_fan_speed(10)


def start_button_service():
    pass


def stop_fan_service():
    pass


def stop_button_service():
    pass


def main():
    config = Config(CONFIG_FILE)
    pi = PiHardware()
    try:
        start_fan_service(pi, config)
        start_button_service()
    except:
        stop_fan_service()
        stop_button_service()
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
