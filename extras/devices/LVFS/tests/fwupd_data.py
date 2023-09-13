""" fwupdmgr json outputs """


GET_RESULTS_RESPONSE_DATA = """{
  "Name" : "System Firmware",
  "DeviceId" : "a45df35ac0e948ee180fe216a5f703f32dda163f",
  "Guid" : [
    "37c94477-30f8-42df-96f9-5e417cc49274"
  ],
  "Plugin" : "uefi_capsule",
  "Flags" : [
    "internal",
    "updatable",
    "require-ac",
    "needs-reboot",
    "historical",
    "can-verify",
    "usable-during-update"
  ],
  "Checksums" : [
    "d655d59f250f7e15a90afb08f348ae428b9a37c1"
  ],
  "Version" : "2.91",
  "Created" : 1694166016,
  "Modified" : 1694166169,
  "UpdateState" : 2,
  "Releases" : [
    {
      "Version" : "2.90",
      "Checksum" : [
        "6232b2a43b22966b179f9b5a8f459731c37d7b8f"
      ],
      "LastAttemptVersion" : "0x2005a",
      "TpmFamily" : "2.0",
      "LastAttemptStatus" : "0x0",
      "RuntimeVersion(org.kernel)" : "5.10.0-1023-oem",
      "DistroVersion" : "20.04",
      "RuntimeVersion(org.freedesktop.fwupd)" : "1.7.9",
      "Pcr0_SHA1" : "d655d59f250f7e15a90afb08f348ae428b9a37c1",
      "UEFIUXCapsule" : "Enabled",
      "CpuArchitecture" : "x86_64",
      "SecureBoot" : "Disabled",
      "HostFamily" : "103C_53335X HP Workstation",
      "HostVendor" : "HP",
      "RuntimeVersion(org.freedesktop.gusb)" : "0.3.4",
      "FwupdTainted" : "False",
      "RuntimeVersion(com.dell.libsmbios)" : "2.4",
      "MissingCapsuleHeader" : "False",
      "CompileVersion(org.freedesktop.gusb)" : "0.3.4",
      "FwupdSupported" : "True",
      "KernelVersion" : "5.10.0-1023-oem",
      "TpmEventLog" : "0x00000008 88f88963e20ba2063edbf78215e9f90f37c551cd",
      "EspPath" : "/boot/efi",
      "HostProduct" : "HP Z4 G4 Workstation",
      "BootTime" : "1694165999",
      "KernelName" : "Linux",
      "CapsuleApplyMethod" : "nvram",
      "LinuxLockdown" : "none",
      "CompileVersion(com.hughsie.libjcat)" : "0.1.4",
      "Pcr0_SHA256" : "580aaf47328accd895515cc0143903c7e88579769d319a511ca9567575bd547f",
      "EfivarNvramUsed" : "100530",
      "KernelCmdline" : "automatic-oem-config",
      "DistroId" : "ubuntu",
      "CompileVersion(org.freedesktop.fwupd)" : "1.7.9",
      "HostSku" : "8DZ51UT#ABA"
    }
  ]
}
"""

GET_RESULTS_ERROR_RESPONSE_DATA = """
{
  "Error" : {
    "Domain" : "FwupdError",
    "Code" : 9,
    "Message" : "Failed to find 4bde70ba4e39b28f9eab1628f9dd6e6244c03027 in history database: No devices found"
  }
}
"""

GET_DEVICES_RESPONSE_DATA = """{
  "Devices" : [
    {
      "Name" : "Core™ i7-9800X CPU @ 3.80GHz",
      "DeviceId" : "4bde70ba4e39b28f9eab1628f9dd6e6244c03027",
      "Guid" : [
        "b9a2dd81-159e-5537-a7db-e7101d164d3f",
        "30249f37-d140-5d3e-9319-186b1bd5cac3",
        "aeac0d3d-a127-52d8-9745-891104b2ec28",
        "1c7713d4-3bd2-5032-b9cc-291671aba257"
      ],
      "Plugin" : "cpu",
      "Flags" : [
        "internal",
        "registered"
      ],
      "Vendor" : "Intel",
      "VersionFormat" : "hex",
      "Icons" : [
        "computer"
      ],
      "Created" : 1693535931
    },
    {
      "Name" : "DVDRW GUD1N",
      "DeviceId" : "612faa85309fec62ddfdce9f4635cdfef838d74e",
      "Guid" : [
        "bcb713aa-ecde-5359-a2e5-49fe84787374",
        "57ac0a58-5421-53ce-ac80-4566d4e1e6e3"
      ],
      "Summary" : "SCSI device",
      "Plugin" : "scsi",
      "Flags" : [
        "registered"
      ],
      "Vendor" : "hp HLDS",
      "VendorId" : "SCSI:hp-HLDS",
      "Version" : "LD06",
      "VersionFormat" : "plain",
      "Icons" : [
        "drive-harddisk"
      ],
      "Created" : 1693535931
    },
    {
      "Name" : "GP104GL [Quadro P5000]",
      "DeviceId" : "3c07caee1bce434f1160c260ba0a471f60d66961",
      "Guid" : [
        "643cf998-eaee-5c6f-b403-8370b5f04f10",
        "0e71595a-45dd-58cc-aed4-a29cd1e0176d",
        "38458a57-3a97-53fa-824a-ba3809471a07",
        "0ed83a18-0bb5-590e-aae1-7d07ca60a280"
      ],
      "Plugin" : "optionrom",
      "Flags" : [
        "internal",
        "registered",
        "can-verify",
        "can-verify-image"
      ],
      "Vendor" : "NVIDIA Corporation",
      "VendorId" : "PCI:0x10DE",
      "Version" : "a1",
      "VersionFormat" : "plain",
      "Icons" : [
        "audio-card"
      ],
      "Created" : 1693535931
    },
    {
      "Name" : "MZVLB256HBHQ-000H1",
      "DeviceId" : "599ead362818be284e800cbc30d4c29f934086c3",
      "Guid" : [
        "0b4d773a-7ac3-58c1-a541-e22ef1cdfe02",
        "c9d531ea-ee7d-5562-8def-c64d0d144813",
        "6e54c992-d302-59ab-b454-2d26ddd63e6d",
        "47335265-a509-51f7-841e-1c94911af66b",
        "e803e58a-cbd1-5b1c-b60b-dc4cd6e985d7"
      ],
      "Serial" : "S4GNNX0NC13964",
      "Summary" : "NVM Express solid state drive",
      "Plugin" : "nvme",
      "Protocol" : "org.nvmexpress",
      "Flags" : [
        "internal",
        "updatable",
        "require-ac",
        "registered",
        "needs-reboot",
        "usable-during-update",
        "signed-payload"
      ],
      "Vendor" : "Samsung",
      "VendorId" : "NVME:0x144D",
      "Version" : "HPS0NEXH",
      "VersionFormat" : "plain",
      "Icons" : [
        "drive-harddisk"
      ],
      "Created" : 1693535931
    },
    {
      "Name" : "SanDisk 3.2Gen1",
      "DeviceId" : "136108aa898cf18c2d6c51fb0d3942fcab13055b",
      "Guid" : [
        "9d4068a9-9553-59a2-ad7f-b19922d584b1",
        "b861e037-c38d-56ea-adaf-b2325ee6b96b"
      ],
      "Summary" : "SCSI device",
      "Plugin" : "scsi",
      "Flags" : [
        "registered"
      ],
      "Vendor" : "USB",
      "VendorId" : "SCSI:USB",
      "Version" : "1.00",
      "VersionFormat" : "plain",
      "Icons" : [
        "drive-harddisk"
      ],
      "Created" : 1693535931
    },
    {
      "Name" : "System Firmware",
      "DeviceId" : "a45df35ac0e948ee180fe216a5f703f32dda163f",
      "Guid" : [
        "37c94477-30f8-42df-96f9-5e417cc49274",
        "230c8b18-8d9b-53ec-838b-6cfc0383493a"
      ],
      "Summary" : "UEFI ESRT device",
      "Plugin" : "uefi_capsule",
      "Protocol" : "org.uefi.capsule",
      "Flags" : [
        "internal",
        "updatable",
        "require-ac",
        "supported",
        "registered",
        "needs-reboot",
        "can-verify",
        "usable-during-update"
      ],
      "Checksums" : [
        "88168c9e2b47f7560125cd6f811a9b4390f8bc70",
        "3bc12536624150ef382938f92ca0d3d80aed712552ae89cc8957d884d9372315"
      ],
      "Vendor" : "HP",
      "VendorId" : "DMI:HP",
      "Version" : "2.90",
      "VersionLowest" : "0.1",
      "VersionFormat" : "pair",
      "VersionRaw" : 131162,
      "VersionLowestRaw" : 1,
      "Icons" : [
        "computer"
      ],
      "Created" : 1693535931,
      "UpdateState" : 2,
      "Releases" : [
        {
          "AppstreamId" : "com.hp.workstation.P62.firmware",
          "ReleaseId" : "28623",
          "RemoteId" : "lvfs",
          "Name" : "Z4 G4 Core-X Workstation",
          "Summary" : "System Firmware (BIOS) for HP Z4 G4 Workstations (Core X-series processors), family P62",
          "Description" : "<p>Fixes and enhancements in P62 2.91:</p><ul><li>Includes enhancements to mitigate security vulnerabilities.</li><li>Added support for a new DIMM manufacturer.</li><li>Added support for HP Anyware Remote System Controller features.</li></ul>",
          "Version" : "2.91",
          "Filename" : "9af72a66c38ab97ed17f1388582eb6baa0929295",
          "Protocol" : "org.uefi.capsule",
          "Categories" : [
            "X-System"
          ],
          "Checksum" : [
            "5ffa48e85b1bbb98a4a911643cd4a690194fee97",
            "2571fa9e4ca038aa41c86ded57d355a70d1da3a02bcd12aa02b9c5ab84d8a2ee"
          ],
          "License" : "LicenseRef-proprietary",
          "Size" : 16781312,
          "Created" : 1679514694,
          "Locations" : [
            "https://fwupd.org/downloads/2571fa9e4ca038aa41c86ded57d355a70d1da3a02bcd12aa02b9c5ab84d8a2ee-P62_0291.cab"
          ],
          "Uri" : "https://fwupd.org/downloads/2571fa9e4ca038aa41c86ded57d355a70d1da3a02bcd12aa02b9c5ab84d8a2ee-P62_0291.cab",
          "Homepage" : "http://www.hp.com/go/workstations",
          "Vendor" : "HP",
          "Flags" : [
            "is-upgrade"
          ]
        },
        {
          "AppstreamId" : "com.hp.workstation.P62.firmware",
          "ReleaseId" : "22717",
          "RemoteId" : "lvfs",
          "Name" : "Z4 G4 Core-X Workstation",
          "Summary" : "System Firmware (BIOS) for HP Z4 G4 Workstations (Core X-series processors), family P62",
          "Description" : "<p>Fixes and enhancements in P62 2.90:</p><ul><li>Added SATA hot plug support.</li><li>Includes enhancements to mitigate security vulnerabilities.</li><li>HP strongly recommends promptly transitioning to this updated BIOS version.</li><li>Updates UEFI-based Hardware Diagnostics to version 2.3.2.0&gt;</li><li>Addressed changes introduced in previous BIOS which prevented a custom logo from being set.</li></ul>",
          "Version" : "2.90",
          "Filename" : "ba3142d342afce4c5bde21ee469871156cb8add3",
          "Protocol" : "org.uefi.capsule",
          "Categories" : [
            "X-System"
          ],
          "Checksum" : [
            "6232b2a43b22966b179f9b5a8f459731c37d7b8f",
            "90c505fd9b6f56311a4202d8fb95e711ab240dfcd50b0ff82a9ebe5f4750eed6"
          ],
          "License" : "LicenseRef-proprietary",
          "Size" : 16781312,
          "Created" : 1675389026,
          "Locations" : [
            "https://fwupd.org/downloads/90c505fd9b6f56311a4202d8fb95e711ab240dfcd50b0ff82a9ebe5f4750eed6-P62_0290.cab"
          ],
          "Uri" : "https://fwupd.org/downloads/90c505fd9b6f56311a4202d8fb95e711ab240dfcd50b0ff82a9ebe5f4750eed6-P62_0290.cab",
          "Homepage" : "http://www.hp.com/go/workstations",
          "Vendor" : "HP"
        },
        {
          "AppstreamId" : "com.hp.workstation.P62.firmware",
          "ReleaseId" : "14966",
          "RemoteId" : "lvfs",
          "Name" : "Z4 G4 Core-X Workstation",
          "Summary" : "System Firmware (BIOS) for HP Z4 G4 Workstations (Core X-series processors), family P62",
          "Description" : "<p>Fixes and enhancements in P62 2.85:</p><ul><li>Includes enhancements to mitigate security vulnerabilities.</li><li>HP strongly recommends promptly transitioning to this updated BIOS version.</li><li>Adds SMBIOS System Enclosure or Chassis (Type 3) entry.</li><li>Fixes an issue where Network BIOS Update would fail in Legacy mode.</li><li>Fixes an issue where system would not boot with a certain PCIe serial card installed.</li><li>Fixes a performance issue with a certain PCIe FireWire card.</li></ul>",
          "Version" : "2.85",
          "Filename" : "8e9bfcf011d2a6c38986d7bebdf5fc8b39e23bd3",
          "Protocol" : "org.uefi.capsule",
          "Categories" : [
            "X-System"
          ],
          "Checksum" : [
            "17fcf952384cbf17f1dce5a150303b4a38e0178b",
            "f328b807e6318c51d531771bd9e1b17efffcad755d7ca9ac3913faa1015f340d"
          ],
          "License" : "LicenseRef-proprietary",
          "Size" : 16781312,
          "Created" : 1658274892,
          "Locations" : [
            "https://fwupd.org/downloads/f328b807e6318c51d531771bd9e1b17efffcad755d7ca9ac3913faa1015f340d-P62_0285.cab"
          ],
          "Uri" : "https://fwupd.org/downloads/f328b807e6318c51d531771bd9e1b17efffcad755d7ca9ac3913faa1015f340d-P62_0285.cab",
          "Homepage" : "http://www.hp.com/go/workstations",
          "Vendor" : "HP",
          "Flags" : [
            "is-downgrade"
          ]
        }
      ]
    },
    {
      "Name" : "TPM",
      "DeviceId" : "c6a80ac3a22083423992a3cb15018989f37834d6",
      "Guid" : [
        "ff71992e-52f7-5eea-94ef-883e56e034c6",
        "5eebb112-75ad-5536-b173-a11eb3399402",
        "ddf995da-1b32-5a8a-bc1b-8d5af4b38b51",
        "6d81ab63-db2e-50ac-934f-6be9accf5e02",
        "301555de-680d-5ddc-b995-7553fc9138f1"
      ],
      "Plugin" : "tpm",
      "Flags" : [
        "internal",
        "registered"
      ],
      "Vendor" : "Infineon",
      "VendorId" : "TPM:IFX",
      "Version" : "7.85.17.51968",
      "VersionFormat" : "quad",
      "VersionRaw" : 1970689910360832,
      "Icons" : [
        "computer"
      ],
      "Created" : 1693535931
    },
    {
      "Name" : "UEFI dbx",
      "DeviceId" : "362301da643102b9f38477387e2193e57abaa590",
      "ParentDeviceId" : "a45df35ac0e948ee180fe216a5f703f32dda163f",
      "CompositeId" : "a45df35ac0e948ee180fe216a5f703f32dda163f",
      "Guid" : [
        "20716f78-5f65-5fe7-b32b-55a6a16392ab",
        "f1d99738-25d4-5f76-a2ec-87750d294993",
        "c6682ade-b5ec-57c4-b687-676351208742",
        "f8ba2887-9411-5c36-9cee-88995bb39731"
      ],
      "Summary" : "UEFI revocation database",
      "Plugin" : "uefi_dbx",
      "Protocol" : "org.uefi.dbx",
      "Flags" : [
        "internal",
        "updatable",
        "registered",
        "needs-reboot",
        "only-version-upgrade",
        "signed-payload"
      ],
      "VendorId" : "UEFI:Linux Foundation",
      "Version" : "239",
      "VersionLowest" : "239",
      "VersionFormat" : "number",
      "Icons" : [
        "computer"
      ],
      "InstallDuration" : 1,
      "Created" : 1693535931
    }
  ]
}"""
