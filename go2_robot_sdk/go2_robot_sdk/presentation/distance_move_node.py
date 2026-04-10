# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

import math
from typing import Optional

import rclpy
from geometry_msgs.msg import Twist
from go2_interfaces.msg import Go2State
from rclpy.node import Node


class DistanceMoveNode(Node):
    """Open-loop distance move helper using /go2_states velocity integration."""

    def __init__(self) -> None:
        super().__init__('distance_move_node')

        self.declare_parameter('speed', 0.0)
        self.declare_parameter('angular_speed', 0.0)
        self.declare_parameter('distance', 0.0)
        self.declare_parameter('publish_rate', 10.0)

        self.speed = float(self.get_parameter('speed').value)
        self.angular_speed = float(self.get_parameter('angular_speed').value)
        self.target_distance = float(self.get_parameter('distance').value)
        self.publish_rate = float(self.get_parameter('publish_rate').value)

        if self.publish_rate <= 0.0:
            raise ValueError('publish_rate must be greater than 0')
        if self.target_distance < 0.0:
            raise ValueError('distance must be >= 0')

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.state_sub = self.create_subscription(
            Go2State, '/go2_states', self._on_go2_state, 10
        )

        self.last_velocity_time: Optional[float] = None
        self.current_speed_mps = 0.0
        self.integrated_distance_m = 0.0
        self.stop_publish_count = 0
        self.motion_complete = False

        self.timer = self.create_timer(1.0 / self.publish_rate, self._on_timer)

        self.get_logger().info(
            'distance_move_node started with '
            f'speed={self.speed:.3f} m/s, '
            f'angular_speed={self.angular_speed:.3f} rad/s, '
            f'distance={self.target_distance:.3f} m'
        )

        if self.target_distance == 0.0:
            self.get_logger().info(
                'distance is 0.0 m, node will only publish stop commands.'
            )

    def _on_go2_state(self, msg: Go2State) -> None:
        now = self.get_clock().now().nanoseconds / 1e9

        if self.last_velocity_time is not None and not self.motion_complete:
            dt = max(0.0, now - self.last_velocity_time)
            self.integrated_distance_m += self.current_speed_mps * dt

        vx = float(msg.velocity[0]) if len(msg.velocity) > 0 else 0.0
        vy = float(msg.velocity[1]) if len(msg.velocity) > 1 else 0.0
        self.current_speed_mps = math.hypot(vx, vy)
        self.last_velocity_time = now

    def _build_twist(self, linear_x: float, angular_z: float) -> Twist:
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.linear.y = 0.0
        msg.linear.z = 0.0
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = float(angular_z)
        return msg

    def _on_timer(self) -> None:
        if not self.motion_complete and self.integrated_distance_m >= self.target_distance:
            self.motion_complete = True
            self.get_logger().info(
                'Target distance reached. '
                f'integrated_distance={self.integrated_distance_m:.3f} m'
            )

        if self.motion_complete:
            self.cmd_pub.publish(self._build_twist(0.0, 0.0))
            self.stop_publish_count += 1
            if self.stop_publish_count >= 3:
                self.get_logger().info('Stop command published. Shutting down.')
                raise SystemExit
            return

        self.cmd_pub.publish(self._build_twist(self.speed, self.angular_speed))

    def publish_stop_commands(self, repeat: int = 5) -> None:
        """Publish zero velocity commands multiple times for a safe stop."""
        stop_msg = self._build_twist(0.0, 0.0)
        for _ in range(repeat):
            self.cmd_pub.publish(stop_msg)
            rclpy.spin_once(self, timeout_sec=0.05)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = DistanceMoveNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if node is not None:
            try:
                node.publish_stop_commands()
            except Exception:
                pass
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
