#!/usr/bin/env python

from __future__ import print_function
import __builtin__
from fcntl import LOCK_SH, LOCK_EX, LOCK_UN, LOCK_NB
import argparse
import datetime
import fcntl
import json
import os
import requests
import shelve
import sys
import time
import types


#critical, error, warning or info
SEVERITY_SVC_MAP = {'OK': 'info', 'WARNING': 'warning', 'CRITICAL': 'critical'}
SEVERITY_HOST_MAP = {'UP': 'info', 'DOWN': 'critical'}
EVENTMAP = {'PROBLEM': 'trigger', 'RECOVERY': 'resolve', 'ACKNOWLEDGEMENT': 'resolve',
        'FLAPPINGSTART': 'warning', 'FLAPPINGEND': 'resolve'}

def parseargs():
    '''
    argument parsing
    '''
    parser = argparse.ArgumentParser(description='Pager duty alert. PagerDuty can process PROBLEM, ACKNOWLEDGEMENT, and RECOVERY messages.')

    parser.add_argument('-t' '--time-duraion', dest='timeframe', type=int,\
            help='Time frame in seconds for which we should check run frequencys', default=300)

    parser.add_argument('-f' '--frequency', dest='frequency', type=int,  default=10,
            help='How many times are too many for time-frame')

    parser.add_argument('-P' '--partial', dest='partial', type=int, default=0,
            help='If set to other than 0, will use to check timeframe / partial and frequency / partial')

    parser.add_argument('-d' '--debug', dest='debug', action='store_true',\
            default=False, help='Enable debugging')

    parser.add_argument('-F' '--floodstatefile', dest='floodstatefile',\
            default='/tmp/floodstatefile', help='File path to store state')

    parser.add_argument('-a' '--api-key', dest='apikey', help='Api key')

    parser.add_argument('-p' '--pager', dest='userpager', help='Contact pager (user.pager)')

    parser.add_argument('-n' '--notification-type', dest='notificationtype', help='PROBLEM/RECOVERY etc (notification.type)')

    parser.add_argument('-N' '--service-name', dest='servicename', help='Service name (service.name)')

    parser.add_argument('-s' '--service-state', dest='servicestate', help='Service state (service.state)')

    parser.add_argument('-S' '--host-state', dest='hoststate', help='Host state (host.state)')

    parser.add_argument('-H' '--host-name', dest='hostname', help='Host name (host.name)')

    parser.add_argument('-A' '--host-alias', dest='hostalias', help='Host alias (host.display_name)')

    parser.add_argument('-o' '--serviceoutput', dest='serviceoutput', help='Service output (service.output)')

    parser.add_argument('-O' '--hostoutput', dest='hostoutput', help='Host output (host.output)')

    parser.add_argument('-m' '--messenger', dest='messenger', help='Most likely "icinga2" or "nagios"')

    parser.add_argument('-g' '--group', dest='group', help='Host or service group')

    parser.add_argument('-l' '--link', dest='link', help='Link to something to send with msg')

    parser.add_argument('-L' '--linktext', dest='linktext', help='Link text to go with the link')

    parser.add_argument('-C' '--clienturl', dest='clienturl', help='clien url')

    args = parser.parse_args()
    if args.debug:
        print("args: ", args)
    return args

# flood avoid functions
def createstatefile(file):
    if not os.path.exists(file):
        print('Creating missing floodstatefile')
        shelf = shelve.open(file)
        shelf['occurence'] = 1
        shelf.close()

def _close(self):
    shelve.Shelf.close(self)
    fcntl.flock(self.lckfile.fileno(), LOCK_UN)
    self.lckfile.close()

def open(filename, flag='c', protocol=None, writeback=False, block=True, lckfilename=None):
    """Open the shelve file, createing a lockfile at filename.lck.  If
    block is False then a IOError will be raised if the lock cannot
    be acquired"""
    if lckfilename == None:
        lckfilename = filename + ".lck"
        lckfile = __builtin__.open(lckfilename, 'w')

    # Accquire the lock
    if flag == 'r':
        lockflags = LOCK_SH
    else:
        lockflags = LOCK_EX
    if not block:
        lockflags = LOCK_NB

    fcntl.flock(lckfile.fileno(), lockflags)

    # Open the shelf
    shelf = shelve.open(filename, flag, protocol, writeback)

    # Override close
    shelf.close = types.MethodType(_close, shelf, shelve.Shelf)
    shelf.lckfile = lckfile

    # And return it
    return shelf

def saveDbase(filename, object):
    shelf = open(filename, flag='w')
    shelf['occurence'] = object
    shelf.close()   # any file-like object will do

def loadDbase(filename):
    shelf = open(filename, flag='r')
    object = shelf['occurence'] # unpickle from file
    shelf.close()   # re-creates object in memory
    return object

# This must occur before we open and update the floodnumber
def getFloodtime(floodstatefile):
    st=os.stat(floodstatefile)
    floodmtime=st.st_mtime
    now = time.time()
    flooddiff = now - floodmtime
    return flooddiff

def avoidaction(args):
    args.hostname = 'Floodavoid'
    args.servicename = 'Floodavoid'
    args.serviceoutput = 'Avoiding flood pausing notifications temporarily! (Resolve manually)!! '
    args.servicestate = None
    trigger_incident(args)
    sys.exit(0)

def check_flood(args):
    flooddiff = getFloodtime(args.floodstatefile)
    if flooddiff > args.timeframe: # last trigger was out of timeframe
        occurence = 1
        saveDbase(args.floodstatefile, occurence)
    else:
        occurence = loadDbase(args.floodstatefile)
        occurence = occurence + 1
        saveDbase(args.floodstatefile, occurence)

    if args.debug:
        print('Flooddiff %s' % flooddiff)
        print('occurence %s' % occurence)

    if args.notificationtype != 'PROBLEM':
        '''We still want resolves and other stuff for older problems'''
        return


    if int(flooddiff) < args.timeframe and int(occurence) > args.frequency :
        print('Avoiding flood')
        sys.exit(0)
    if int(flooddiff) < args.timeframe and int(occurence) > (args.frequency - 1):
        avoidaction(args)

    if args.partial:
        args.timeframe = args.timeframe / args.partial
        args.frequency =  args.frequency / args.partial
        if args.debug:
            print('calculating partial args.timeframe=%s, occurence=%s' % (args.timeframe, args.frequency))
        if int(flooddiff) < args.timeframe and int(occurence) > (args.frequency - 1):
            avoidaction(args)
        if int(flooddiff) < args.timeframe and int(occurence) > args.frequency:
            print('Avoiding flood on short timeframe.')
            sys.exit(0)
# end flood avoid functions

def set_title(args):
    msg = ''
    if args.servicename:
        msg += '{servicename} on {hostname} = {servicestate}'.format(**args.__dict__)

    if args.hoststate:
        msg += '{hostname} {hoststate}'.format(**args.__dict__)
    
    if args.serviceoutput: 
        msg +=  '; ' + args.serviceoutput

    if args.hostoutput: 
        msg +=  '; ' + args.hostoutput

    msg = msg[0:500]

    return msg

def trigger_incident(args):
    """Triggers an incident via the V2 REST API using sample data."""
    msgtitle = set_title(args)
    
    url = 'https://events.pagerduty.com/v2/enqueue'
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/vnd.pagerduty+json;version=2',
        'Authorization': 'Token token={token}'.format(token=args.apikey),
        'X-Routing-Key': args.apikey,
        'From': args.messenger
    }
    postdata = {
        'payload' : {
            'summary': msgtitle,
            'timestamp': datetime.datetime.now().isoformat(),
            'source': args.hostname,
            'severity':  SEVERITY_SVC_MAP[args.servicestate] if args.servicestate else 'info',
            'component': args.servicename or 'Host check',
            'group': args.group,
            'class': args.servicename or args.hostname,

        },
        'routing_key': args.apikey,
        'dedup_key': '{servicename}!{hostname}'.format(**args.__dict__),
        'event_action': EVENTMAP[args.notificationtype],
        'client': 'icinga2',
        "client_url": args.clienturl,
    }
    if args.link:
        postdata.update({'links': [{'href': args.link, 'text': args.linktext or ''}]})

    try:
        r = requests.post(url, headers=headers, data=json.dumps(postdata))
    except Exception, e:
        print('Failed to connect to pagerduty %s' % e)
        sys.exit(2)
    if not r.status_code == 202:
        print('Failed to post to pagerduty  %s: %s: %s' % (r.status_code, r.reason, r.message))
        sys.exit(2)

    print('Post msg to pagerduty: %s: %s' % (r.status_code, r.reason))



def main():
    args = parseargs()
    createstatefile(args.floodstatefile)
    check_flood(args)
    trigger_incident(args)
    sys.exit(0)

if __name__ == '__main__':
    main()
