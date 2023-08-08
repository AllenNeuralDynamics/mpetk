#!/usr/bin/env python
#   -*- coding: utf-8 -*-

from setuptools import setup
from setuptools.command.install import install as _install


class install(_install):
    def pre_install_script(self):
        pass

    def post_install_script(self):
        pass

    def run(self):
        self.pre_install_script()

        _install.run(self)

        self.post_install_script()


if __name__ == '__main__':
    setup(
        name='mpetk',
        version='0.4.6.dev3',
        description='configuration tools for mpe projects',
        long_description='configuration tools for mpe projects',
        long_description_content_type=None,
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Programming Language :: Python'
        ],
        keywords='',

        author='ross hytnen, ben sutton',
        author_email='rossh@alleninstitute.org, ben.sutton@alleninstitute.org',
        maintainer='',
        maintainer_email='',

        license='',

        url='http://stash.corp.alleninstitute.org/scm/~rossh/mpeconfig',
        project_urls={},

        scripts=[],
        packages=[
            'mpetk',
            'mpetk.aibsmw',
            'mpetk.aibsmw.aibsmw',
            'mpetk.aibsmw.routerio',
            'mpetk.lims',
            'mpetk.mpeconfig',
            'mpetk.mpeconfig.python_3',
            'mpetk.mtrain',
            'mpetk.piddl',
            'mpetk.zro'
        ],
        namespace_packages=[],
        py_modules=[],
        entry_points={
            'console_scripts': ['zk=zk:main']
        },
        data_files=[],
        package_data={
            'lib/site-packages/mpetk/mpeconfig/python_3/resources': [
                'mpetk/mpeconfig/python_3/resources/mpe_defaults_configuration.yml',
                'mpetk/mpeconfig/python_3/resources/mpe_defaults_logging.yml'],
            'mpetk/mpeconfig': ['python_3/resources/mpe_defaults_configuration.yml',
                                'python_3/resources/mpe_defaults_logging.yml']
        },
        install_requires=[
            'importlib_metadata==4.6.3',
            'kazoo==2.8.0',
            'pyyaml==5.3',
            'requests==2.25.1',
            'psutil==5.8.0',
            'protobuf==3.12.4',
            'graphviz==0.14.1',
            'pyzmq==19.0.2',
            'tornado==4.5.3',
            'watchdog==2.0.2',
            'zmq==0.0.0'
        ],
        dependency_links=[],
        zip_safe=True,
        cmdclass={'install': install},
        python_requires='',
        obsoletes=[],
    )
