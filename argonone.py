import smbus
import RPi.GPIO as GPIO
import yaml

import os
import psutil
import subprocess
import time

CONFIG_FILE = "config.yaml"
SLEEP_INTERVAL = 10
# CONFIG_FILE = "/etc/argonone/config.yaml"


class Config:
    def __init__(self, config_file):
        # TODO: check if the config exists
        self.config = yaml.load(open(config_file, "r"), Loader=yaml.SafeLoader)
        self.validate()

        self.config["temperature"].sort(
            key=lambda x: x["start_temperature"], reverse=True)
        print(self.config)

    def is_balanced(self):
        return self.config["mode"] == "balanced"

    def is_quiet(self):
        return self.config["mode"] == "quiet"

    def is_performance(self):
        return self.config["mode"] == "performance"

    def validate(self):
        if not "mode" in self.config:
            raise ValueError("missing field 'mode' in the config file")
        if not self.config["mode"] in ["balanced", "quiet", "performance"]:
            raise ValueError(
                "value of 'mode' must be 'balanced', 'quiet', or 'performance'")

    def temperature(self):
        return self.config["temperature"]

    def idle_temperature_limit(self):
        return self.config["idle_temperature_limit"]

    def idle_fan_speed(self):
        return self.config["idle_fan_speed"] if "idle_fan_speed" in self.config else 0

    def min_set_fan_speed(self):
        return self.config["temperature"][-1]["fan_speed"]

    def fan_speed(self, temperature):
        if self.is_balanced():
            for item in self.temperature():
                if item["start_temperature"] >= temperature:
                    return item["fan_speed"]
            return self.idle_fan_speed()
        elif self.is_quiet():
            for item in self.temperature():
                if item["start_temperature"] >= temperature:
                    return item["fan_speed"]
            if temperature <= self.idle_temperature_limit():
                return self.idle_fan_speed()
            else:
                return self.min_set_fan_speed()
        elif self.is_performance():
            return 100
        else:
            raise ValueError("unknown mode is set")


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
        output = subprocess.check_output(
            ['vcgencmd', 'measure_temp'], encoding='utf-8')
        return float(output.replace('temp=', '').replace('\'C\n', ''))

    def set_fan_speed(self, percent):
        self.bus.write_byte(self.FAN_SPEED_BUS_ADDRESS, percent)


def start_fan_service(pi, config):
    print(pi.cpu_temperature())
    fan_speed = config.idle_fan_speed()
    pi.set_fan_speed(fan_speed)
    while True:
        next_fan_speed = config.fan_speed(pi.temperature())
        pi.set_fan_speed(next_fan_speed)
        time.sleep(SLEEP_INTERVAL)


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
