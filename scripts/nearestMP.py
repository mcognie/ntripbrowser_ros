#!/usr/bin/python

from decimal import Decimal
import sys
import rospy
from ntripbrowser import NtripBrowser, UnableToConnect, ExceededTimeoutError
from sensor_msgs.msg import NavSatFix

class nearest_base:

    def __init__(self):
        self.gps_topic = rospy.get_param('~gps_topic', 'gps')
        self.excluded_MP = rospy.get_param('~excluded_MP', '[]')
        self.caster = rospy.get_param('~caster', 'caster.centipede.fr')
        self.port = rospy.get_param('~port', '2101')
        self.max_dist = rospy.get_param('~max_dist', '50')
        self.hysteresis = rospy.get_param('~hysteresis', '1')
        self.lat = 0.0
        self.lon = 0.0
        self.mp = ''
        self.sub = rospy.Subscriber(self.gps_topic, NavSatFix, self.callback)   

    def set_new_MP(self):
        rospy.loginfo("switching for the nearest mountpoint : " + self.mp)
        rospy.set_param('/ntrip_ros/ntrip_stream', self.mp)
        rospy.set_param('/ntrip_ros/is_new_stream', True)     

    def browser(self):
        coord = (Decimal(self.lat),Decimal(self.lon))
        b = NtripBrowser(self.caster,port=self.port,timeout=10,
            coordinates=coord,maxdist=self.max_dist)
        return b   

    def callback(self, data):
        self.lat = data.latitude
        self.lon = data.longitude
        browser = self.browser()
        getmp = []
        mountpoints = {}
        ''' Critical distance from which it will check if there is not a base closer '''
        crit_dist = 15  

        try:
            getmp = browser.get_mountpoints()['str']
        except ExceededTimeoutError as e:
            rospy.logwarn(e)
        except UnableToConnect as e:
            rospy.logwarn(e)

        ''' Extracting the nearest base receiving from L1-L2 carrier + not in the exclude list '''
        for i in range(len(getmp)):
            if int(getmp[i]['Carrier']) >= 2 and getmp[i]['Mountpoint'] not in self.excluded_MP:
                mountpoints = getmp[i]
                break

        if mountpoints:
            self.mp = rospy.get_param('/ntrip_ros/ntrip_stream')

            ''' Nearest base is not the current base '''
            if self.mp != mountpoints['Mountpoint']:
                mp_index = next((i for (i,val) in enumerate(getmp) 
                        if (val['Mountpoint'] == self.mp and val['Carrier']>= 2)), None)
                
                ''' Checks that the base is still active '''
                if mp_index != None and self.mp not in self.excluded_MP:
                    mp_dist = getmp[mp_index]['Distance']

                    ''' Applies Hysteresis filtering only if the current base is more than 15km away '''
                    if mp_dist > crit_dist:
                        mountpoint_dist = mountpoints['Distance']

                        ''' Hysteresis filter to treat the case where the point is between two bases '''
                        if (mp_dist + float(self.hysteresis)) > mountpoint_dist:
                            self.mp = mountpoints['Mountpoint']
                            self.set_new_MP()
                else:
                    self.mp = mountpoints['Mountpoint']
                    self.set_new_MP()
        else:
            rospy.logwarn("No base in the area !")


def main(args):
    rospy.init_node('nearest_MP', anonymous=True)
    nearest_base()
    try:
        rospy.spin()
    except KeyboardInterrupt:
        print("Shutting down")

if __name__ == '__main__':
    main(sys.argv)
