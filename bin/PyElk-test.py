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

    if len(argv) < 2:
        print('usage: [host/device]')
        sys.exit(-1)

    host = argv[1]

    print('Connecting to ' + host)

    import PyElk

    config = {'host' : host,
              #'zone' : {'include' : '1-38', 'exclude' : '15-20'},
              }

    ELK = PyElk.Elk(config, log=_LOGGER)

    time.sleep(1)
    versions = ELK.get_version()
    from pprint import pprint
    pprint(versions)
    #for o in range(1,209):
    #    sys.stdout.write('Output {}: '.format(repr(ELK.OUTPUTS[o].description())))
    #    sys.stdout.write('{}\n'.format(repr(ELK.OUTPUTS[o].status())))
    pprint(ELK.X10[1]._description)
    #ELK.X10[1].turn_on()

    while True:
        ELK.update()
        time.sleep(5)