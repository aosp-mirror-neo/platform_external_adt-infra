import argparse
emu_args = None
import re

def get_parser():
    parser = argparse.ArgumentParser(description='Argument parser for emu test')

    parser.add_argument('-t', '--timeout', type=int, dest='timeout_in_seconds', action='store',
                        default=1200,
                        help='an integer for timeout in seconds, default is 1200')
    parser.add_argument('-l', '--loglevel', type=str, dest='loglevel', action='store',
                        choices=['DEBUG' , 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='INFO',
                        help='set the log level, default is INFO')
    parser.add_argument('-avd', type=str, nargs='+', dest='avd_list', action='store',
                        default=None,
                        help='run test for given AVD, support multiple avd separated by space')
    parser.add_argument('-b', type=int, dest='expected_boot_time', action='store',
                        default=720,
                        help='expected boot time in seconds, default is 720')
    parser.add_argument('-exec', type=str, dest='emulator_exec', action='store',
                        default='emulator',
                        help='path of emulator executable, default is system emulator')
    parser.add_argument('-s', type=str, dest='session_dir', action='store',
                        default=None,
                        help='specify the name of the dir created to store the session files of tests If not specified, the test driver uses the timestamp as the session dir name')
    parser.add_argument('-p', type=str, dest='pattern', action='store',
                        default='test*.py',
                        help='regex file name pattern for inclusion in the test suite')
    parser.add_argument('unittest_args', nargs='*')
    return parser
