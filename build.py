import itertools
import os

from pybuilder.core import use_plugin, init, Author

# plugins
use_plugin('python.distutils')
use_plugin('python.core')
use_plugin('python.install_dependencies')
# use_plugin('python.flake8')
# use_plugin('pypi:pybuilder_pytest')
#use_plugin('pypi:pybuilder_pytest_coverage')

#use_plugin('python.sphinx')
default_task = ['install_dependencies',
                #'analyze',
                # 'run_unit_tests',
                #'sphinx_generate_documentation',
                'publish']

# project meta
name = 'mpetk'
version = '0.4.4.dev0'
summary = 'configuration tools for mpe projects'
description = __doc__
authors = (Author('ross hytnen', 'rossh@alleninstitute.org'),
           Author('ben sutton', 'ben.sutton@alleninstitute.org'),)
url = 'http://stash.corp.alleninstitute.org/scm/~rossh/mpeconfig'


def add_files_to_project(project, path):
    top = f'src/{path}'
    resource_patterns = ['yaml', 'yml', 'png', 'jpeg', 'jpeg', 'ui', 'json', 'ico']
    for directory, subdirectory, files in os.walk(top):
        directory = directory.replace(f'{top}\\', '').replace('\\', '/')
        directory = directory.replace(f'{top}/', '')

        for file, pattern in itertools.product(files, resource_patterns):
            if pattern in file.lower():
                project.include_file(path, directory + '/' + file)



@init
def initialize(project):
    project.set_property('verbose', True)

    # modules / di  st
    project.set_property('dir_source_main_python', 'src')
    project.set_property('dir_source_main_scripts', 'scripts')
    project.set_property('dir_dist', 'dist/{0}-{1}'.format(name, version))

    # testing
    project.set_property('dir_source_pytest_python', "tests")
    #project.set_property_if_unset("pytest_coverage_break_build_threshold", 50)

    # deployment
    # project.install_dependencies_index_url = 'http://aibspi:3141/aibs/dev'
    # project.install_dependencies_insecure_installation = ['aibspi']

    # documentation
    project.set_property('dir_docs', 'docs')
    project.set_property('sphinx_config_path', 'docs/')
    project.set_property('sphinx_source_dir', 'docs/')
    project.set_property('sphinx_output_dir', 'docs/_build/html')
    project.set_property('sphinx_builder', 'html')

    # linting
    project.set_property('flake8_break_build', False)
    project.set_property('flake8_include_scripts', True)
    project.set_property('flake8_include_test_sources', True)

    # dependencies
    project.build_depends_on_requirements('requirements_dev.txt')
    project.depends_on_requirements('requirements.txt')

    # entry points (typically the .py files in mpeconfig
    project.set_property('distutils_entry_points',
                         {'console_scripts': [
                             'zk=zk:main']})

    for d in ['mptk/aibsmw', 'mptk/lims', 'mpetk/mpeconfig', 'mpetk/piddl', 'mpetk/zro']:
        add_files_to_project(project, d)
    project.include_file('lib/site-packages/mpetk/mpeconfig/python_3/resources',
                         'mpetk/mpeconfig/python_3/resources/mpe_defaults_configuration.yml')
    project.include_file('lib/site-packages/mpetk/mpeconfig/python_3/resources',
                         'mpetk/mpeconfig/python_3/resources/mpe_defaults_logging.yml')
