from math import pi, sin, cos
from mavros_msgs.msg import CommandCode, Waypoint, PositionTarget
from geometry_msgs.msg import TwistStamped
import rospy


"""
Origin of the world as set by the Gazebo simulation
Corresponds to the (0, 0, 0) coordinates for a newly spawned UAV
"""
ORIGIN_LAT = 47.397742
ORIGIN_LON = 8.5455934


"""
localToGlobal()
convert a serie of waypoint in a local coordinate system to a global GPS
coordinate system. Each local coordinate is mapped to an offset relative to
a reference point in the GPS system.
May not be accurate for high offsets distances.

Reference :
- https://stackoverflow.com/questions/7477003/calculating-new-longitude-latitude-from-old-n-meters
- http://www.edwilliams.org/avform.htm#LL

@param waypoints: [[dx: int, dy: int, dz: int]] Offset to the longitude, latitude and altitude (in meters)
@param ref_lat Latitude of the reference point (in degrees)
@param ref_lon Longitude of the reference point (in degrees)
@return [[new_lat, new_lon]]
"""
def local_to_global(waypoints, ref_lat=ORIGIN_LAT, ref_lon=ORIGIN_LON):
    r_earth = 6378137. # WGS-84 ellipsoid parameters (in meters)
    new_wps = []

    for dx, dy, dz in waypoints:
        # Fix wrong TF when using mission system
        # The reference axis are rotated clock wise (-Z)
        # dx, dy, dz = dy, -dx, dz

        new_lat = ref_lat + (dy / r_earth) * (180. / pi)
        new_lon = ref_lon + (dx / r_earth) * (180. / pi) / cos(ref_lat * pi / 180.)
        new_wps.append([new_lat, new_lon, dz])

    return new_wps


"""
build_waypoints()
Build a list of MAVLink waypoints to be used in a mission.
The path input should be 3D, in global coordinates.

@param path: [[lat, lon, alt]] 3D path
@return [Waypoints]
"""
def build_waypoints(path):
    assert len(path) > 0, 'The path is empty !'

    waypoints = []
    for lat, lon, alt in path:
        wp = Waypoint()
        wp.frame = Waypoint.FRAME_GLOBAL_REL_ALT
        wp.command = CommandCode.NAV_WAYPOINT
        wp.is_current = False
        wp.autocontinue = True
        wp.x_lat = lat
        wp.y_long = lon
        wp.z_alt = alt
        waypoints.append(wp)

    wp = Waypoint()
    wp.frame = Waypoint.FRAME_GLOBAL_REL_ALT
    wp.command = CommandCode.NAV_LAND
    wp.is_current = False
    wp.autocontinue = True
    wp.x_lat = lat
    wp.y_long = lon
    wp.z_alt = alt
    waypoints.append(wp)
    waypoints[0].command = CommandCode.NAV_TAKEOFF
    waypoints[0].is_current = True

    return waypoints

"""
fix_path_orientation()
Fix wrong TF when using mission and offboard system
The reference axis are rotated clock wise (-Z)
"""
def fix_path_orientation(path):
    new_path = []
    for x, y, z in path:
        x, y, z = y, -x, z
        new_path.append([x, y, z])
    return new_path

"""
remove_start_offset()
Remove the offset from the starting point in the path
as if the path was starting from the (0, 0) point.
"""
def remove_start_offset(path):
    x_start, y_start, z_start = path[0]
    new_path = [[0, 0, z_start]]

    for x, y, z in path:
        new_path.append([x - x_start, y - y_start, z])

    return new_path 
    
"""
build_position_target()
Build a PositionTarget MAVROS message.
Set the correct type_mask flag depending on the parameters used.
"""
ALL_FLAGS = PositionTarget.IGNORE_PX + PositionTarget.IGNORE_PY + PositionTarget.IGNORE_PZ + \
            PositionTarget.IGNORE_VX + PositionTarget.IGNORE_VY + PositionTarget.IGNORE_VZ + \
            PositionTarget.IGNORE_AFX + PositionTarget.IGNORE_AFY + PositionTarget.IGNORE_AFZ + PositionTarget.IGNORE_YAW + PositionTarget.IGNORE_YAW_RATE
def build_position_target(px=None, py=None, pz=None, v=None, vx=None, vy=None, vz=None, a=None, ax=None, ay=None, az=None, yaw=None, yaw_rate=None, is_force=False):
    msg = PositionTarget()
    msg.header.stamp = rospy.Time.now()
    msg.type_mask = ALL_FLAGS
    msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED

    if v is not None:
        vx, vy, vz = v, v, v
    if a is not None:
        ax, ay, az = a, a, a

    if px is not None:
        msg.position.x = px
        msg.type_mask -= PositionTarget.IGNORE_PX
    if py is not None:
        msg.position.y = py
        msg.type_mask -= PositionTarget.IGNORE_PY
    if pz is not None:
        msg.position.z = pz
        msg.type_mask -= PositionTarget.IGNORE_PZ

    if vx is not None:
        msg.velocity.x = vx
        msg.type_mask -= PositionTarget.IGNORE_VX
    if vy is not None:
        msg.velocity.y = vy
        msg.type_mask -= PositionTarget.IGNORE_VY
    if vz is not None:
        msg.velocity.z = vz
        msg.type_mask -= PositionTarget.IGNORE_VZ

    if ax is not None:
        msg.velocity.x = ax
        msg.type_mask -= PositionTarget.IGNORE_AFX
    if ay is not None:
        msg.velocity.y = ay
        msg.type_mask -= PositionTarget.IGNORE_AFY
    if az is not None:
        msg.velocity.z = az
        msg.type_mask -= PositionTarget.IGNORE_AFZ

    if yaw is not None:
        msg.yaw = yaw
        msg.type_mask -= PositionTarget.IGNORE_YAW
    if yaw_rate is not None:
        msg.yaw_rate = yaw_rate
        msg.type_mask -= PositionTarget.IGNORE_YAW_RATE
    
    if is_force:
        msg.type_mask -= PositionTarget.FORCE
    
    return msg

"""
build_traj_tracker()
Build a TwistStamped message.
To be used as a trajectory tracker with the mavors_controllers package.
"""
def build_traj_tracker(pos=[0., 0., 2.], vel=[0., 0., 0.]):
    msg = TwistStamped()

    msg.header.stamp = rospy.Time.now()
    msg.header.frame_id = 'map'
    
    msg.twist.angular.x = pos[0]
    msg.twist.angular.y = pos[1]
    msg.twist.angular.z = pos[2]
    msg.twist.linear.x = vel[0]
    msg.twist.linear.y = vel[1]
    msg.twist.linear.z = vel[2]

    return msg