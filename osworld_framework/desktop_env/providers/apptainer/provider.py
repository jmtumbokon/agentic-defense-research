import logging
import os
import subprocess
import time
import requests

from desktop_env.providers.base import Provider

logger = logging.getLogger("desktopenv.providers.apptainer.ApptainerProvider")
logger.setLevel(logging.INFO)

WAIT_TIME = 3
RETRY_INTERVAL = 5

class ApptainerProvider(Provider):
    def __init__(self, region: str):
        self.process = None
        self.server_port = 15000
        self.chromium_port = 19222
        self.vnc_port = 5900
        self.vlc_port = 18080
        self.sif_image = os.path.expanduser("~/research/osworld-docker_latest.sif")
        self.launch_script = os.path.expanduser("~/research/launch_osworld.sh")

    def _wait_for_vm_ready(self, timeout=600):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                r = requests.get(f"http://localhost:{self.server_port}/screenshot", timeout=(10,10))
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            logger.info("Waiting for VM to boot...")
            time.sleep(RETRY_INTERVAL)
        raise TimeoutError("VM failed to become ready")

    def start_emulator(self, path_to_vm, headless, os_type):
        logger.info("Starting QEMU via Apptainer...")
        overlay = "/tmp/osworld_storage/boot.qcow2"
        if os.path.exists(overlay):
            os.remove(overlay)
        cmd = ["apptainer", "exec", "--writable-tmpfs",
               "--bind", f"{os.path.abspath(path_to_vm)}:/System.qcow2:ro",
               self.sif_image, "bash", self.launch_script]
        logger.info(f"Launch: {' '.join(cmd)}")
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        logger.info(f"PID: {self.process.pid}")
        self._wait_for_vm_ready()

    def get_ip_address(self, path_to_vm):
        return f"localhost:{self.server_port}:{self.chromium_port}:{self.vnc_port}:{self.vlc_port}"

    def save_state(self, path_to_vm, snapshot_name):
        raise NotImplementedError("Snapshots not available for Apptainer provider")

    def revert_to_snapshot(self, path_to_vm, snapshot_name):
        self.stop_emulator(path_to_vm)

    def stop_emulator(self, path_to_vm, region=None, *args, **kwargs):
        if self.process:
            logger.info("Stopping QEMU...")
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping: {e}")
            finally:
                self.process = None
                overlay = "/tmp/osworld_storage/boot.qcow2"
                if os.path.exists(overlay):
                    os.remove(overlay)
            time.sleep(WAIT_TIME)
