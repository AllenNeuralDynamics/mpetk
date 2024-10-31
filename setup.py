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
        version='0.5.2.dev2',
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
            'mpetk.zro',
            'mpetk.teams',
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
            'kazoo~=2.10.0',
            'protobuf>=4.23.4,<=4.25.3',
            'psutil~=5.9.8',
            'pymsteams~=0.2.2',
            'PyYAML~=6.0.0',
            'pyzmq>=25.1.0,<=26.0.2',
            'redis~=5.0.4',
            'requests~=2.31.0',
            'tornado~=6.4',
            'urllib3~=2.2.1',
            'watchdog~=4.0.0',
            'pykeepass~=4.1.0'
        ],
        dependency_links=[],
        zip_safe=True,
        cmdclass={'install': install},
        python_requires='>=3.9.5,<=3.12.3',
        obsoletes=[],
    )
