# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class TimedMoveNode(Node):
    """Publish cmd_vel for a fixed duration, then publish stop commands."""

    def __init__(self) -> None:
        super().__init__('timed_move_node')

        self.declare_parameter('speed', 0.0)
        self.declare_parameter('angular_speed', 0.0)
        self.declare_parameter('duration', 0.0)
        self.declare_parameter('publish_rate', 10.0)

        self.speed = float(self.get_parameter('speed').value)
        self.angular_speed = float(self.get_parameter('angular_speed').value)
        self.duration = float(self.get_parameter('duration').value)
        self.publish_rate = float(self.get_parameter('publish_rate').value)

        if self.publish_rate <= 0.0:
            raise ValueError('publish_rate must be greater than 0')
        if self.duration < 0.0:
            raise ValueError('duration must be >= 0')

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.start_time: Optional[float] = None
        self.motion_complete = False
        self.stop_publish_count = 0

        self.timer = self.create_timer(1.0 / self.publish_rate, self._on_timer)

        self.get_logger().info(
            'timed_move_node started with '
            f'speed={self.speed:.3f} m/s, '
            f'angular_speed={self.angular_speed:.3f} rad/s, '
            f'duration={self.duration:.3f} s'
        )

        if self.duration == 0.0:
            self.get_logger().info(
                'duration is 0.0 s, node will only publish stop commands.'
            )

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
        now = self.get_clock().now().nanoseconds / 1e9

        if self.start_time is None:
            self.start_time = now

        elapsed = now - self.start_time

        if not self.motion_complete and elapsed >= self.duration:
            self.motion_complete = True
            self.get_logger().info(
                f'Target duration reached. elapsed={elapsed:.3f} s'
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
        node = TimedMoveNode()
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
