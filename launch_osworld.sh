#!/usr/bin/env bash
set -euo pipefail

QCOW2="/System.qcow2"
STORAGE="/tmp/osworld_storage"
mkdir -p "$STORAGE"

BOOT_DISK="$STORAGE/boot.qcow2"
if [ ! -f "$BOOT_DISK" ]; then
    echo "Creating overlay disk..."
    qemu-img create -f qcow2 -b "$QCOW2" -F qcow2 "$BOOT_DISK"
fi

VM_IP="20.20.20.21"
MAC_ADDR="02:11:32:AA:BB:CC"

ARGS=""
ARGS+=" -cpu max,l3-cache=on,+hypervisor,migratable=no,+ssse3,+sse4.1,+sse4.2"
ARGS+=" -smp 4,sockets=1,dies=1,cores=4,threads=1"
ARGS+=" -accel tcg,thread=multi"
ARGS+=" -m 4G"
ARGS+=" -machine type=q35,smm=off,graphics=off,vmport=off,dump-guest-core=off,hpet=off"
ARGS+=" -display vnc=:0,websocket=5700 -vga virtio"
ARGS+=" -netdev user,id=hostnet0,host=20.20.20.1,net=20.20.20.0/24,dhcpstart=${VM_IP},hostname=QEMU"
ARGS+=",hostfwd=tcp::15000-${VM_IP}:5000"
ARGS+=",hostfwd=tcp::19222-${VM_IP}:9222"
ARGS+=",hostfwd=tcp::18080-${VM_IP}:8080"
ARGS+=",hostfwd=tcp::2222-${VM_IP}:22"
ARGS+=",hostfwd=tcp::13389-${VM_IP}:3389"
ARGS+=" -device virtio-net-pci,romfile=,netdev=hostnet0,mac=${MAC_ADDR},id=net0"
ARGS+=" -drive file=${BOOT_DISK},format=qcow2,if=virtio,cache=writeback,aio=threads,discard=unmap"
ARGS+=" -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/edk2-x86_64-code.fd"
ARGS+=" -device qemu-xhci,id=xhci -device usb-tablet"
ARGS+=" -monitor telnet:localhost:7100,server,nowait,nodelay"
ARGS+=" -name osworld,process=osworld,debug-threads=on"
ARGS+=" -serial mon:stdio"
ARGS+=" -object rng-random,id=objrng0,filename=/dev/urandom"
ARGS+=" -device virtio-rng-pci,rng=objrng0,id=rng0,bus=pcie.0,addr=0x1c"
ARGS+=" -device virtio-balloon-pci,id=balloon0,bus=pcie.0,addr=0x4"

echo "Starting QEMU (TCG mode, no KVM)..."
echo "Ports: API=15000, Chrome=19222, VLC=18080, VNC=5900, WS=5700, SSH=2222"
exec qemu-system-x86_64 $ARGS
