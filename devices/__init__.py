import imp
import os


def load_devices():
    devices = []
    device_path = os.path.dirname(os.path.realpath(__file__))
    devs = [os.path.join(device_path, device)
            for device in os.listdir(device_path)
            if os.path.isdir(os.path.join(device_path, device))]
    for device in devs:
        if '__pycache__' in device:
            continue
        module = imp.load_source(
            'module', os.path.join(device, '__init__.py'))
        devices.append((module.device_name, module.DeviceAgent))
    return tuple(devices)

if __name__ == '__main__':
    load_devices()
