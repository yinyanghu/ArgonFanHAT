import smbus
import RPi.GPIO as GPIO
import yaml

import argparse
import logging
import os
import psutil
import subprocess
import time
from threading import Thread

DEFAULT_CONFIG_FILE = "/etc/argonone/config.yaml"
SLEEP_INTERVAL = 10

log = logging.getLogger("argonone")
log.setLevel(logging.WARNING)


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
    SHUTDOWN_PIN = 4

    def __init__(self):
        if GPIO.RPI_REVISION in [2, 3]:
            self.bus = smbus.SMBus(1)
        else:
            self.bus = smbus.SMBus(0)
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.SHUTDOWN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

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

    def button_pulse_time(self):
        pulse_time = 1
        GPIO.write_for_edge(self.SHUTDOWN_PIN, GPIO.RISING)
        time.sleep(0.01)
        while GPIO.input(self.SHUTDOWN_PIN) == GPIO.HIGH:
            time.sleep(0.01)
            pulse_time += 1
        return pulse_time


def fan_service(pi, config, verbose):
    log.info(
        "starting fan service, current temperature: {}".format(
            pi.temperature()))
    fan_speed = config.idle_fan_speed()
    if verbose:
        log.info("set fan speed to {}%".format(fan_speed))
    pi.set_fan_speed(fan_speed, verbose)
    while True:
        temperature = pi.temperature()
        next_fan_speed = config.fan_speed(temperature)
        if verbose:
            log.info(
                "current temperature: {}, set fan speed to {}%".format(
                    temperature, next_fan_speed))
        pi.set_fan_speed(next_fan_speed)
        time.sleep(SLEEP_INTERVAL)


def button_service(pi, verbose):
    while True:
        pulse_time = pi.button_pulse_time()
        if 2 <= pulse_time <= 3:
            if verbose:
                log.info("button pressed for rebooting the system")
            os.system("reboot")
        elif 4 <= pulse_time <= 5:
            if verbose:
                log.info("button pressed for shutting down the system")
            os.system("shutdown now -h")


def main():
    parser = argparse.ArgumentParser(
        prog="argonone", description="Argon Fan HAT driver")
    parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_FILE,
        help="specify config file")
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="enable verbose output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if args.verbose:
        log.setLevel(logging.INFO)

    log.info("loading config file {}".format(os.path.abspath(args.config)))
    config = Config(args.config)
    pi = PiHardware()
    thread_fan = Thread(target=fan_service, args=(pi, config, args.verbose))
    thread_button = Thread(target=button_service, args=(pi, args.verbose))
    try:
        thread_fan.start()
        thread_button.start()
    except:
        thread_fan.stop()
        thread_button.stop()
    finally:
        pi.set_fan_speed(config.idle_fan_speed())
        GPIO.cleanup()


if __name__ == "__main__":
    main()
