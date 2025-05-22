"""Map DMI chassis type to readable name."""


class Dmi:
    chassis = (
        ("Undefined", "unknown"),  # 0x00
        ("Other", "unknown"),  # 0x01
        ("Unknown", "unknown"),
        ("Desktop", "LVFS"),  # 0x03
        ("Low Profile Desktop", "unknown"),
        ("Pizza Box", "unknown"),
        ("Mini Tower", "unknown"),
        ("Tower", "unknown"),
        ("Portable", "unknown"),
        ("Laptop", "unknown"),  # 0x09
        ("Notebook", "unknown"),  # 0x0A
        ("Hand Held", "unknown"),
        ("Docking Station", "unknown"),
        ("All In One", "LVFS"),  # 0x0D
        ("Sub Notebook", "unknown"),
        ("Space-saving", "unknown"),
        ("Lunch Box", "unknown"),
        ("Main Server Chassis", "unknown"),  # 0x11
        ("Expansion Chassis", "unknown"),
        ("Sub Chassis", "unknown"),
        ("Bus Expansion Chassis", "unknown"),
        ("Peripheral Chassis", "unknown"),
        ("RAID Chassis", "unknown"),
        ("Rack Mount Chassis", "OEM-defined,LVFS"),  # 0x17
        ("Sealed-case PC", "unknown"),
        ("Multi-system", "unknown"),
        ("CompactPCI", "unknonw"),
        ("AdvancedTCA", "unknown"),
        ("Blade", "server"),
        ("Blade Enclosure", "unknown"),
        ("Tablet", "unknown"),
        ("Convertible", "unknown"),  # 0x1F
        ("Detachable", "unknown"),
        ("IoT Gateway", "unknown"),  # 0x21
        ("Embedded PC", "unknown"),
        ("Mini PC", "LVFS"),  # 0x23
        ("Stick PC", "unknown"),
    )

    chassis_names = tuple(c[0] for c in chassis)
    chassis_types = tuple(c[1] for c in chassis)
    chassis_name_to_type = dict(chassis)
