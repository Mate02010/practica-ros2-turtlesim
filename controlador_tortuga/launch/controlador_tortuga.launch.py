from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='controlador_tortuga',
            executable='turtle_controller',
            name='turtle_controller',
            output='screen',
        )
    ])
