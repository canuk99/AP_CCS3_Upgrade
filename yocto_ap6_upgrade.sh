#!/bin/sh

# upgrade AP from legacy flash layout to new yocto based flash layout
#
#old:
#0x000004000000-0x0000041e0000 : "kernel"
#0x0000041e0000-0x000004200000 : "dtb"
#0x000004200000-0x000004b00000 : "root"
#0x000004b00000-0x000005600000 : "onramp_sw"
#0x000005600000-0x000007e80000 : "user"
#0x000007e80000-0x000007f40000 : "factory"
#0x000007f40000-0x000007f60000 : "onramp_env"
#0x000007f60000-0x000007fa0000 : "env"
#0x000007fa0000-0x000008000000 : "u-boot"
#0x000000000000-0x000000020000 : "bootcount"
#0x000000020000-0x000000200000 : "failsafe-kernel"
#0x000000200000-0x000000220000 : "failsafe-dtb"
#0x000000220000-0x000000b20000 : "failsafe-root"
#0x000000b20000-0x0000033a0000 : "cache"
#
#
#
#new:
#0x000000000000-0x000002800000 : "image_1"
#0x000002800000-0x000005000000 : "image_2"
#0x000005000000-0x0000060a0000 : "rootfs_data"
#0x0000060a0000-0x000007e80000 : "orw_data"
#0x000007e80000-0x000007f40000 : "factory_cal"
#0x000007f40000-0x000007f60000 : "transition_data"
#0x000007f60000-0x000007f80000 : "bootenv_1"
#0x000007f80000-0x000007fa0000 : "bootenv_2"
#0x000007fa0000-0x000008000000 : "u-boot"



usage()
{
    echo "usage:"
    echo
    echo "$0 path_to_fw_file"
    echo
    exit 1
}

if [ -f /etc/issue ]; then
    grep -q Yocto /etc/issue
    if [ $? -eq 0 ]; then
        echo This AP has already been upgraded to the yocto distribution.  Use "ap_upgrade $1"
        exit 1
    fi
fi

grep -iq powerpc /proc/cpuinfo
if [ $? -ne 0 ]; then
    echo $0 should only be run on an AP6
    exit 1
fi

if [ ! -r "$1" ]; then
    usage
fi

UPGRADE_COMPLETE_FILE=/tmp/upgrade_complete

# turn on some verbosity
set -ex

if [ "$2" != "upgrade" ]; then
    #Rerun self with captured output
    $0 $1 upgrade 2>&1 | tee -i /tmp/yocto_upgrade.log
    if [ ! -f $UPGRADE_COMPLETE_FILE ]; then
        echo DO NOT REBOOT!!!  UPGRADE WAS NOT SUCCESSFUL!!!
        exit 1
    fi

    # Just reboot immediately.  AP is in a weird state right now.  Let's get sane...
    echo Done is the upgrade. Reboot the AP now I will.
    /sbin/reboot
    exit 0
fi


DIST_FILE=$1
STAGE_DIR=/tmp/upgrade

if [ ! -r $DIST_FILE ]; then
    echo invalid dist file: $DIST_FILE
    exit 1
fi

rm -rf $STAGE_DIR
mkdir -p $STAGE_DIR
tar xz -C $STAGE_DIR -f $DIST_FILE
cd $STAGE_DIR
echo Verifying image
openssl dgst -sha512 -verify /etc/ds_pubkey.pem -signature dist.sha512 crap.tgz 2>/dev/null
if [ $? -ne 0 ]; then
    echo failed to verify dist file
    exit 1
fi

echo Collecting transition data
#make the folder with ipconfig.db, config.db and text file containing mac address
RESTORE=cfg2restore
mkdir -p $RESTORE
rm -f $RESTORE/*
cd $RESTORE
sqlite3 /var/onramp/ipconfig.db .dump|sqlite3 ipconfig.db
# sqlite seems to not free up the space after removing the code download image.
# Recreating it seems to work
cp -p /onramp/db/config.db temp.db
sqlite3 temp.db "update code_download set image=X'00', cmac=X'00000000000000000000000000000000'"
sqlite3 temp.db .dump|sqlite3 config.db
rm -f temp.db
/sbin/ifconfig | head -n 1 | awk '{ print $5 }' > macaddr
grep root /etc/shadow |awk -F : '{print $2}' >root_passwd
grep admin /etc/shadow |awk -F : '{print $2}' >admin_passwd
cp -p /mnt/onramp/etc/.htpasswd htpasswd
cp -p /onramp/bin/orw.pem orw.pem
cp -p /onramp/bin/ap.pem ap.pem
cp -p /onramp/bin/key.pem key.pem
cp -p /mnt/onramp/etc/conf/onramp_cert.pem onramp_cert.pem
if [ -d ~/.ssh ]; then
    cp -pLr ~/.ssh dot_ssh || true
fi
cp -p /etc/conf/resolv.conf resolv.conf
cp -p  /etc/conf/ether.conf ether.conf
cd ..

#test for size, leaving some of the 128k left for the log file
tar pczf $RESTORE.tgz $RESTORE
TAR_SIZE=`stat -c '%s' $RESTORE.tgz`
if [ $TAR_SIZE -gt 100000 ]; then
    echo config size of $TAR_SIZE is too big
    echo ain\'t gonna upgrade
    exit 1
fi
# remove and rebuild later with log file included
rm -f $RESTORE.tgz

# free up some memory and prep for upgrade
stop_respawn || true
killall -9 cmn_logger || true
killall -9 mini_httpd || true

rm -f /tmp/ap.log*

# we'll be overwriting these partitions
umount /mnt/jffs2 || true
umount /mnt/cache || true

tar xzf crap.tgz

#don't really need to erase these.  will be erased later
#/usr/bin/mtd_debug erase /dev/mtd0 0x0 0x1e0000
#/usr/bin/mtd_debug erase /dev/mtd1 0x0 0x20000
#/usr/bin/mtd_debug erase /dev/mtd2 0x0 0x900000
#/usr/bin/mtd_debug erase /dev/mtd3 0x0 0xb00000
#/usr/bin/mtd_debug erase /dev/mtd4 0x0 0x2880000
# skip locked cal data /dev/mtd5

# unlock uboot env
echo Unlocking uboot environment
/onramp/bin/flash_enter_password -h 0xE4579FFC74E03781
/onramp/bin/flash_partition_unlock env

# update uboot
echo Erasing uboot
UBOOT_SIZE=`stat -c '%s' u-boot.bin`
/usr/bin/mtd_debug erase /dev/mtd8 0x0 0x60000
echo Writing uboot
/usr/bin/mtd_debug write /dev/mtd8 0x0 $UBOOT_SIZE u-boot.bin

# erase uboot env
echo Erasing uboot environment
/usr/bin/mtd_debug erase /dev/mtd7 0x0 0x40000

# erase image1
echo Erasing /dev/mtd9
/usr/bin/mtd_debug erase /dev/mtd9 0x0 0x20000
echo Erasing /dev/mtd10
/usr/bin/mtd_debug erase /dev/mtd10 0x0 0x1e0000
echo Erasing /dev/mtd11
/usr/bin/mtd_debug erase /dev/mtd11 0x0 0x20000
echo Erasing /dev/mtd12
/usr/bin/mtd_debug erase /dev/mtd12 0x0 0x900000
echo Erasing /dev/mtd13
/usr/bin/mtd_debug erase /dev/mtd13 0x0 0x2880000


echo Writing FIT image
# fragment based on current layout and put FIT image in what will be image1
export BYTES_WRITTEN=0
export MTD_NUM=9
FIT_IMAGE=fitImage-ingenu-image-ap-rev5.bin
BYTES_TO_WRITE=`stat -c '%s' $FIT_IMAGE`
TMP_CHUNK=fit_chunk
MTD_SIZES=0x20000,0x1e0000,0x20000,0x900000,0x2880000
CHUNK_NUM=1
BLOCK_SIZE=131072

while [ $BYTES_WRITTEN -lt $BYTES_TO_WRITE ]; do
    BYTES_LEFT=`expr $BYTES_TO_WRITE - $BYTES_WRITTEN`
    MTD_SIZE=`echo $MTD_SIZES | awk -F , "{print \\$$CHUNK_NUM}"`
    MTD_SIZE=`printf "%d" $MTD_SIZE` # to decimal

    echo Writing $MTD_SIZE bytes to /dev/mtd$MTD_NUM from offset $BYTES_WRITTEN

    rm -f $TMP_CHUNK
    if [ $MTD_SIZE -gt $BYTES_LEFT ]; then
        # note below expr exits with fail if numerator is 0, hence "|| true"

        # handle full blocks (faster)
        COUNT=`expr $BYTES_LEFT / $BLOCK_SIZE || true`
        SKIP=`expr $BYTES_WRITTEN / $BLOCK_SIZE || true`
        dd if=$FIT_IMAGE of=$TMP_CHUNK bs=$BLOCK_SIZE count=$COUNT skip=$SKIP

        # now handle partial block
        SEEK=`expr $COUNT \* $BLOCK_SIZE`
        COUNT=`expr $BYTES_TO_WRITE % $BLOCK_SIZE || true`
        SKIP=`expr $BYTES_TO_WRITE - $COUNT || true`
        dd conv=notrunc if=$FIT_IMAGE of=$TMP_CHUNK bs=1 count=$COUNT seek=$SEEK skip=$SKIP

        # now fill out to MTD size
        dd conv=notrunc if=/dev/zero of=$TMP_CHUNK bs=1 count=1 seek=`expr $MTD_SIZE - 1`
    else
        COUNT=`expr $MTD_SIZE / $BLOCK_SIZE`
        SKIP=`expr $BYTES_WRITTEN / $BLOCK_SIZE || true`
        dd if=$FIT_IMAGE of=$TMP_CHUNK bs=$BLOCK_SIZE count=$COUNT skip=$SKIP
    fi

    mtd_debug write /dev/mtd$MTD_NUM 0 ${MTD_SIZE} $TMP_CHUNK
    rm -f $TMP_CHUNK
    BYTES_WRITTEN=`expr ${BYTES_WRITTEN} + $MTD_SIZE`
    MTD_NUM=`expr $MTD_NUM + 1`
    CHUNK_NUM=`expr $CHUNK_NUM + 1`
done


cp /tmp/yocto_upgrade.log $RESTORE


#Tar it and resize to the size of the partition
tar pczf $RESTORE.tgz $RESTORE
TAR_SIZE=`stat -c '%s' $RESTORE.tgz`
if [ $TAR_SIZE -gt 131071 ]; then
    echo UPGRADE FAILED!!!  DO NOT REBOOT!!!
    echo config size of $TAR_SIZE is too big
    exit 1
fi
dd if=/dev/zero of=$RESTORE.tgz bs=1 count=1 seek=131071
rm -rf $RESTORE

echo Erasing transition data
/usr/bin/mtd_debug erase /dev/mtd6 0 0x20000

echo Writing transition data
/usr/bin/mtd_debug write /dev/mtd6 0 0x20000 $RESTORE.tgz 2>&1

touch $UPGRADE_COMPLETE_FILE
