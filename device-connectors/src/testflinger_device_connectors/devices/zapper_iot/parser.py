"""provision yaml verify"""

import logging
import validators
import jsonschema
from jsonschema import validate

logger = logging.getLogger(__name__)

TPLAN_SCHEMA = {
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
                            "enum": [115200, 9600, 921600],
                            "default": 115200,
                        },
                    },
                    "required": ["port", "baud_rate"],
                },
                "network": {"type": "string"},
                "recipients": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/mail_format"},
                },
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
                                            "genio_flash",
                                            "utp_com",
                                            "uuu",
                                            "uuu_bootloader",
                                            "seed_override",
                                            "seed_override_lk",
                                        ],
                                    },
                                    "method": {"$ref": "#/$defs/method"},
                                    "extra_provision_tool_args": {
                                        "type": "string"
                                    },
                                    "timeout": {
                                        "type": "integer",
                                        "default": 600,
                                    },
                                    "update_boot_assets": {"type": "boolean"},
                                },
                                "required": ["utility", "method"],
                            },
                            "checkbox": {
                                "type": "object",
                                "properties": {
                                    "snap_name": {"type": "string"},
                                    "launcher": {"type": "string"},
                                    "secure_id": {
                                        "type": "string",
                                        "pattern": "^[0-9a-zA-Z]{22}$",
                                    },
                                    "submission_description": {
                                        "type": "string"
                                    },
                                },
                                "required": [
                                    "snap_name",
                                    "launcher",
                                    "secure_id",
                                ],
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
                            "console_commands_nb": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "cmd": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                ]
            },
        },
        "period": {
            "type": "object",
            "properties": {
                "mode": {"$ref": "#/$defs/mode"},
                "day": {"$ref": "#/$defs/day"},
                "time": {"$ref": "#/$defs/time"},
            },
            "required": ["mode"],
            "allOf": [
                {
                    "if": {"properties": {"mode": {"enum": ["day"]}}},
                    "then": {"required": ["time"]},
                },
                {
                    "if": {"properties": {"mode": {"enum": ["week"]}}},
                    "then": {"required": ["time", "day"]},
                },
            ],
        },
    },
    "required": ["config", "run_stage"],
    "$defs": {
        "time": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
        "day": {
            "type": "string",
            "enum": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        },
        "mode": {"type": "string", "enum": ["hour", "day", "week", "test"]},
        "mail_format": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9.]+@[a-zA-Z0-9.]+$",
        },
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


def validate_tplan(data):
    """for verify provision yaml"""
    try:
        validate(instance=data, schema=TPLAN_SCHEMA)
        logger.info("the JSON data is valid")
    except jsonschema.exceptions.ValidationError as err:
        raise ValueError("the JSON data is invalid") from err


def validate_url(url):
    """for verify url"""
    for link in url:
        if not validators.url(link):
            raise ValueError("url format is not correct")
