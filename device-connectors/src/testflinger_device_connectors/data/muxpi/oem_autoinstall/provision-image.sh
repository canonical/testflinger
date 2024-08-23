#!/bin/bash

exec 2>&1
set -euox pipefail
#
# This script is used by TF agent to provision OEM PCs with Ubuntu Noble images
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
    exit
fi

TARGET_USER="ubuntu"
TARGET_IPS=()
ISO_PATH=""
ISO=""
URL_DUT=""
STORE_PART=""
TIMEOUT=3600
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
SSH="ssh $SSH_OPTS"
SCP="scp $SSH_OPTS"

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

create_sshd_conf() {
    # generates config to enable the exported authorized_keys file
    local filename=$1

    cat <<EOL > "$filename"
AuthorizedKeysFile .ssh/authorized_keys /etc/ssh/authorized_keys
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
    WGET_OPTS="--no-verbose --tries=3"
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

    echo "Downloading ISO on DUT..."
    if ! $SSH "$TARGET_USER"@"$addr" -- sudo wget "$WGET_OPTS" -O /home/"$TARGET_USER"/"$ISO" "$URL_DUT"; then
        echo "Downloading ISO on DUT failed."
        exit 4
    fi

    if ! $SSH "$TARGET_USER"@"$addr" -- sudo test -e /home/"$TARGET_USER"/"$ISO"; then
        echo "ISO file doesn't exist after downloading."
        exit 4
    fi
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



read -ra TARGET_IPS <<< "$@"

for addr in "${TARGET_IPS[@]}";
do
    # Clear the known host
    if [ -f "$HOME/.ssh/known_hosts" ]; then
        ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$addr"
    fi

    # Find the partitions
    while read -r name fstype mountpoint;
    do
        echo "$name,$fstype,$mountpoint"
        if [ "$fstype" = "ext4" ]; then
            if [ "$mountpoint" = "/home/$TARGET_USER" ] || [ "$mountpoint" = "/" ]; then
                STORE_PART="/dev/$name"
                break
            fi
        fi
    done < <($SSH "$TARGET_USER"@"$addr" -- lsblk -n -l -o NAME,FSTYPE,MOUNTPOINT)

    if [ -z "$STORE_PART" ]; then
        echo "Can't find partition to store ISO on target $addr"
        exit
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

    # ssh configs are expected to be deployed as a directory
    mkdir -p "$CONFIG_REPO_PATH"/ssh/sshd_config.d

    create_sshd_conf "$CONFIG_REPO_PATH"/ssh/sshd_config.d/pc_sanity.conf
    cp "$CONFIG_REPO_PATH"/authorized_keys "$CONFIG_REPO_PATH"/ssh || true  # optional file
    $SCP -r "$CONFIG_REPO_PATH"/ssh "$TARGET_USER"@"$addr":/home/"$TARGET_USER"/redeploy/ssh-config

    rm -rf "$CONFIG_REPO_PATH"/ssh

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

    $SSH "$TARGET_USER"@"$addr" -- sudo mount -o loop /home/"$TARGET_USER"/"$ISO" /home/"$TARGET_USER"/iso || true
    $SSH "$TARGET_USER"@"$addr" -- sudo mount "$RESET_PART" /home/"$TARGET_USER"/reset || true

    # Sync ISO to the reset partition
    $SSH "$TARGET_USER"@"$addr" -- sudo rsync -avP /home/"$TARGET_USER"/iso/ /home/"$TARGET_USER"/reset || true

    # Sync cloud-configs to the reset partition
    $SSH "$TARGET_USER"@"$addr" -- sudo mkdir -p /home/"$TARGET_USER"/reset/cloud-configs || true
    $SSH "$TARGET_USER"@"$addr" -- sudo cp -r /home/"$TARGET_USER"/redeploy/cloud-configs/redeploy/ /home/"$TARGET_USER"/reset/cloud-configs/
    $SSH "$TARGET_USER"@"$addr" -- sudo cp -r /home/"$TARGET_USER"/redeploy/ssh-config/ /home/"$TARGET_USER"/reset/
    $SSH "$TARGET_USER"@"$addr" -- sudo cp /home/"$TARGET_USER"/redeploy/cloud-configs/grub/redeploy.cfg /home/"$TARGET_USER"/reset/boot/grub/grub.cfg
    $SSH "$TARGET_USER"@"$addr" -- sudo sed -i "s/RP_PARTUUID/${RESET_PARTUUID}/" /home/"$TARGET_USER"/reset/boot/grub/grub.cfg

    # Reboot the target
    $SSH "$TARGET_USER"@"$addr" -- sudo reboot || true
done

# Clear the known hosts
for addr in "${TARGET_IPS[@]}";
do
    if [ -f "$HOME/.ssh/known_hosts" ]; then
        ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$addr"
    fi
done

# Polling the targets
STARTED=("${TARGET_IPS[@]}")
finished=0
startTime=$(date +%s)
while :;
do
    sleep 180
    currentTime=$(date +%s)
    if [[ $((currentTime - startTime)) -gt $TIMEOUT ]]; then
        echo "Timeout is reached, deployment was not finished"
        break
    fi

    for addr in "${STARTED[@]}";
    do
        if $SSH "$TARGET_USER"@"$addr" -- exit; then
            STARTED=("${STARTED[@]/$addr}")
            finished=$((finished + 1))
        fi
    done

    if [ $finished -eq ${#TARGET_IPS[@]} ]; then
        echo "Deployment is done"
        break
    fi
done
