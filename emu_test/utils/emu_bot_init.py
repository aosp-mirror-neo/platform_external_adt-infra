import os
import platform
import argparse
import shutil
from subprocess import PIPE,STDOUT
import psutil
import logging

parser = argparse.ArgumentParser(description='Download and unzip a list of files separated by comma')
parser.add_argument('--build-dir', dest='build_dir', action='store',
                    help='full path to build directory')
parser.add_argument('--log-dir', dest='log_dir', action='store',
                    help='full path to log directory')

args = parser.parse_args()

log_formatter = logging.Formatter('%(message)s')
if not os.path.exists(args.log_dir):
  os.makedirs(args.log_dir)
file_handler = logging.FileHandler(os.path.join(args.log_dir, "init_bot.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

logger = logging.getLogger()
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

def clean_up():
  """clean up build directory and qemu-gles-[pid] files"""

  # remove qemu-gles-[pid] files
  host = platform.system()
  if host in ["Linux", "Darwin"]:
    tmp_dir = "/tmp/android-%s" % os.environ["USER"]
    if os.path.isdir(tmp_dir):
      for f in os.listdir(tmp_dir):
        if f.startswith('qemu-gles-'):
          file_path = os.path.join(tmp_dir, f)
          logger.info("Delete file %s", file_path)
          try:
            os.remove(file_path)
          except Exception as e:
            logger.info("Error in deleting qemu-gles-[pid] %r", e)

  # remove build directory
  for f in os.listdir(args.build_dir):
    file_path = os.path.join(args.build_dir,f)
    try:
      if os.path.isfile(file_path):
        logger.info("Delete file %s", file_path)
        os.remove(file_path)
      elif os.path.isdir(file_path):
        logger.info("Delete directory %s", file_path)
        shutil.rmtree(file_path)
    except Exception as e:
      logger.error("Error in deleting build directory %r", e)

def update_sdk(filter):
    android_exec = "android.bat" if os.name == "nt" else "android"
    cmd = [android_exec, "update", "sdk", "-s", "--no-ui", "--filter", filter]
    logger.info("Update android sdk, cmd: %s", ' '.join(cmd))
    ps = psutil.Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=STDOUT, bufsize=1)
    with ps.stdout:
      ps.stdin.write('y\n')
      for line in iter(ps.stdout.readline, b""):
        logger.info(line)
        if "Do you accept the license" in line:
          try:
            ps.stdin.write('y\n')
          except:
            pass
      ps.wait()

if __name__ == "__main__":
  try:
    clean_up()
  except:
    pass
  if os.name != "nt":
    update_sdk('add-on,system-image,extra,platform-tool,platform,tool')
