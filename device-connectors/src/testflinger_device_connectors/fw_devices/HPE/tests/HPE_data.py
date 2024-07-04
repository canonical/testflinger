"""This file provides HPE ilorest outputs for unit tests"""

"""
ilorest rawget /redfish/v1/UpdateService/FirmwareInventory/ --expand --silent
"""
RAWGET_FIRMWARE_INVENTORY = """{
  "@odata.context": "/redfish/v1/$metadata#InventoryCollection",
  "@odata.etag": "W9EA3BDF0",
  "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/",
  "@odata.type": "#InventoryCollection.InventoryCollection",
  "Description": "Firmware Inventory Collection",
  "Members": [
    {
      "@odata.context": "/redfish/v1/$metadata#Inventory.Inventory",
      "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/1/",
      "@odata.type": "#Inventory.v1_2_0.Inventory",
      "Description": "SystemBMC",
      "Id": "1",
      "Name": "iLO 5",
      "Oem": {
        "Hpe": {
          "@odata.context": "/redfish/v1/$metadata#HpeiLOInventory",
          "@odata.type": "#HpeiLOInventory.v2_1_0.HpeiLOInventory",
          "DeviceClass": "2f317b9d-c9e3-4d76-bff6-b9d0d085a952",
          "DeviceContext": "System Board",
          "Targets": [
            "4764a662-b342-4fc7-9ce9-258c5d99e815",
            "c0bcf2b9-1141-49af-aab8-c73791f0349c"
          ]
        }
      },
      "Status": {
        "Health": "OK",
        "State": "Enabled"
      },
      "Updateable": true,
      "Version": "2.96 Aug 17 2023"
    },
    {
      "@odata.context": "/redfish/v1/$metadata#Inventory.Inventory",
      "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/2/",
      "@odata.type": "#Inventory.v1_2_0.Inventory",
      "Description": "SystemRomActive",
      "Id": "2",
      "Name": "System ROM",
      "Oem": {
        "Hpe": {
          "@odata.context": "/redfish/v1/$metadata#HpeiLOInventory",
          "@odata.type": "#HpeiLOInventory.v2_1_0.HpeiLOInventory",
          "DeviceClass": "aa148d2e-6e09-453e-bc6f-63baa5f5ccc4",
          "DeviceContext": "System Board",
          "Targets": [
            "00000000-0000-0000-0000-000000000205",
            "00000000-0000-0000-0000-000001553330"
          ]
        }
      },
      "Status": {
        "Health": "OK",
        "State": "Enabled"
      },
      "Updateable": true,
      "Version": "U30 v2.90 (07/20/2023)"
    },
    {
      "@odata.context": "/redfish/v1/$metadata#Inventory.Inventory",
      "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/3/",
      "@odata.type": "#Inventory.v1_2_0.Inventory",
      "Description": "PlatformDefinitionTable",
      "Id": "3",
      "Name": "Intelligent Platform Abstraction Data",
      "Oem": {
        "Hpe": {
          "@odata.context": "/redfish/v1/$metadata#HpeiLOInventory",
          "@odata.type": "#HpeiLOInventory.v2_1_0.HpeiLOInventory",
          "DeviceClass": "b8f46d06-85db-465c-94fb-d106e61378ed",
          "DeviceContext": "System Board",
          "Targets": [
            "00000000-0000-0000-0000-000000000205",
            "00000000-0000-0000-0000-000001553330"
          ]
        }
      },
      "Updateable": true,
      "Version": "16.5.0 Build 53"
    },
    {
      "@odata.context": "/redfish/v1/$metadata#Inventory.Inventory",
      "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/4/",
      "@odata.type": "#Inventory.v1_2_0.Inventory",
      "Description": "SystemProgrammableLogicDevice",
      "Id": "4",
      "Name": "System Programmable Logic Device",
      "Oem": {
        "Hpe": {
          "@odata.context": "/redfish/v1/$metadata#HpeiLOInventory",
          "@odata.type": "#HpeiLOInventory.v2_1_0.HpeiLOInventory",
          "DeviceClass": "b1ad439a-9dd1-41c1-a496-2da9313f1f07",
          "DeviceContext": "System Board",
          "Targets": [
            "00000000-0000-0000-0000-000000000205"
          ]
        }
      },
      "Status": {
        "Health": "OK",
        "State": "Enabled"
      },
      "Updateable": true,
      "Version": "0x31"
    },
    {
      "@odata.context": "/redfish/v1/$metadata#Inventory.Inventory",
      "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/5/",
      "@odata.type": "#Inventory.v1_2_0.Inventory",
      "Description": "PowerManagementController",
      "Id": "5",
      "Name": "Power Management Controller Firmware",
      "Oem": {
        "Hpe": {
          "@odata.context": "/redfish/v1/$metadata#HpeiLOInventory",
          "@odata.type": "#HpeiLOInventory.v2_1_0.HpeiLOInventory",
          "DeviceClass": "9e48a28a-586c-4519-8405-a04f84e27f0f",
          "DeviceContext": "System Board",
          "Targets": [
            "00000000-0000-0000-0000-000000000205",
            "00000000-0000-0000-0000-000000504d05"
          ]
        }
      },
      "Updateable": true,
      "Version": "1.1.0"
    }
  ],
  "Members@odata.count": 24,
  "Name": "Firmware Inventory Collection"
}
"""

"""ilorest systeminfo --system --json"""
SYSTEMINFO_SYSTEM = """{
  "system": {
    "Bios Version": "U30 v2.90 (07/20/2023)",
    "Model": "HPE ProLiant DL380 Gen10",
    "Serial Number": "2M20520660"
  }
}
"""
