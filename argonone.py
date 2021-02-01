# import smbus
# import RPi.GPIO as GPIO
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
    @staticmethod
    def temperature():
        return max(PiHardware.cpu_temperature(), PiHardware.gpu_temperature())

    @staticmethod
    def cpu_temperature():
        temperatures = psutil.sensors_temperatures()
        if not 'cpu_thermal' in temperatures:
            return None
        return temperatures['cpu_thermal'][0].current

    @staticmethod
    def gpu_temperature():
        output = subprocess.check_output(['vcgencmd', 'measure_temp'], encoding='utf-8')
        return float(output.replace('temp=', '').replace('\'C\n', ''))

def start_fan_service(config):
    print(PiHardware.cpu_temperature())
    print(PiHardware.gpu_temperature())
    print(PiHardware.temperature())


def start_button_service():
    pass


def stop_fan_service():
    pass


def stop_button_service():
    pass


def main():
    config = Config(CONFIG_FILE)
    try:
        start_fan_service(config)
        start_button_service()
    except:
        stop_fan_service()
        stop_button_service()
    finally:
        pass
        # GPIO.cleanup()


if __name__ == "__main__":
    main()
