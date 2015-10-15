import argparse
emu_args = None
import re

# Provides a regular expression for matching gtimeout-based durations.
TIMEOUT_REGEX = re.compile(r"(^\d+)([smhd])?$")
def timeout_to_seconds(timeout):
    """Converts timeout/gtimeout timeout values into seconds.

    @param timeout a timeout in the form of xm representing x minutes.

    @return None if timeout is None, or the number of seconds as a float
    if a valid timeout format was specified.
    """
    if timeout is None:
        return None
    else:
        match = TIMEOUT_REGEX.match(timeout)
        if match:
            value = float(match.group(1))
            units = match.group(2)
            if units is None:
                # default is seconds.  No conversion necessary.
                return value
            elif units == 's':
                # Seconds.  No conversion necessary.
                return value
            elif units == 'm':
                # Value is in minutes.
                return 60.0 * value
            elif units == 'h':
                # Value is in hours.
                return (60.0 * 60.0) * value
            elif units == 'd':
                # Value is in days.
                return 24 * (60.0 * 60.0) * value
            else:
                raise Exception("unexpected units value '{}'".format(units))
        else:
            raise Exception("could not parse TIMEOUT spec '{}'".format(
                timeout))
def get_parser():
    parser = argparse.ArgumentParser(description='Argument parser for emu test')

    parser.add_argument('-t', '--timeout', type=int, dest='timeout_in_seconds', action='store',
                        default=300,
                        help='an integer for timeout in seconds, default is 300')
    parser.add_argument('-l', '--loglevel', type=str, dest='loglevel', action='store',
                        choices=['DEBUG' , 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='INFO',
                        help='set the log level, default is INFO')
    parser.add_argument('-avd', type=str, nargs='+', dest='avd_list', action='store',
                        default=None,
                        help='run test for given AVD, support multiple avd separated by space')
    parser.add_argument('-b', type=int, dest='expected_boot_time', action='store',
                        default=60,
                        help='expected boot time in seconds, default is 60')
    parser.add_argument('-exec', type=str, dest='emulator_exec', action='store',
                        default='emulator',
                        help='path of emulator executable, default is system emulator')
    parser.add_argument('unittest_args', nargs='*')
    return parser
