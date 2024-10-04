#!/bin/bash
set -ex

jenkins_job_for_iso=""
jenkins_job_build_no="lastSuccessfulBuild"
script_on_target_machine="inject_recovery_from_iso.sh"
additional_grub_for_ubuntu_recovery="99_ubuntu_recovery"
user_on_target="ubuntu"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
SSH="ssh $SSH_OPTS"
SCP="scp $SSH_OPTS"
#TAR="tar -C $temp_folder"
temp_folder="$(mktemp -d -p "$PWD")"
GIT="git -C $temp_folder"
ubuntu_release=""
enable_sb="no"
dut_iso_url=""
dut_iso=""

enable_secureboot() {
    if [ "${ubr}" != "yes" ] && [ "$enable_sb" = "yes" ]; then
        ssh -o StrictHostKeyChecking=no "$user_on_target"@"$target_ip" sudo sb_fixup
        ssh -o StrictHostKeyChecking=no "$user_on_target"@"$target_ip" sudo reboot
    fi
}

clear_all() {
    rm -rf "$temp_folder"
    # remove Ubiquity in the end to match factory and Stock Ubuntu image behavior.
    # and it also workaround some debsum error from ubiquity.
    ssh -o StrictHostKeyChecking=no "$user_on_target"@"$target_ip" sudo apt-get -o DPkg::Lock::Timeout=-1 purge -y ubiquity
}
trap clear_all EXIT
# shellcheck disable=SC2046
eval set -- $(getopt -o "su:c:j:b:t:h" -l "local-iso:,dut-iso-url:,sync,url:,jenkins-credential:,jenkins-job:,jenkins-job-build-no:,oem-share-url:,oem-share-credential:,target-ip:,ubr,enable-secureboot,inject-ssh-key:,help" -- "$@")

usage() {
    set +x
cat << EOF
Usage:
    # This triggers sync job, downloads the image from oem-share, upload the
    # image to target DUT, and starts recovery.
    $(basename "$0") \\
        -s -u http://10.102.135.50:8080 \\
        -c JENKINS_USERNAME:JENKINS_CREDENTIAL \\
            -j dell-bto-jammy-jellyfish -b 17 \\
        --oem-share-url https://oem-share.canonical.com/share/lyoncore/jenkins/job \\
        --oem-share-credential OEM_SHARE_USERNAME:OEM_SHARE_PASSWORD \\
        -t 192.168.101.68

    # This downloads the image from Jenkins, upload the image to target DUT,
    # and starts recovery.
    $(basename "$0") \\
        -u 10.101.46.50 \\
        -j dell-bto-jammy-jellyfish -b 17 \\
        -t 192.168.101.68

    # This upload the image from local to target DUT, and starts recovery.
    $(basename "$0") \\
        --local-iso ./dell-bto-jammy-jellyfish-X10-20220519-17.iso \\
        -t 192.168.101.68

    # This upload the image from local to target DUT, and starts recovery.  The
    # image is using ubuntu-recovery.
    $(basename "$0") \\
        --local-iso ./pc-stella-cmit-focal-amd64-X00-20210618-1563.iso \\
        --ubr -t 192.168.101.68

Limition:
    It will failed when target recovery partition size smaller than target iso
    file.

The assumption of using this tool:
 - An root account 'ubuntu' on target machine.
 - The root account 'ubuntu' can execute command with root permission with
   \`sudo\` without password.
 - Host executing this tool can access target machine without password over ssh.

OPTIONS:
    --local-iso
      Use local

    -s | --sync
      Trigger sync job \`infrastructure-swift-client\` in Jenkins in --url,
      then download image from --oem-share-url.

    -u | --url
      URL of jenkins server.

    -c | --jenkins-credential
      Jenkins credential in the form of username:password, used with --sync.

    -j | --jenkins-job
      Get iso from jenkins-job.

    -b | --jenkins-job-build-no
      The build number of the Jenkins job assigned by --jenkins-job.

    --oem-share-url
      URL of oem-share, used with --sync.

    --oem-share-credential
      Credential in the form of username:password of lyoncore, used with --sync.

    -t | --target-ip
      The IP address of target machine. It will be used for ssh accessing.
      Please put your ssh key on target machine. This tool no yet support
      keyphase for ssh.

    --enable-secureboot
      Enable Secure Boot. When this option is on, the script will not install
      file that prevents turning on Secure Boot after installation. Only
      effective with dell-recovery images that enables Secure Boot on
      Somerville platforms.

    --ubr
      DUT which using ubuntu recovery (volatile-task).

    --inject-ssh-key
      Path to ssh key to inject into the target machine.

    -h | --help
      Print this message
EOF
    set -x
exit 1
}

download_preseed() {
    echo " == download_preseed == "
    if [ "${ubr}" == "yes" ]; then
        if [ "$enable_sb" = "yes" ]; then
            echo "error: --enable-secureboot does not apply to ubuntu-recovery images"
            exit 1
        fi
        # TODO: sync togother
        # replace $GIT clone https://git.launchpad.net/~oem-solutions-engineers/pc-enablement/+git/oem-fix-misc-cnl-no-secureboot --depth 1
        # Why need it?
        # reokace $GIT clone https://git.launchpad.net/~oem-solutions-engineers/pc-enablement/+git/oem-fix-misc-cnl-skip-storage-selecting --depth 1
        mkdir "$temp_folder/preseed/"
        echo "# Ubuntu Recovery configuration preseed

ubiquity ubuntu-oobe/user-interface string dynamic
ubiquity ubuntu-recovery/recovery_partition_filesystem string 0c
ubiquity ubuntu-recovery/active_partition string 1
ubiquity ubuntu-recovery/dual_boot_layout string primary
ubiquity ubuntu-recovery/disk_layout string gpt
ubiquity ubuntu-recovery/swap string dynamic
ubiquity ubuntu-recovery/dual_boot boolean false
ubiquity ubiquity/reboot boolean true
ubiquity ubiquity/poweroff boolean false
ubiquity ubuntu-recovery/recovery_hotkey/partition_label string PQSERVICE
ubiquity ubuntu-recovery/recovery_type string dev
" | tee ubuntu-recovery.cfg
        mv ubuntu-recovery.cfg "$temp_folder/preseed"
        $SCP "$user_on_target"@"$target_ip":/cdrom/preseed/project.cfg ./
        sed -i 's%ubiquity/reboot boolean false%ubiquity/reboot boolean true%' ./project.cfg
        sed -i 's%ubiquity/poweroff boolean true%ubiquity/poweroff boolean false%' ./project.cfg
        mv project.cfg "$temp_folder/preseed"

        mkdir -p "$temp_folder/oem-fix-set-local-repo/scripts/chroot-scripts/fish/"
        mkdir -p "$temp_folder/oem-fix-set-local-repo/scripts/chroot-scripts/os-post/"
        cat <<EOF > "$temp_folder/oem-fix-set-local-repo/scripts/chroot-scripts/fish/00-setup-local-repo"
#!/bin/bash -ex
# setup local repo
mkdir /tmp/cdrom_debs
apt-ftparchive packages /cdrom/debs > /tmp/cdrom_debs/Packages
echo 'deb [ trusted=yes ] file:/. /tmp/cdrom_debs/' >> /etc/apt/sources.list.d/$(basename "$0")_$$.list
sudo apt-get update
EOF

        cat <<EOF > "$temp_folder/oem-fix-set-local-repo/scripts/chroot-scripts/os-post/99-remove-local-repo"
#!/bin/bash -ex
# remove local repo
rm -f /etc/apt/sources.list.d/$(basename "$0")_$$.list
sudo apt update
EOF
    else
        # get checkbox pkgs and prepare-checkbox
        # get pkgs to skip OOBE
        if [ "$enable_sb" = "yes" ]; then
            $GIT clone  https://git.launchpad.net/~oem-solutions-engineers/pc-enablement/+git/oem-fix-misc-cnl-install-sbhelper --depth 1
        else
            $GIT clone https://git.launchpad.net/~oem-solutions-engineers/pc-enablement/+git/oem-fix-misc-cnl-no-secureboot --depth 1
        fi
        $GIT clone https://git.launchpad.net/~oem-solutions-engineers/pc-enablement/+git/oem-fix-misc-cnl-skip-storage-selecting --depth 1
    fi

    # install packages related to skip oobe
    skip_oobe_branch="master"
    if [ -n "$ubuntu_release" ]; then
        # set ubuntu_release to jammy or focal, depending on detected release
        skip_oobe_branch="$ubuntu_release"
    fi
    $GIT clone https://git.launchpad.net/~oem-solutions-engineers/pc-enablement/+git/oem-fix-misc-cnl-skip-oobe --depth 1 -b "$skip_oobe_branch"
    # get pkgs for ssh key and skip disk checking.
    $GIT clone https://git.launchpad.net/~oem-solutions-engineers/pc-enablement/+git/oem-fix-misc-cnl-misc-for-automation --depth 1 misc_for_automation

    if [ "${ubr}" == "yes" ]; then
    mkdir -p "$temp_folder"/preseed
    cat <<EOF1 > "$temp_folder/preseed/$additional_grub_for_ubuntu_recovery"
#!/bin/bash -e
source /usr/lib/grub/grub-mkconfig_lib
cat <<EOF
menuentry "ubuntu-recovery restore" --hotkey f9 {
        search --no-floppy --hint '(hd0,gpt2)' --set --fs-uuid UUID_OF_RECOVERY_PARTITION
        if [ -s /boot/grub/common.cfg ]; then
            source /boot/grub/common.cfg
        else
            set options="boot=casper automatic-ubiquity noprompt nomodeset quiet splash"
        fi

        #Support starting from a loopback mount (Only support ubuntu.iso for filename)
        if [ -f /ubuntu.iso ]; then
            loopback loop /ubuntu.iso
            set root=(loop)
            set options="\\\$options iso-scan/filename=/ubuntu.iso"
        fi
        if [ -n "\\\${lang}" ]; then
            set options="\\\$options locale=\\\$lang"
        fi

        linux   /casper/vmlinuz ubuntu-recovery/recovery_type=hdd \\\$options
        initrd  /casper/initrd
}
EOF
EOF1
    cat <<EOF > "$temp_folder/preseed/set_env_for_ubuntu_recovery"
#!/bin/bash -ex
# replace the grub entry which ubuntu_recovery expected
recover_p=\$(lsblk -l | grep efi | cut -d ' ' -f 1 | sed 's/.$/2'/)
UUID_OF_RECOVERY_PARTITION=\$(ls -l /dev/disk/by-uuid/ | grep \$recover_p | awk '{print \$9}')
echo partition = \$UUID_OF_RECOVERY_PARTITION
sed -i "s/UUID_OF_RECOVERY_PARTITION/\$UUID_OF_RECOVERY_PARTITION/" push_preseed/preseed/$additional_grub_for_ubuntu_recovery
sudo rm -f /etc/grub.d/99_dell_recovery || true
chmod 766 push_preseed/preseed/$additional_grub_for_ubuntu_recovery
sudo cp push_preseed/preseed/$additional_grub_for_ubuntu_recovery /etc/grub.d/

# Force changing the recovery partition label to PQSERVICE for ubuntu-recovery
sudo fatlabel /dev/\$recover_p PQSERVICE
EOF
    fi

    return 0
}
push_preseed() {
    echo " == download_preseed == "
    $SSH "$user_on_target"@"$target_ip" rm -rf push_preseed
    $SSH "$user_on_target"@"$target_ip" mkdir -p push_preseed
    $SSH "$user_on_target"@"$target_ip" touch push_preseed/SUCCSS_push_preseed
    $SSH "$user_on_target"@"$target_ip" sudo rm -f /cdrom/SUCCSS_push_preseed

    if [ "${ubr}" == "yes" ]; then
        $SCP -r "$temp_folder/preseed" "$user_on_target"@"$target_ip":~/push_preseed || $SSH "$user_on_target"@"$target_ip" sudo rm -f push_preseed/SUCCSS_push_preseed
        folders=(
            "oem-fix-set-local-repo"
        )
    else
        folders=(
            "oem-fix-misc-cnl-skip-storage-selecting"
        )
        if [ "$enable_sb" = "yes" ]; then
            folders+=("oem-fix-misc-cnl-install-sbhelper")
        else
            folders+=("oem-fix-misc-cnl-no-secureboot")
        fi
    fi

    folders+=("misc_for_automation" "oem-fix-misc-cnl-skip-oobe")

    for folder in "${folders[@]}"; do
        tar -C "$temp_folder/$folder" -zcvf "$temp_folder/$folder".tar.gz .
        $SCP "$temp_folder/$folder".tar.gz "$user_on_target"@"$target_ip":~
        $SSH "$user_on_target"@"$target_ip" tar -C push_preseed -zxvf "$folder".tar.gz || $SSH "$user_on_target"@"$target_ip" sudo rm -f push_preseed/SUCCSS_push_preseed
    done

    $SSH "$user_on_target"@"$target_ip" sudo cp -r push_preseed/* /cdrom/
    return 0
}
inject_preseed() {
    echo " == inject_preseed == "
    $SSH "$user_on_target"@"$target_ip" rm -rf /tmp/SUCCSS_inject_preseed
    download_preseed && \
    push_preseed
    $SCP "$user_on_target"@"$target_ip":/cdrom/SUCCSS_push_preseed "$temp_folder" || usage

    if [ "${ubr}" == "yes" ]; then
        $SSH "$user_on_target"@"$target_ip" bash \$HOME/push_preseed/preseed/set_env_for_ubuntu_recovery || usage
    fi
    $SSH "$user_on_target"@"$target_ip" touch /tmp/SUCCSS_inject_preseed
}

download_image() {
    img_path=$1
    img_name=$2
    user=$3

    MAX_RETRIES=10
    local retries=0

    echo "downloading $img_name from $img_path"
    curl_cmd=(curl --retry 3 --fail --show-error)
    if [ -n "$user" ]; then
        curl_cmd+=(--user "$user")
    fi

    pushd "$temp_folder"

    while [ "$retries" -lt "$MAX_RETRIES" ]; do
        ((retries+=1)) || true # arithmetics, see https://www.shellcheck.net/wiki/SC2219
        echo "Downloading checksum and image, tries $retries/$MAX_RETRIES"
        "${curl_cmd[@]}" -O "$img_path/$img_name".md5sum || true
        "${curl_cmd[@]}" -O "$img_path/$img_name" || true
        if md5sum -c "$img_name".md5sum; then
            break
        fi
        sleep 10; continue
    done

    if [ "$retries" -ge "$MAX_RETRIES" ]; then
        echo "error: max retries reached"
        exit 1
    fi

    local_iso="$PWD/$img_name"

    popd
}

download_from_jenkins() {
    path="ftp://$jenkins_url/jenkins_host/jobs/$jenkins_job_for_iso/builds/$jenkins_job_build_no/archive/out"
    img_name=$(wget -q "$path/" -O - | grep -o 'href=.*iso"' | awk -F/ '{print $NF}' | tr -d \")
    download_image "$path" "$img_name"
}

sync_to_swift() {
    if [ -z "$jenkins_url" ] ; then
        echo "error: --url not set"
        exit 1
    elif [ -z "$jenkins_credential" ]; then
        echo "error: --jenkins-credential not set"
        exit 1
    elif [ -z "$jenkins_job_for_iso" ]; then
        echo "error: --jenkins-job not set"
        exit 1
    elif [ -z "$jenkins_job_build_no" ]; then
        echo "error: --jenkins-job-build-no not set"
        exit 1
    elif [ -z "$oem_share_url" ]; then
        echo "error: --oem-share-url not set"
        exit 1
    elif [ -z "$oem_share_credential" ]; then
        echo "error: --oem-share-credential not set"
        exit 1
    fi

    jenkins_job_name="infrastructure-swift-client"
    jenkins_job_url="$jenkins_url/job/$jenkins_job_name/buildWithParameters"
    curl_cmd=(curl --retry 3 --max-time 10 -sS)
    headers_path="$temp_folder/build_request_headers"

    echo "sending build request"
    "${curl_cmd[@]}" --user "$jenkins_credential" -X POST -D "$headers_path" "$jenkins_job_url" \
        --data option=sync \
        --data "jenkins_job=$jenkins_job_for_iso" \
        --data "build_no=$jenkins_job_build_no"

    echo "getting job id from queue"
    queue_url=$(grep '^Location: ' "$headers_path" | awk '{print $2}' | tr -d '\r')
    duration=0
    timeout=600
    url=
    until [ -n "$timeout" ] && [[ $duration -ge $timeout ]]; do
        url=$("${curl_cmd[@]}" --user "$jenkins_credential" "${queue_url}api/json" | jq -r '.executable | .url')
        if [ "$url" != "null" ]; then
            break
        fi
        sleep 5
        duration=$((duration+5))
    done
    if [ "$url" = "null" ]; then
        echo "error: sync job was not created in time"
        exit 1
    fi

    echo "polling build status"
    duration=0
    timeout=1800
    until [ -n "$timeout" ] && [[ $duration -ge $timeout ]]; do
        result=$("${curl_cmd[@]}" --user "$jenkins_credential" "${url}api/json" | jq -r .result)
        if [ "$result" = "SUCCESS" ]; then
            break
        fi
        if [ "$result" = "FAILURE" ]; then
            echo "error: sync job failed"
            exit 1
        fi
        sleep 30
        duration=$((duration+30))
    done
    if [ "$result" != "SUCCESS" ]; then
        echo "error: sync job has not been done in time"
        exit 1
    fi

    oem_share_path="$oem_share_url/$jenkins_job_for_iso/$jenkins_job_build_no"
    img_name=$(curl -sS --user "$oem_share_credential" "$oem_share_path/" | grep -o 'href=.*iso"' | tr -d \")
    img_name=${img_name#"href="}
    download_image "$oem_share_path" "$img_name" "$oem_share_credential"
}

wget_iso_on_dut() {
    # Download ISO on DUT
    WGET_OPTS="--no-verbose --tries=3 --no-check-certificate"
    dut_iso="$(basename "$dut_iso_url")"
    echo "Downloading ISO on DUT..."
    if ! $SSH "$user_on_target"@"$target_ip" -- sudo wget "$WGET_OPTS" -O /home/"$user_on_target"/"$dut_iso" "$dut_iso_url"; then
        echo "Downloading ISO on DUT failed."
        exit 4
    fi

    if ! $SSH "$user_on_target"@"$target_ip" -- sudo test -e /home/"$user_on_target"/"$dut_iso"; then
        echo "ISO file doesn't exist after downloading."
        exit 4
    fi
    # successfully downloaded the file
}


download_iso() {
    if [ "$enable_sync_to_swift" = true ]; then
        sync_to_swift
    elif [ -n "$dut_iso_url" ]; then
        wget_iso_on_dut
    else
        download_from_jenkins
    fi

}

inject_recovery_iso() {
    if [ -z "$local_iso" ]; then
        download_iso
    fi

    if [ -n "$dut_iso" ]; then
        img_name="$dut_iso"
    else
        img_name="$(basename "$local_iso")"
    fi

    if [ -z "${img_name##*stella*}" ] ||
       [ -z "${img_name##*sutton*}" ]; then
        ubr="yes"
    fi
    if [ -z "${img_name##*jammy*}" ]; then
        ubuntu_release="jammy"
    elif [ -z "${img_name##*focal*}" ]; then
        ubuntu_release="focal"
    fi
    rsync_opts="--exclude=efi --delete --temp-dir=/var/tmp/rsync"

    if [ -n "$local_iso" ]; then
        $SCP "$local_iso" "$user_on_target"@"$target_ip":~/
    fi
    # by now, $dut_iso already present on the DUT
cat <<EOF > "$temp_folder/$script_on_target_machine"
#!/bin/bash
set -ex
sudo umount /cdrom /mnt || true
sudo mount -o loop $img_name /mnt && \
recover_p=\$(lsblk -l | grep efi | cut -d ' ' -f 1 | sed 's/.$/2'/) && \
sudo mount /dev/\$recover_p /cdrom && \
df | grep "cdrom\|mnt" | awk '{print \$2" "\$6}' | sort | tail -n1 | grep -q cdrom && \
sudo mkdir -p /var/tmp/rsync && \
sudo rsync -alv /mnt/ /cdrom/ $rsync_opts && \
sudo cp /mnt/.disk/ubuntu_dist_channel /cdrom/.disk/ && \
touch /tmp/SUCCSS_inject_recovery_iso
EOF
    $SCP "$temp_folder"/"$script_on_target_machine" "$user_on_target"@"$target_ip":~/
    $SSH "$user_on_target"@"$target_ip" chmod +x "\$HOME/$script_on_target_machine"
    $SSH "$user_on_target"@"$target_ip" "\$HOME/$script_on_target_machine"
    $SCP "$user_on_target"@"$target_ip":/tmp/SUCCSS_inject_recovery_iso "$temp_folder" || usage
}
prepare() {
    echo "prepare"
    inject_recovery_iso
    inject_preseed
}

inject_ssh_key() {
    while(:); do
        echo "Attempting to inject ssh key"
        if [ "$(sshpass -p u ssh-copy-id $SSH_OPTS -f -i "$ssh_key" "$user_on_target@$target_ip")" ] ; then
            break
        fi
        sleep 180
    done
}

poll_recovery_status() {
    while(:); do
        if [ "$($SSH "$user_on_target"@"$target_ip"  systemctl is-active ubiquity)" = "inactive" ] ; then
           break
        fi
        sleep 180
    done
}

do_recovery() {
    if [ "${ubr}" == "yes" ]; then
        echo GRUB_DEFAULT='"ubuntu-recovery restore"' | $SSH "$user_on_target"@"$target_ip" -T "sudo tee -a /etc/default/grub.d/automatic-oem-config.cfg"
        echo GRUB_TIMEOUT_STYLE=menu | $SSH "$user_on_target"@"$target_ip" -T "sudo tee -a /etc/default/grub.d/automatic-oem-config.cfg"
        echo GRUB_TIMEOUT=5 | $SSH "$user_on_target"@"$target_ip" -T "sudo tee -a /etc/default/grub.d/automatic-oem-config.cfg"
        $SSH "$user_on_target"@"$target_ip" sudo update-grub
        $SSH "$user_on_target"@"$target_ip" sudo reboot &
    else
        $SSH "$user_on_target"@"$target_ip" sudo dell-restore-system -y &
    fi
    sleep 300 # sleep to make sure the target system has been rebooted to recovery mode.
    if [ -n "$ssh_key" ]; then
        inject_ssh_key
    fi
    poll_recovery_status
}

main() {
    while [ $# -gt 0 ]
    do
        case "$1" in
            --local-iso)
                shift
                local_iso="$1"
                ;;
            --dut-iso-url)
                shift
                dut_iso_url="$1"
                ;;
            -s | --sync)
                enable_sync_to_swift=true
                ;;
            -u | --url)
                shift
                jenkins_url="$1"
                ;;
            -c | --jenkins-credential)
                shift
                jenkins_credential="$1"
                ;;
            -j | --jenkins-job)
                shift
                jenkins_job_for_iso="$1"
                ;;
            -b | --jenkins-job-build-no)
                shift
                jenkins_job_build_no="$1"
                ;;
            --oem-share-url)
                shift
                oem_share_url="$1"
                ;;
            --oem-share-credential)
                shift
                oem_share_credential="$1"
                ;;
            -t | --target-ip)
                shift
                target_ip="$1"
                ;;
            --ubr)
                ubr="yes"
                ;;
            --enable-secureboot)
                enable_sb="yes"
                ;;
            --inject-ssh-key)
                shift
                ssh_key="$1"
                ;;
            -h | --help)
                usage 0
                exit 0
                ;;
            --)
                ;;
            *)
                echo "Not recognize $1"
                usage
                exit 1
                ;;
           esac
           shift
    done
    prepare
    do_recovery
    clear_all
    enable_secureboot
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
