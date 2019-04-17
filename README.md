# icinga2_nagios_pagerduty_integration
notifications to pagerduty from icinga2 and nagios, hosts and services. Also has flood avoidance functionality.

Pager duty alert. PagerDuty can process PROBLEM, ACKNOWLEDGEMENT, and RECOVERY
messages.

optional arguments:
  -h, --help            show this help message and exit
  -t--time-duraion TIMEFRAME
                        Time frame in seconds for which we should check run
                        frequencys
  -f--frequency FREQUENCY
                        How many times are too many for time-frame
  -P--partial PARTIAL   If set to other than 0, will use to check timeframe /
                        partial and frequency / partial
  -d--debug             Enable debugging
  -F--floodstatefile FLOODSTATEFILE
                        File path to store state
  -a--api-key APIKEY    Api key
  -p--pager USERPAGER   Contact pager (user.pager)
  -n--notification-type NOTIFICATIONTYPE
                        PROBLEM/RECOVERY etc (notification.type)
  -N--service-name SERVICENAME
                        Service name (service.name)
  -s--service-state SERVICESTATE
                        Service state (service.state)
  -S--host-state HOSTSTATE
                        Host state (host.state)
  -H--host-name HOSTNAME
                        Host name (host.name)
  -A--host-alias HOSTALIAS
                        Host alias (host.display_name)
  -o--serviceoutput SERVICEOUTPUT
                        Service output (service.output)
  -O--hostoutput HOSTOUTPUT
                        Host output (host.output)
  -m--messenger MESSENGER
                        Most likely "icinga2" or "nagios"
  -g--group GROUP       Host or service group
  -l--link LINK         Link to something to send with msg
  -L--linktext LINKTEXT
                        Link text to go with the link
  -C--clienturl CLIENTURL
                        clien url

#Example usage
./pd_icinga.py -a "ABC123#############" -p "ABC123#############"  -n PROBLEM -N testservice123 -H testhost123 -o 'testoutput and alot of strange information' -s CRITICAL -l 'https://wiki.help.page' -m 'icinga2' -g testgroup -t 300 -f 7

# also see example command configuration 
