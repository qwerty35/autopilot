#!/usr/bin/env python
import rospy, math, numpy as np, time
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from mavros_msgs.msg import Altitude, ExtendedState, HomePosition, State, WaypointList, CommandCode, Waypoint, PositionTarget
from mavros_msgs.srv import CommandBool, ParamGet, SetMode, WaypointClear, WaypointPush
from sensor_msgs.msg import NavSatFix, Imu
from octomap_node import OctomapNode
from motion_primitive import MotionPrimitiveLibrary, TrajectoryError
from autopilot.srv import MotionPrimitive


TOLERANCE_FROM_WAYPOINT = .5
TOLERANCE_FROM_GOAL = 1

IDLE_DURATION = 1

class MotionPrimitiveNode(OctomapNode):
    def setup(self):
        super(MotionPrimitiveNode, self).setup()
        rospy.loginfo('Setting up the service...')
        self.tf = 3
        self.mpl = None
        self.trajectory = None
        self.traj_history = []
        self.service = rospy.Service('/autopilot/trajectory', MotionPrimitive, self.generate_trajectory)
        rospy.loginfo('Waiting for trajectory request...')
        rospy.spin()
    

    def generate_trajectory(self, msg):
        if self.local_goal_point is None or self.local_goal_direction is None:
            rospy.logerr('Cannot generate a trajectory: No local goal received !')

        try:
            self.trajectory = self.compute_optimal_traj()
            rospy.loginfo('Selected trajectory with cost: {}'.format(self.trajectory.print_cost()))

            msg = self.trajectory.toMsg()
            self.visualize_local_path(pos=self.pos, vel=self.vel, trajLibrary=self.mpl.trajs, trajSelected=self.trajectory, trajHistory=self.traj_history, tf=self.tf)
            self.traj_history.append(self.trajectory)
            return msg
        except TrajectoryError:
            rospy.logerr('Cannot generate a trajectory: No feasible trajectory found')
    

    def compute_optimal_traj(self):
        start = time.time()
        if self.trajectory is None:
            pos, vel, acc, yaw = self.pos, self.vel, self.acc, self.yaw
        else:
            pos, vel = self.trajectory.get_position(self.tf), self.trajectory.get_velocity(self.tf), 
            acc, yaw = self.trajectory.get_acceleration(self.tf), self.trajectory.get_yaw(self.tf), 
            
        if np.linalg.norm(vel) < 0.2: 
            # When the UAV stopped, we artificially increase its 
            # initial velocity to make move in the right direction
            vel = np.array([.1 * np.cos(yaw), .1 * np.sin(yaw), 0.])
            acc = np.array([0., 0., 0.])

        self.mpl = MotionPrimitiveLibrary(tf=self.tf)
        self.mpl.generate_traj_library(pos, vel, acc)
        self.mpl.rank_trajectories(self.local_goal_point, self.local_goal_direction, self.get_point_edt)
        traj = self.mpl.get_best_traj()
        rospy.loginfo('Generated a new trajectory in {}sec'.format(time.time() - start))
        return traj
