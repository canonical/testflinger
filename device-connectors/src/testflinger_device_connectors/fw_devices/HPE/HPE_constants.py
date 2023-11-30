"""This file stores constants for HPE.py"""


"""
HPE firmware repository and index file
"""
HPE_SDR = "https://downloads.linux.hpe.com/SDR/repo"
INDEX_FILE = "fwrepo.json"

"""
HPE server model name to firmware repo name mapping
"""
FW_REPOS = {
    "rl": "rlcp",
    "gen10": "fwpp-gen10",
    "gen11": "fwpp-gen11",
}

"""
List of System Board firmware
"""
SYSTEM_BOARD_FW = [
    "iLO",
    "System ROM",
    "Innovation Engine",
    "Power",
    "Server Platform Services",
    "NVMe Backplane",
]

"""
Firmware to be ignored since they're not provided in the repository
"""
IGNORE_LIST = [
    "Intelligent Platform Abstraction Data",
    "Intelligent Provisioning",
    "Power Management Controller FW Bootloader",
    "Power Supply",
    "Redundant System ROM",
    "Descriptor",
    "Programmable Logic Device",
    "TPM Firmware",
    "TM Firmware",
    "EEPROM Engine",
]

"""
SPS firmware name to firmware file name mapping
"""
GEN10_SPS_TYPES = {
    "DL20 Gen10 Plus": "DL20GEN10Plus",
    "ML30 Gen10 Plus": "ML30GEN10Plus",
    "DL20 Gen10": "DL20ML30Gen10SPS",
    "ML30 Gen10": "DL20ML30Gen10SPS",
    "MicroServer Gen10 Plus v2": "MicroServerv2GEN10Plus",
    "MicroServer Gen10 Plus": "MicroserverGen10PlusSPS",
    "Gen10 Plus": "SPSGen10Plus",
    "Gen10": "SPSGen10",
}

"""
IE firmware name to file name mapping
"""
IE_TYPES = {"Gen10 Plus": "IEGen10Plus", "Gen10": "IEGen10"}

""" 
mapping PCI device to target ID with PCI IDs
target: a6b1a447-382a-5a4f-[ven]-[dev][subven][subdev]
"""
TARGET_PREFIX = "a6b1a447-382a-5a4f-"
