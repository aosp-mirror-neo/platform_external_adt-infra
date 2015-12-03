import os
import argparse
import subprocess

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

def download_and_unzip():
  file_list = args.remote_file_list.split(',')
  dst_dir = get_dst_dir(file_list[0])
  if dst_dir is not None:
    subprocess.call(['rm', '-rf', os.path.dirname(dst_dir)])

  for file_path in file_list:
    file_path = file_path.strip('\n')
    if file_path == '':
      continue
    dst_dir = get_dst_dir(file_path)
    remote_path = '%s@%s:%s' % (args.remote_user, args.remote_ip, file_path)
    file_name = os.path.basename(remote_path)
    subprocess.call(['scp', remote_path, '.'])
    if dst_dir is not None:
      subprocess.call(['mkdir', '-p', dst_dir])
      if 'x86_64' in file_path:
        subprocess.call(['rm', '-rf', os.path.join(dst_dir,'x86_64')])
      else:
        subprocess.call(['rm', '-rf', os.path.join(dst_dir,'x86')])
      subprocess.call(['unzip', '-o', file_name, '-d', dst_dir])
    else:
      subprocess.call(['unzip', '-o', file_name])

if __name__ == "__main__":
  download_and_unzip()
