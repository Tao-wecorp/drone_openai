import numpy
import rospy
import time
from openai_ros import robot_gazebo_env
from std_msgs.msg import Float64
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from geometry_msgs.msg import Pose
from std_msgs.msg import Empty


class SJTUDroneEnv(robot_gazebo_env.RobotGazeboEnv):

    def __init__(self):
        
        self.controllers_list = []
        self.robot_name_space = ""

        super(SJTUDroneEnv, self).__init__(controllers_list=self.controllers_list,
                                    robot_name_space=self.robot_name_space,
                                    reset_controls=False,
                                    start_init_physics_parameters=False,
                                    reset_world_or_sim="WORLD")

        self.gazebo.unpauseSim()

        self._check_all_sensors_ready()
        rospy.Subscriber("/drone/front_camera/image_raw", Image, self._front_camera_rgb_image_raw_callback)
        rospy.Subscriber("/drone/gt_pose", Pose, self._gt_pose_callback)

        self._cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self._takeoff_pub = rospy.Publisher('/drone/takeoff', Empty, queue_size=1)
        self._land_pub = rospy.Publisher('/drone/land', Empty, queue_size=1)
        self._check_all_publishers_ready()

        self.gazebo.pauseSim()

    # Check systems ready
    def _check_all_systems_ready(self):
        self._check_all_sensors_ready()
        return True

    def _check_all_sensors_ready(self):
        self._check_front_camera_rgb_image_raw_ready()
        self._check_gt_pose_ready()
        rospy.logdebug("ALL SENSORS READY")
        
    def _check_front_camera_rgb_image_raw_ready(self):
        self.front_camera_rgb_image_raw = None
        while self.front_camera_rgb_image_raw is None and not rospy.is_shutdown():
            try:
                self.front_camera_rgb_image_raw = rospy.wait_for_message("/drone/front_camera/image_raw", Image, timeout=5.0)
                rospy.logdebug("Current /drone/front_camera/image_raw READY")
            except:
                rospy.logerr("Current /drone/front_camera/image_raw not ready yet, retrying for getting front_camera_rgb_image_raw")
        return self.front_camera_rgb_image_raw
            
    def _check_gt_pose_ready(self):
        self.gt_pose = None
        while self.gt_pose is None and not rospy.is_shutdown():
            try:
                self.gt_pose = rospy.wait_for_message("/drone/gt_pose", Pose, timeout=5.0)
                rospy.logdebug("Current /drone/gt_pose READY")
            except:
                rospy.logerr("Current /drone/gt_pose not ready yet, retrying for getting gt_pose")
        return self.gt_pose
    
    def _front_camera_rgb_image_raw_callback(self, data):
        self.front_camera_rgb_image_raw = data
        
    def _gt_pose_callback(self, data):
        self.gt_pose = data

    def _check_all_publishers_ready(self):
        self._check_cmd_vel_pub_connection()
        self._check_takeoff_pub_connection()
        self._check_land_pub_connection()
        rospy.logdebug("All Publishers READY")

    def _check_cmd_vel_pub_connection(self):
        rate = rospy.Rate(30)
        while self._cmd_vel_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _cmd_vel_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                pass
        rospy.logdebug("_cmd_vel_pub Publisher Connected")
        
    def _check_takeoff_pub_connection(self):
        rate = rospy.Rate(30)
        while self._takeoff_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _takeoff_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                pass
        rospy.logdebug("_takeoff_pub Publisher Connected")
        
    def _check_land_pub_connection(self):
        rate = rospy.Rate(30)
        while self._land_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _land_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                pass
        rospy.logdebug("_land_pub Publisher Connected")
    
    # Methods for task env
    def _set_init_pose(self):
        raise NotImplementedError()
    
    def _init_env_variables(self):
        raise NotImplementedError()

    def _compute_reward(self, observations, done):
        raise NotImplementedError()

    def _set_action(self, action):
        raise NotImplementedError()

    def _get_obs(self):
        raise NotImplementedError()

    def _is_done(self, observations):
        raise NotImplementedError()
        
    # Methods predefined
    def takeoff(self):
        self.gazebo.unpauseSim()
        self._check_takeoff_pub_connection()
        
        takeoff_cmd = Empty()
        self._takeoff_pub.publish(takeoff_cmd)
        
        self.wait_for_height(heigh_value_to_check=1.2,
                            smaller_than=False,
                            epsilon = 0.05,
                            update_rate = 30)
        self.gazebo.pauseSim()
        
    def land(self):
        self.gazebo.unpauseSim() 
        self._check_land_pub_connection()
        
        land_cmd = Empty()
        self._land_pub.publish(land_cmd)

        self.wait_for_height(heigh_value_to_check=0.6,
                            smaller_than=True,
                            epsilon = 0.05,
                            update_rate = 30)
        self.gazebo.pauseSim()
        
    def wait_for_height(self, heigh_value_to_check, smaller_than, epsilon, update_rate):
        rate = rospy.Rate(update_rate)
        start_wait_time = rospy.get_rostime().to_sec()
        end_wait_time = 0.0
        
        while not rospy.is_shutdown():
            current_gt_pose = self._check_gt_pose_ready()
            current_height = current_gt_pose.position.z
            
            if smaller_than:
                takeoff_height_achieved = current_height <= heigh_value_to_check
            else:
                takeoff_height_achieved = current_height >= heigh_value_to_check
            
            if takeoff_height_achieved:
                rospy.logwarn("Reached Height!")
                end_wait_time = rospy.get_rostime().to_sec()
                break
            rate.sleep()
        
    def move_base(self, linear_speed_vector, angular_speed, epsilon=0.05, update_rate=30):
        cmd_vel_value = Twist()
        cmd_vel_value.linear.x = linear_speed_vector.x
        cmd_vel_value.linear.y = linear_speed_vector.y
        cmd_vel_value.linear.z = linear_speed_vector.z
        cmd_vel_value.angular.z = angular_speed
        self._check_cmd_vel_pub_connection()
        self._cmd_vel_pub.publish(cmd_vel_value)
        self.wait_time_for_execute_movement()
                                        
    def wait_time_for_execute_movement(self):
        time.sleep(0.5)
    
    def get_front_camera_rgb_image_raw(self):
        return self.front_camera_rgb_image_raw
        
    def get_gt_pose(self):
        return self.gt_pose
