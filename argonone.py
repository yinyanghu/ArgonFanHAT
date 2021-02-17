import smbus
import RPi.GPIO as GPIO
import yaml

import argparse
import logging
import os
import psutil
import signal
import subprocess
import sys
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

    def mode(self):
        return self.config["mode"]

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
                if item["start_temperature"] <= temperature:
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
        GPIO.wait_for_edge(self.SHUTDOWN_PIN, GPIO.RISING)
        time.sleep(0.01)
        while GPIO.input(self.SHUTDOWN_PIN) == GPIO.HIGH:
            time.sleep(0.01)
            pulse_time += 1
        return pulse_time


def fan_service(pi, config, verbose):
    log.info("mode: {}".format(config.mode()))
    log.info(
        "starting fan service, current temperature: {}".format(
            pi.temperature()))
    fan_speed = config.idle_fan_speed()
    if verbose:
        log.info("setting fan speed to {}%".format(fan_speed))
    pi.set_fan_speed(fan_speed)
    while True:
        temperature = pi.temperature()
        next_fan_speed = config.fan_speed(temperature)
        if verbose:
            log.info(
                "current temperature: {}, setting fan speed to {}%".format(
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


def safe_exit(signum, frame):
    log.info("exiting")
    log.info("setting fan speed to 0")
    PiHardware().set_fan_speed(0)
    GPIO.cleanup()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        prog="argonone", description="Argon Fan HAT driver")
    parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_FILE,
        help="specify config file")
    parser.add_argument("-f", "--force-speed", default=None, type=int,
                        help="force set fan speed (0-100)")
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="enable verbose output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if args.verbose:
        log.setLevel(logging.INFO)

    pi = PiHardware()

    if not args.force_speed is None:
        if 0 <= args.force_speed <= 100:
            log.info("forcing fan speed to speed {}%".format(args.force_speed))
            pi.set_fan_speed(args.force_speed)
        else:
            log.error("please give a valid fan speed")
        GPIO.cleanup()
        return

    log.info("loading config file {}".format(os.path.abspath(args.config)))
    config = Config(args.config)

    signal.signal(signal.SIGINT, safe_exit)
    signal.signal(signal.SIGTERM, safe_exit)

    thread_fan = Thread(target=fan_service, args=(pi, config, args.verbose))
    thread_button = Thread(target=button_service, args=(pi, args.verbose))
    thread_fan.daemon = True
    thread_button.daemon = True

    thread_fan.start()
    thread_button.start()

    thread_fan.join()
    thread_button.join()


if __name__ == "__main__":
    main()
