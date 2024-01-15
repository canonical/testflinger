import os
import json
import yaml
import jsonschema
from jsonschema import validate

LAUNCHER_SCHEMA = {
    "type": "object",
    "properties": {
        "config": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "serial_console": {
                    "type": "object",
                    "properties": {
                        "port": {"type": "string"},
                        "baud_rate": {
                            "type": "integer",
                            "enum": [115200, 9600],
                            "default": 115200,
                        },
                    },
                    "required": ["port", "baud_rate"],
                },
                "network": {"type": "string"},
                "hostname": {"type": "string"},
            },
            "required": [
                "project_name",
                "username",
                "password",
                "serial_console",
                "network",
            ],
        },
        "run_stage": {
            "type": "array",
            "minItems": 1,
            "items": {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": ["login", "run_login", "reboot"],
                    },
                    {
                        "type": "object",
                        "properties": {
                            "deploy": {
                                "type": "object",
                                "properties": {
                                    "utility": {
                                        "type": "string",
                                        "enum": [
                                            "utp_com",
                                            "uuu",
                                            "uuu_bootloader",
                                            "seed_override",
                                            "seed_override_lk",
                                        ],
                                    },
                                    "method": {"$ref": "#/$defs/method"},
                                    "timeout": {
                                        "type": "integer",
                                        "default": 600,
                                    },
                                    "update_boot_assets": {"type": "boolean"},
                                },
                                "required": ["utility", "method"],
                            },
                            "initial_login": {
                                "type": "object",
                                "properties": {
                                    "method": {"$ref": "#/$defs/method"},
                                    "timeout": {
                                        "type": "integer",
                                        "default": 600,
                                    },
                                },
                                "required": ["method"],
                            },
                            "reboot_install": {
                                "type": "object",
                                "properties": {
                                    "method": {"$ref": "#/$defs/method"},
                                    "timeout": {
                                        "type": "integer",
                                        "default": 600,
                                    },
                                },
                                "required": ["method"],
                            },
                            "sys_commands": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "eof_commands": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "cmd": {"type": "string"},
                                        "expected": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                ]
            },
        },
    },
    "required": ["config", "run_stage"],
    "$defs": {
        "method": {
            "type": "string",
            "enum": [
                "cloud-init",
                "console-conf",
                "system-user",
            ],
        },
    },
}


class LauncherParser:
    def __init__(self, file):
        _, ext = os.path.splitext(file)
        with open(file, "r") as fp:
            if ext == ".json":
                self._data = json.load(fp)
            elif ext in [".yaml", ".yml"]:
                self._data = yaml.load(fp, Loader=yaml.FullLoader)
            else:
                raise SystemExit(
                    "The tplan should has extend name in json or yaml."
                )

        self.validate_data()

    @property
    def data(self):
        return self._data

    def validate_data(self):
        try:
            validate(instance=self._data, schema=LAUNCHER_SCHEMA)
            print("the JSON data is valid")
        except jsonschema.exceptions.ValidationError as err:
            raise ValueError("the JSON data is invalid, err {}".format(err))
