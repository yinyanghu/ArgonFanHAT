# import smbus
# import RPi.GPIO as GPIO
import yaml

import os
import time

CONFIG_FILE = "config.yaml"
# CONFIG_FILE = "/etc/argonone/config.yaml"


def start_fan_service():
    pass


def start_button_service():
    pass


def stop_fan_service():
    pass


def stop_button_service():
    pass


def load_config_yaml(config_file):
    config = yaml.load(open(config_file, "r"), Loader=yaml.SafeLoader)
    # TODO: verify the config
    if not "mode" in config:
        raise ValueError("missing field 'mode' in the config file")
    config["temperature"].sort(key=lambda x: x["start_temp"], reverse=True)
    print(config)


def main():
    config = load_config_yaml(CONFIG_FILE)
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
