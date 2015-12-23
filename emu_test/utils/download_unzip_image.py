import os
import argparse
import subprocess
import psutil

parser = argparse.ArgumentParser(description='Download and unzip a list of files separated by comma')
parser.add_argument('--file', dest='remote_file_list', action='store',
                    help='string contains a list of remote files separated by comma')
parser.add_argument('--dst', dest='dst', action='store',
                    help='local location to store images')
parser.add_argument('--user', dest='remote_user', action='store',
                    help='remote user name')
parser.add_argument('--ip', dest='remote_ip', action='store',
                    help='remote ip')

args = parser.parse_args()


def get_dst_dir(remote_path):
  file_name = os.path.basename(remote_path)
  if file_name.startswith('sdk-repo-linux-system-images'):
    branch_name = remote_path.split('/')[-2]
    if 'google_phone' in branch_name:
      tag = 'google_apis'
    else:
      tag = 'default'
    if 'lmp' in branch_name:
      api = '22'
    elif 'mnc' in branch_name:
      api = '23'
    else:
      raise ValueError("unsupported image %s", branch_name)
    return os.path.join(os.environ['ANDROID_SDK_ROOT'],
                        "system-images", "android-%s" % api, tag)
  else:
    return None

def clean_emu_proc():
  print 'clean up any emulator process'
  for x in psutil.process_iter():
    try:
      proc = psutil.Process(x.pid)
      # mips 64 use qemu-system-mipsel64, others emulator-[arch]
      if "emulator" in proc.name() or "qemu-system" in proc.name():
        print "trying to kill - %s, pid - %d, status - %s" % (proc.name(), proc.pid, proc.status())
        proc.kill()
    except:
      pass

def download_and_unzip():
  clean_emu_proc()
  file_list = args.remote_file_list.split(',')
  dst_dir = get_dst_dir(file_list[0])

  def verbose_call(cmd):
    print "Run command %s" % ' '.join(cmd)
    subprocess.check_call(cmd)

  for file_path in file_list:
    file_path = file_path.strip('\n')
    if file_path == '':
      continue
    dst_dir = get_dst_dir(file_path)
    remote_path = '%s@%s:%s' % (args.remote_user, args.remote_ip, file_path)
    file_name = os.path.basename(remote_path)
    try:
      verbose_call(['scp', remote_path, '.'])
      if dst_dir is not None:
        verbose_call(['mkdir', '-p', dst_dir])
        if 'x86_64' in file_path:
          verbose_call(['rm', '-rf', os.path.join(dst_dir,'x86_64')])
        else:
          verbose_call(['rm', '-rf', os.path.join(dst_dir,'x86')])
        verbose_call(['unzip', '-o', file_name, '-d', dst_dir])
      else:
        verbose_call(['unzip', '-o', file_name])
    except Exception as e:
      print "Error in download_and_unzip %r" % e
      return 1
  return 0

if __name__ == "__main__":
  exit(download_and_unzip())
