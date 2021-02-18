PX4 autopilot
=============

Python autopilot using the PX4 firmware toolchain, Gazebo, ROS, MAVROS and the MAVLink protocol.

## Installation

### Setting up the toolchain
Install the PX4 toolchain, ROS and Gazebo, using the
[PX4 scripts](https://dev.px4.io/master/en/setup/dev_env_linux_ubuntu.html).
You need to execute the `ubuntu_sim_ros_melodic.sh` script to install ROS Melodic and MavROS.
Then, execute the `ubuntu.sh` script to install simulators like Gazebo and the rest
of the PX4 toolchain. You **need** to use Ubuntu 18, otherwise it will not work !

You may need to clone the Firmware. We cloned it in the home folder.

The source code is in `~/catkin_ws/src/`, with some common modules like MAVROS,
and the custom autopilot from this repository. You need to always build the packages
with `catkin build`.

In the `.bashrc`, you need the following lines. Adapt `$fw_path` and `$gz_path` according to the location
of the PX4 firmware.
```shell script
source /opt/ros/melodic/setup.bash
source ~/catkin_ws/devel/setup.bash

fw_path="$HOME/Firmware"
gz_path="$fw_path/Tools/sitl_gazebo"
source $fw_path/Tools/setup_gazebo.bash $fw_path $fw_path/build/px4_sitl_default
export ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH:$fw_path
export ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH:$gz_path

# Set the plugin path so Gazebo finds our model and sim
export GAZEBO_PLUGIN_PATH=${GAZEBO_PLUGIN_PATH}:$gz_path/build
# Set the model path so Gazebo finds the airframes
export GAZEBO_MODEL_PATH=${GAZEBO_MODEL_PATH}:$gz_path/models
# Disable online model lookup since this is quite experimental and unstable
export GAZEBO_MODEL_DATABASE_URI=""
export SITL_GAZEBO_PATH=$gw_path
```

### Compile and run a vanilla simulation

First, you need to compile the PX4 toolchain once.
```shell script
DONT_RUN=1 make px4_sitl_default gazebo
```

We use `roslaunch` to launch every ROS nodes necessary.
```shell script
roslaunch px4 mavros_posix_sitl.launch
```

This command launch the launch file located in the PX4 ROS package in
`Firmware/launch/mavros_posix_sitl.launch`.
It launches PX4 as SITL, MAVROS, Gazebo connected to PX4, and spawns the UAV.

It is possible to send some arguments to change the vehicle initial pose,
the world or the vehicle type.
```shell script
roslaunch px4 mavros_posix_sitl.launch x:=10 y:=10 world:=$HOME/Firmware/Tools/sitl_gazebo/worlds/warehouse.world
```
The maps are stored in the PX4 toolchain in `Firmware/Tools/sitl_gazebo/worlds/`.
The Gazebo models and UAVs used in the simulation are in `Firmware/Tools/sitl_gazebo/models/`.

### Setting up the octomap

To use the octomap generated by all the sensors, you need to install the
`octomap_serveur` node to be used in ROS.
```shell script
sudo apt install ros-melodic-octomap ros-melodic-octomap-mapping
rosdep install octomap_mapping
rosmake octomap_mapping
```

Then, in order to use the octomap data in the autopilot, you need the
[python wrapper](https://github.com/wkentaro/octomap-python)
of the [C++ octomap library](https://github.com/OctoMap/octomap).
You can install it with `pip2`, but I had conflicts between python 2 and 3, so
I compiled the module directly.
```shell script
git clone --recursive https://github.com/wkentaro/octomap-python.git
cd octomap-python
python2 setup.py build
python2 setup.py install
```

If you are using the _ground truth_ octomap of the Gazebo world,
you need to generate the `.bt` file representation of the octomap.
You can generate it using the `world2oct.sh` script in the `autopilot/world_to_octomap/`
folder of this repo.

For more info, refer to `autopilot/world_to_octomap/readme.md`.


### SLAM

For mapping and localization, we are using [OpenVSLAM](https://github.com/xdspacelab/openvslam).
First, you need to [install OpenVSLAM](https://openvslam.readthedocs.io/en/master/installation.html#chapter-installation), 
using OpenCV 3.x.x and maybe PangolinViewer.
You can simply follow the script on that page to compile all the dependancies.
Then, you need to install the [ROS package](https://openvslam.readthedocs.io/en/master/ros_package.html).

You may need to download a [DBOW](https://github.com/dorian3d/DBoW2) dictionnary. One is provided by OpenVSLAM
on [Google Drive](https://drive.google.com/open?id=1wUPb328th8bUqhOk-i8xllt5mgRW4n84)
or [Baidu Drive](https://pan.baidu.com/s/1627YS4b-DC_0Ioya3gLTPQ) (Pass: zb6v). 
This will give you the `orb_vocab.dbow` file needed later.

You may also need to calibrate your camera. OpenVSLAM requires a `config.yaml` file to calibrate the camera.
[This page](http://wiki.ros.org/camera_calibration/Tutorials/MonocularCalibration) provides a tutorial
to calibrate a camera and output a Yaml and a Txt files. But the Yaml file is not the right format
for OpenVSLAM. To convert the Yaml format, you have to do it by hand. You can use [this](https://github.com/xdspacelab/openvslam/issues/104)
and [this](http://www.huyaoyu.com/technical/2018/06/23/convert-results-from-ros-camera_calibration-into-format-used-by-opencv.html).
We provide a config file for the Bebop in `./bebop/config.yaml`.

Add the bash sourcing file of OpenVSLAM in your `.bashrc`.
```shell script
source $HOME/openvslam/ros/devel/setup.bash
```

By default, the ROS OpenVSLAM package does not publish any data on ROS topics.
We replace a C++ file inside the OpenVSLAM package to make it publish data.
We are using a user made [implementation](https://github.com/xdspacelab/openvslam/issues/347) of the provided `run_localization.cc`.
```shell script
# Replace the file
cd openvslam/ros/src/openvslam/src
wget https://raw.githubusercontent.com/anbello/openvslam/pr-ros1-pose-pub/ros/1/src/openvslam/src/run_localization.cc -O run_localization.cc
cd ../../..

# Build OpenVSLAM
catkin_make \
    -DBUILD_WITH_MARCH_NATIVE=ON \
    -DUSE_PANGOLIN_VIEWER=ON \
    -DUSE_SOCKET_PUBLISHER=OFF \
    -DUSE_STACK_TRACE_LOGGER=ON \
    -DBOW_FRAMEWORK=DBoW2
```

If the the build fails, we found out that commenting the following lines in the
`run_localization.cc` file in the `pose_odometry_pub` function makes it work.
**But it is not an ideal solution and a better fix should be found !**
**Ideally a custom C++ module should be added to this repository to start the SLAM and publish in topics.**
```C++
// transform broadcast
static tf2_ros::TransformBroadcaster tf_br;

geometry_msgs::TransformStamped transformStamped;

transformStamped.header.stamp = ros::Time::now();
transformStamped.header.frame_id = "map";
transformStamped.child_frame_id = "base_link_frame";
transformStamped.transform.translation.x = transform_tf.getOrigin().getX();
transformStamped.transform.translation.y = transform_tf.getOrigin().getY();
transformStamped.transform.translation.z = transform_tf.getOrigin().getZ();
transformStamped.transform.rotation.x = transform_tf.getRotation().getX();
transformStamped.transform.rotation.y = transform_tf.getRotation().getY();
transformStamped.transform.rotation.z = transform_tf.getRotation().getZ();
transformStamped.transform.rotation.w = transform_tf.getRotation().getW();

tf_br.sendTransform(transformStamped);
```

The pose and odometry data are published in `/openvslam/camera_pose` and `/openvslam/odometry`, 
as `geometry_msgs/PoseStamped` and `nav_msgs/Odometry`.


### SLAM mapping with an Android phone

To create a map of the environment, you may want to map it using an Android phone.
To do that use the app [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam&hl=fr&gl=US),
and get the IP address of the phone. The video feed should be accessible at `http://192.168.x.x:8080/video`.

Then, clone the [ip_camera](https://github.com/ravich2-7183/ip_camera) ROS package, a small
python utility which publish an IP camera feed to the `/camera/image_raw` ROS topic.

```shell script
git clone https://github.com/ravich2-7183/ip_camera
cd ip_camera
python2 nodes/ip_camera.py -u http://192.168.x.x:8080/video
```

You can then start the OpenVSLAM node which can analyses the raw video feed.
You may need to use to transport the video to a different topic. Follow the 
[tutorial](https://openvslam.readthedocs.io/en/master/ros_package.html#publish-images-of-a-usb-camera) to learn how.
```shell script
rosrun openvslam run_slam -v /home/rhidra/orb_vocab/orb_vocab.dbow2 -c aist_entrance_hall_1/config.yaml
```

### Bebop setup

To run the program on actual UAVs, we are using the Parrot Bebop 2. The firmware is closed, so we are using
a ROS driver, [bebop_autonomy](https://bebop-autonomy.readthedocs.io/).

To install the driver, follow the [official tutorial](https://bebop-autonomy.readthedocs.io/en/latest/installation.html).

During the installation we had [this issue](https://github.com/AutonomyLab/bebop_autonomy/issues/170).
To solve it, make sure you have the folder `catkin_ws/devel/lib/parrot_arsdk`.
If not, install the `parrot_arsdk` ROS module. Then copy the module in the catkin workspace.
```shell script
sudo apt install ros-melodic-parrot-arsdk
cp -r /opt/ros/melodic/lib/parrot_arsdk ~/catkin_ws/devel/lib/
```

Once you have the module installed, add this line to your `.bashrc` file.
```shell script
export LD_LIBRARY_PATH=~/catkin_ws/devel/lib/parrot_arsdk:$LD_LIBRARY_PATH
```

To process the Bebop video stream, we have a custom module `image_proc` which add some brightness.
You need to install a few dependencies.
```shell script
sudo apt install python-cv-bridge
```

To connect to the Bebop you need to connect to the WiFi access point deployed by the UAV.
To still be able to access the internet while being connected, you can connect to a wired internet connection,
reroute all 192.168.42.1 (drone IP address) traffic to the WiFi interface and the rest of the traffic to the wired interface.
To do that, get your WiFi interface name with `ip route list`, and update your routing table.
You have to run that script everytime you connect to the WiFi access point.
```shell script
sudo ip route add 192.168.42.1/32 dev wlp3s0
```

## Launch simulation

To launch all necessary nodes, a launch file is available in `autopilot/launch/simulation.launch`.
It launches ROS, MAVROS, PX4, Gazebo and the Octomap server using a `.bt` file.
It also start Rviz with the `./config.rviz` configuration file, to visualize the octomap and the algorithms.
The `/autopilot/viz/global` and `/autopilot/viz/local` topics are used by the autopilot to display data on Rviz.
You can also specify a vehicle, and a starting position.
```shell script
roslaunch autopilot simulation.launch vehicle:=iris world:=test_zone
```

## Use a Bebop UAV

To use a Bebop as the autonomous UAV, you first need to make a map of the environment.
You can just start the drone without taking off, and move it around to analyse the environment.
To start the mapping module, run `roslaunch autopilot mapping.launch`.
It launches the Bebop driver, the OpenVSLAM mapping module and the image processing bridge module.
To improve the image quality, you can modify the brightness and contrast of the image processing module.
Once done, the OpenVSLAM creates a map database, located be default at `autopilot/map-db.msg`.

You can now run the autopilot in fly mode, with `roslaunch autopilot fly.launch`.
It launches the Bebop driver, the OpenVSLAM localization module, the image processing bridge module,
the Rviz visualization tool and the octomap server.

## Autopilot

### Global planner

To launch the global planner, launch the simulation (previous section),
and run the global planner ROS node with the following command.
You can specify a few different parameters, like the algorithms used,
if an advanced display should be used, or to record data for later analysis.
You can use the `--help` option to learn more. 

```shell script
rosrun autopilot global_planner.py -p <planning_algorithm>
```

`<planning_algorithm>` can be:
- a_star
- ~~RRT~~
- rrt_star
- theta_star
- phi_star
- dummy (Dummy planning algorithm, for testing purposes)

The global planner computes a global path only **once**, then broadcast
continuously a potential _local goal_ position to use as an objective for the
local planner. The local goal is broadcasted as a
[PoseStamped](http://docs.ros.org/en/api/geometry_msgs/html/msg/PoseStamped.html)
on the `/autopilot/local_goal` topic.

### Local planner

To launch the local planner, launch the simulation and the global planner.
Then run the local planner ROS node with the following command.

```shell script
rosrun autopilot local_planner.py
```