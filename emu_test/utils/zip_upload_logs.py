import os
import argparse
import subprocess

parser = argparse.ArgumentParser(description='Zip and upload log folders')

parser.add_argument('--dir', dest='zip_dir', action='store',
                    help='string contains a list of remote files separated by comma')
parser.add_argument('--name', dest='zip_name', action='store',
                    help='name of zipped file - usually contains the build number')
parser.add_argument('--user', dest='remote_user', action='store',
                    help='remote user name')
parser.add_argument('--ip', dest='remote_ip', action='store',
                    help='remote ip')
parser.add_argument('--dst', dest='remote_dir', action='store',
                    help='remote directory')

args = parser.parse_args()

def zip_and_upload():

  def verbose_call(cmd):
    print "Run command %s" % ' '.join(cmd)
    subprocess.check_call(cmd)

  try:
    args.remote_dir = args.remote_dir.replace(" ", "_")
    verbose_call(['zip', '-r', args.zip_name, args.zip_dir])
    remote_host = '%s@%s' % (args.remote_user, args.remote_ip)
    remote_path = '%s:%s' % (remote_host, args.remote_dir)
    verbose_call(['ssh', remote_host, 'mkdir -p %s' % args.remote_dir])
    verbose_call(['scp', args.zip_name, remote_path])
  except Exception as e:
    print "Error in zip_and_upload %r" % e
    return 1

  return 0

if __name__ == "__main__":
  exit(zip_and_upload())
