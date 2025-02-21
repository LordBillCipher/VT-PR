from pyplayready import Device
import base64


device = Device.load("./devices/samsung_gt-i9100-europen_gt-i9100_sl2000_b94a9b62.prd")
print("SL", device.security_level)
print("Device Version -", device.CURRENT_VERSION)
bytesdevice = device.dumps()

print(base64.b64encode(bytesdevice).decode("utf-8"))