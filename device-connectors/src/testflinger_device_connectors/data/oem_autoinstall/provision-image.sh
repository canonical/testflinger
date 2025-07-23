#!/bin/bash

exec 2>&1
set -euo pipefail
#
# This script is to provision OEM PCs with Ubuntu OEM images using Recovery Partition
# It checks if the ISO is valid and deploys it on the target
# It assumes that Recovery Partition exists on the target
#

usage()
{
cat <<EOF
Usage:
    $0 [OPTIONS] <TARGET_IP 1> <TARGET_IP 2> ...
Options:
    -h|--help        The manual of the script
    --iso-dut        URL to wget ISO on target DUT and deploy
    -u|--user        The user of the target, default ubuntu
    -o|--timeout     The timeout for doing the deployment, default 3600 seconds
    --iso            Local ISO file path to scp on target DUT and deploy
EOF
}

if [ $# -lt 3 ]; then
    usage
    exit 1
fi

TARGET_USER="ubuntu"
TARGET_PASSWORD="insecure"
ISO_PATH=""
ISO=""
CONFIG_REPO_PATH=""
URL_DUT=""
STORE_PART=""
TIMEOUT=3600
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
SSH="ssh $SSH_OPTS"
SCP="scp $SSH_OPTS"
SSH_WITH_PASS="sshpass -p $TARGET_PASSWORD ssh $SSH_OPTS"
create_redeploy_cfg() {
    # generates grub.cfg file to start the redeployment
    local filename=$1

    cat <<EOL > "$filename"
set timeout=3

loadfont unicode

set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

if [ -s (\$root)/boot/grub/theme/theme.cfg ]; then
        source (\$root)/boot/grub/theme/theme.cfg
fi

menuentry "Start redeployment" {
        set gfxpayload=keep
        linux   /casper/vmlinuz layerfs-path=minimal.standard.live.hotfix.squashfs nopersistent ds=nocloud\;s=/cdrom/cloud-configs/redeploy --- quiet splash nomodeset modprobe.blacklist=nouveau nouveau.modeset=0 autoinstall rp-partuuid=RP_PARTUUID
        initrd  /casper/initrd
}
menuentry "Start normal reset installation" {
        set gfxpayload=keep
        linux   /casper/vmlinuz layerfs-path=minimal.standard.live.hotfix.squashfs nopersistent ds=nocloud\;s=/cdrom/cloud-configs/reset-media --- quiet splash nomodeset modprobe.blacklist=nouveau nouveau.modeset=0
        initrd  /casper/initrd
}
grub_platform
if [ "\$grub_platform" = "efi" ]; then
menuentry 'UEFI firmware settings' {
        fwsetup
}
fi

EOL

    echo "'$filename' was generated with default content."
}

create_meta_data() {
    local filename=$1
    # currently meta-data is an empty file, but it's required by cloud-init
    touch "$filename"
}

wget_iso_on_dut() {
    # Download ISO on DUT
    URL_TOKEN="$CONFIG_REPO_PATH"/url_token

    echo "Downloading ISO on DUT..."
    if [[ "$URL_DUT" =~ "oem-share.canonical.com" ]]; then
        # use rclone for webdav storage
        if [ ! -f "$URL_TOKEN" ]; then
            echo "oem-share URL requires webdav authentication. Please attach token_file"
            exit 3
        fi
        $SCP "$URL_TOKEN" "$TARGET_USER"@"$addr":/home/"$TARGET_USER"/

        if ! $SSH "$TARGET_USER"@"$addr" -- sudo command -v rclone  >/dev/null 2>&1; then
            $SSH "$TARGET_USER"@"$addr" -- sudo sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
            $SSH "$TARGET_USER"@"$addr" -- sudo sudo DEBIAN_FRONTEND=noninteractive apt-get install -yqq rclone
        fi

        if [[ "$URL_DUT" =~ "partners" ]]; then
            PROJECT=$(echo "$URL_DUT" | cut -d "/" -f 5)
            FILEPATH=$(echo "$URL_DUT" | sed "s/.*share\///g")
        else
            PROJECT=$(echo "$URL_DUT" | cut -d "/" -f 5)
            FILEPATH=$(echo "$URL_DUT" | sed "s/.*$PROJECT\///g")
        fi

        if ! $SSH "$TARGET_USER"@"$addr" -- sudo rclone --config /home/"$TARGET_USER"/url_token copy "$PROJECT":"$FILEPATH" /home/"$TARGET_USER"/; then
            echo "Downloading ISO on DUT from oem-share failed."
            exit 4
        fi
    else
        WGET_OPTS="--tries=3 --progress=bar:force"
        # Optional URL credentials
        if [ -r "$URL_TOKEN" ]; then
            username=$(awk -F':' '/^username:/ {print $2}' "$URL_TOKEN" | xargs)
            token=$(awk -F':' '/^token:/ {print $2}' "$URL_TOKEN" | xargs)
            if [ -z "$username" ] || [ -z "$token" ]; then
                echo "Error: check username or token format in $URL_TOKEN file"
                exit 3
            fi
            WGET_OPTS+=" --auth-no-challenge --user=$username --password=$token"
        fi

        if ! $SSH "$TARGET_USER"@"$addr" -- sudo wget "$WGET_OPTS" -O /home/"$TARGET_USER"/"$ISO" "$URL_DUT"; then
            echo "Downloading ISO on DUT failed."
            exit 4
        fi
    fi

    if ! $SSH "$TARGET_USER"@"$addr" -- sudo test -e /home/"$TARGET_USER"/"$ISO"; then
        echo "ISO file doesn't exist after downloading."
        exit 4
    fi
}

is_valid_iso_on_dut() {
    local addr=$1
    local iso_path="/home/$TARGET_USER/$ISO"
    local exit_code=0

    # Ensure xorriso is installed
    if ! $SSH "$TARGET_USER@$addr" -- "command -v xorriso >/dev/null 2>&1"; then
        echo "Installing xorriso for ISO verification..."
        $SSH "$TARGET_USER@$addr" -- sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
        $SSH "$TARGET_USER@$addr" -- sudo DEBIAN_FRONTEND=noninteractive apt-get install -y xorriso
        if ! $SSH "$TARGET_USER@$addr" -- "command -v xorriso >/dev/null 2>&1"; then
            echo "ERROR: xorriso failed to install. Exit"
            return 1
        fi
    fi

    # Check if file is an ISO image
    if ! $SSH "$TARGET_USER@$addr" -- sudo file -b --mime-type "$iso_path" | grep -q "application/x-iso9660"; then
        echo "ERROR: File is not a valid ISO 9660 image or doesn't exist"
        return 1
    fi

    # Verify content
    local required_dirs=("'/cloud-configs/grub'" "'/sideloads'")  # should be oem specific
    local required_files=("'/casper/vmlinuz'" "'/casper/initrd'")

    for dir in "${required_dirs[@]}"; do
        if ! $SSH "$TARGET_USER@$addr" -- sudo xorriso -indev "$iso_path" -find / -type d 2>/dev/null | grep -qx "$dir"; then
            echo "ERROR: Required directory '$dir' not found in ISO"
            exit_code=1
        fi
    done

    for file in "${required_files[@]}"; do
        if ! $SSH "$TARGET_USER@$addr" -- sudo xorriso -indev "$iso_path" -find / -type f 2>/dev/null | grep -qx "$file"; then
            echo "ERROR: Required file '$file' not found in ISO"
            exit_code=1
        fi
    done

    if [ $exit_code -eq 0 ]; then
        echo "ISO verification passed"
    else
        echo "ERROR: ISO verification failed"
        echo "Removing invalid ISO from DUT"
        $SSH "$TARGET_USER@$addr" -- sudo rm -f "$iso_path"
    fi

    return $exit_code
}

is_unsigned_iso() {
    local iso_lower
    iso_lower="$(echo "$1" | tr '[:upper:]' '[:lower:]')"

    case "$iso_lower" in
        *next*)
            echo "Detected 'next' ISO image"
            return 0
            ;;
        *edge*)
            echo "Detected 'edge' ISO image"
            return 0
            ;;
    esac

    return 1
}


is_secure_boot_enabled() {
    local sb_status
    sb_status=$($SSH "$TARGET_USER@$addr" -- sudo mokutil --sb-state 2>&1)
    if [[ "$sb_status" == *"SecureBoot enabled"* ]]; then
        echo "Secure Boot is enabled on the system"
        return 0
    fi
    return 1
}

OPTS="$(getopt -o u:o:l: --long iso:,user:,timeout:,local-config:,iso-dut: -n 'provision-image.sh' -- "$@")"
eval set -- "${OPTS}"
while :; do
    case "$1" in
        ('-h'|'--help')
            usage
            exit;;
        ('--iso')
            ISO_PATH="$2"
            ISO=$(basename "$ISO_PATH")
            shift 2;;
        ('-u'|'--user')
            TARGET_USER="$2"
            shift 2;;
        ('-o'|'--timeout')
            TIMEOUT="$2"
            shift 2;;
        ('-l'|'--local-config')
            CONFIG_REPO_PATH="$2"
            shift 2;;
        ('--iso-dut')
            URL_DUT="$2"
            ISO=$(basename "$URL_DUT")
            shift 2;;
	('--') shift; break ;;
	(*) break ;;
    esac
done


# Get the target IP (should be the only remaining argument)
if [ $# -ne 1 ]; then
    echo "Error: Expected exactly one target IP address" >&2
    exit 1
fi
addr="$1"

# Clear the known host
if [ -f "$HOME/.ssh/known_hosts" ]; then
    ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$addr"
fi

# Find the partitions
while read -r name fstype mountpoint;
do
    #echo "$name,$fstype,$mountpoint"
    if [ "$fstype" = "ext4" ]; then
        if [ "$mountpoint" = "/home/$TARGET_USER" ] || [ "$mountpoint" = "/" ]; then
            STORE_PART="/dev/$name"
            break
        fi
    fi
done < <($SSH "$TARGET_USER"@"$addr" -- lsblk -n -l -o NAME,FSTYPE,MOUNTPOINT)

if [ -z "$STORE_PART" ]; then
    echo "Can't find partition to store ISO on target $addr"
    exit 1
fi

if is_unsigned_iso "$ISO" && is_secure_boot_enabled; then
    echo "Error: With Secure Boot enabled, unsigned ISO will fail to boot after provision"
    echo "Error: Consider disabling Secure Boot on DUT or use 'production', 'proposed' ISO"
    exit 6
fi

# Handle ISO
if [ -n "$URL_DUT" ]; then
    # store ISO directly on DUT
    wget_iso_on_dut
elif [ -n "$ISO_PATH" ]; then
    # ISO file was stored on agent; scp to DUT
    if [ ! -f "$ISO_PATH" ]; then
        echo "No designated ISO file"
        exit 2
    fi
    $SCP "$ISO_PATH" "$TARGET_USER"@"$addr":/home/"$TARGET_USER"
fi

if ! is_valid_iso_on_dut "$addr"; then
    echo "Only OEM Ubuntu images are supported"
    exit 5
fi

RESET_PART="${STORE_PART:0:-1}2"
RESET_PARTUUID=$($SSH "$TARGET_USER"@"$addr" -- lsblk -n -o PARTUUID "$RESET_PART")
EFI_PART="${STORE_PART:0:-1}1"

# Copy cloud-config redeploy to the target
$SSH "$TARGET_USER"@"$addr" -- mkdir -p /home/"$TARGET_USER"/redeploy/cloud-configs/redeploy
$SSH "$TARGET_USER"@"$addr" -- mkdir -p /home/"$TARGET_USER"/redeploy/cloud-configs/grub

$SCP "$CONFIG_REPO_PATH"/user-data "$TARGET_USER"@"$addr":/home/"$TARGET_USER"/redeploy/cloud-configs/redeploy/

if [ ! -r "$CONFIG_REPO_PATH"/meta-data ]; then
    create_meta_data "$CONFIG_REPO_PATH"/meta-data
fi
$SCP "$CONFIG_REPO_PATH"/meta-data "$TARGET_USER"@"$addr":/home/"$TARGET_USER"/redeploy/cloud-configs/redeploy/

if [ ! -r "$CONFIG_REPO_PATH"/redeploy.cfg ]; then
    create_redeploy_cfg "$CONFIG_REPO_PATH"/redeploy.cfg
fi
$SCP "$CONFIG_REPO_PATH"/redeploy.cfg "$TARGET_USER"@"$addr":/home/"$TARGET_USER"/redeploy/cloud-configs/grub/redeploy.cfg

# Umount the partitions
MOUNT=$($SSH "$TARGET_USER"@"$addr" -- lsblk -n -o MOUNTPOINT "$RESET_PART")
if [ -n "$MOUNT" ]; then
    $SSH "$TARGET_USER"@"$addr" -- sudo umount "$RESET_PART"
fi
MOUNT=$($SSH "$TARGET_USER"@"$addr" -- lsblk -n -o MOUNTPOINT "$EFI_PART")
if [ -n "$MOUNT" ]; then
    $SSH "$TARGET_USER"@"$addr" -- sudo umount "$EFI_PART"
fi

# Format partitions
$SSH "$TARGET_USER"@"$addr" -- sudo mkfs.vfat "$RESET_PART"
$SSH "$TARGET_USER"@"$addr" -- sudo mkfs.vfat "$EFI_PART"

# Mount ISO and reset partition
$SSH "$TARGET_USER"@"$addr" -- mkdir -p /home/"$TARGET_USER"/iso || true
$SSH "$TARGET_USER"@"$addr" -- mkdir -p /home/"$TARGET_USER"/reset || true

$SSH "$TARGET_USER"@"$addr" -- sudo mount -o loop /home/"$TARGET_USER"/"$ISO" /home/"$TARGET_USER"/iso || true
$SSH "$TARGET_USER"@"$addr" -- sudo mount "$RESET_PART" /home/"$TARGET_USER"/reset || true

# Sync ISO to the reset partition (output hidden due to many files)
$SSH "$TARGET_USER"@"$addr" -- sudo rsync -aP /home/"$TARGET_USER"/iso/ /home/"$TARGET_USER"/reset >/dev/null 2>&1 || true

# Sync cloud-configs to the reset partition
$SSH "$TARGET_USER"@"$addr" -- sudo mkdir -p /home/"$TARGET_USER"/reset/cloud-configs || true
$SSH "$TARGET_USER"@"$addr" -- sudo cp -r /home/"$TARGET_USER"/redeploy/cloud-configs/redeploy/ /home/"$TARGET_USER"/reset/cloud-configs/
$SSH "$TARGET_USER"@"$addr" -- sudo cp /home/"$TARGET_USER"/redeploy/cloud-configs/grub/redeploy.cfg /home/"$TARGET_USER"/reset/boot/grub/grub.cfg
$SSH "$TARGET_USER"@"$addr" -- sudo sed -i "s/RP_PARTUUID/${RESET_PARTUUID}/" /home/"$TARGET_USER"/reset/boot/grub/grub.cfg

# Reboot the target
$SSH "$TARGET_USER"@"$addr" -- sudo reboot || true

# Clear the known hosts
if [ -f "$HOME/.ssh/known_hosts" ]; then
    ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$addr"
fi

echo "Deployment will start after reboot"

# After provisioning, wait for the target to come back online
startTime=$(date +%s)
echo "Polling ssh connection status on $addr until timeout ($TIMEOUT seconds)..."

while :; do
    sleep 180
    currentTime=$(date +%s)
    if [[ $((currentTime - startTime)) -gt $TIMEOUT ]]; then
        echo "Timeout is reached, deployment is not finished on $addr."
        exit 1
    fi

    if $SSH_WITH_PASS "$TARGET_USER"@"$addr" -- echo "Connection Success"; then
        echo "$addr is back online. Deployment is done."
        break
    fi
done
