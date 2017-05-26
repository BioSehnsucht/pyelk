from collections import namedtuple
from collections import deque
import logging
import time
import sys
import traceback

ELK = None

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
_LOGGER = logging.getLogger()

#code = '1234'
#host = '/dev/ttyUSB0'
#host = 'socket://1.2.3.4:2101'

if __name__ == '__main__':
    from sys import argv

    if len(argv) < 3:
        print('usage: [usercode] [host/device]')
        sys.exit(-1)

    code = argv[1]
    host = argv[2]

    print('Connecting as usercode ' + code + ' to ' + host)

    import PyElk

    ELK = PyElk.Elk(address=host, usercode=code, log=_LOGGER)
    
    time.sleep(1)
    versions = ELK.get_version()
    from pprint import pprint
    pprint(versions)
    #for o in range(1,209):
    #    sys.stdout.write('Output {}: '.format(repr(ELK.OUTPUTS[o].description())))
    #    sys.stdout.write('{}\n'.format(repr(ELK.OUTPUTS[o].status())))
    
    while True:
        ELK.update()

