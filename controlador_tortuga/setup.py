from setuptools import find_packages, setup

package_name = 'controlador_tortuga'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='brayan_mateo_bravo_l',
    maintainer_email='brayan_mateo_bravo_l@todo.todo',
    description='Controlador de modos, círculo y trayectoria para turtlesim.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'turtle_controller = controlador_tortuga.turtle_controller:principal',
        ],
    },
)
