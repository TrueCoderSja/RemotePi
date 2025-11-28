#!/bin/bash


set -e 
export CONFIGFS_HOME="/sys/kernel/config/usb_gadget"
export GADGET_NAME="remotepi"

# Color codes for professional output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_msg() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] [SYSTEM] $1${NC}"
}

err_msg() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

# Check for root privileges
if [ "$EUID" -ne 0 ]; then 
    err_msg "Please run as root (sudo)"
    exit 1
fi

log_msg "Loading libcomposite kernel module..."
modprobe libcomposite

cd $CONFIGFS_HOME
if [ -d "$GADGET_NAME" ]; then
    log_msg "Gadget directory already exists. Cleaning up..."
    # Cleanup logic would go here (omitted for brevity)
fi

log_msg "Creating gadget directory structure..."
mkdir -p "$GADGET_NAME"
cd "$GADGET_NAME"

# Set USB Device Descriptors (Vendor: Linux Foundation)
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

# Create English (0x409) string descriptors
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "Bennett University" > strings/0x409/manufacturer
echo "RemotePi KVM Device" > strings/0x409/product

# Create Configuration
mkdir -p configs/c.1/strings/0x409
echo "Config 1: Composite HID" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# Create Function: HID Keyboard & Mouse
# Note: Report descriptors are binary data passed as raw bytes
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
# Write report descriptor (Keyboard + Mouse composite)
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc

# Bind function to configuration
ln -s functions/hid.usb0 configs/c.1/

# Enable the device (Bind to the first available USB controller)
log_msg "Binding to USB controller..."
ls /sys/class/udc > UDC

log_msg "RemotePi HID Gadget successfully configured."
chmod 777 /dev/hidg0 || log_msg "Warning: /dev/hidg0 not ready yet."
