#!/usr/bin/env python3

from __future__ import print_function
import argparse
import pathlib
import re
import socket
import sys
import time
import git
import yaml
from __version__ import __version__


class VersionHelper():
    '''
    Maintain version information for git-controlled project
    See also https://github.com/jeffsw/buildhelper/
    See also VersionHelper --help
    '''
    from __version__ import __version__
    ARGS_REQUIRED = frozenset(['repo_path'])
    url = 'https://github.com/jeffsw/buildhelper/'

    def __init__(self, *args, **kwargs):
        self.args = dict(*args, **kwargs)
        for k in self.ARGS_REQUIRED:
            if k not in self.args:
                raise NameError("Required argument %s is missing." % (k));

        self.verbose = self.args['verbose']
        self.build_host = socket.gethostname()
        self.build_host = re.match('^([^.]+).', self.build_host).group(1)
        self.symbol_prefix = self.args['symbol_prefix']
        self.symbol_prefix_lower = self.symbol_prefix.lower()
        self.symbol_prefix_upper = self.symbol_prefix.upper()

        if type(self.args['touch']) == str:
            # User might have supplied a string (instead of list) in YAML config.
            print('#VersionHelper CONVERTING touch ARGUMENT FROM STRING TO LIST')
            self.args['touch'] = [ self.args['touch'] ]

        repo = git.repo.Repo(self.args['repo_path'])
        self.commit = repo.head.commit.hexsha
        self.describe = repo.git.describe(always=True, dirty=True, abbrev=40)
        self.time_str = time.asctime(time.gmtime())
        self.untracked = len(repo.untracked_files)
        self.dirty = int(repo.is_dirty())

        # Figure out the current branch name.
        ## @todo Improve this so it will work in detached head state.
        try:
            self.branch = repo.active_branch.name
        except TypeError:
            # GitPython repo.active_branch raises a TypeError if called when repo in detached head state
            self.branch = 'detached'

        # decide what the project's version string will be
        # store that in self.proj_version
        re1 = re.compile('(r|rel|release|v|ver|version)? [-/]? (([0-9abc.]+) (?:-([0-9]+)-g([0-9a-f]{40}))?)', re.I|re.X)
        rerv1 = re1.fullmatch(self.describe)
        if rerv1:
            self.proj_version = rerv1.group(2)
            self.proj_version_from = 'tag'
        else:
            re2 = re.compile('(r|rel|release|v|ver|version)? [-/]? ([0-9abc.]+)', re.I|re.X)
            rerv2 = re2.fullmatch(self.branch)
            if rerv2:
                self.proj_version = '%s.0.%d' % (rerv2.group(2), int(time.time()))
                self.proj_version_from = 'branch name'
            else:
                self.proj_version = '0.0.%d' % (int(time.time()))
                self.proj_version_from = 'not recognized; fallback to 0.0.time'
        if self.dirty:
            self.proj_version += '-dirty'
        if self.untracked:
            self.proj_version += '-untracked'

    def run_c(self):
        'Output C header file containing project version information'
        if 'c_file' not in self.args:
            return 0
        if not hasattr(self, 'c_symbol_prefix'):
            self.c_symbol_prefix = self.symbol_prefix
        self.c_symbol_prefix_lower = self.c_symbol_prefix.lower()
        self.c_symbol_prefix_upper = self.c_symbol_prefix.upper()

        htmp = open(self.args['c_template'], 'r')
        hstr = htmp.read()
        htmp.close()
        hout = open(self.args['c_file'], 'w')
        hout.write(hstr.format(self=self))
        hout.close()
        if self.verbose >= 1:
            print('#VersionHelper C {c_template} -> {c_file}'.format(
                c_template=self.args['c_template'],
                c_file=self.args['c_file']))
        return(1)

    def run_touch(self):
        'run the configured touch (update file timestamp) actions; returns number of files touched'
        effects = 0
        for filename in self.args['touch']:
            pn = pathlib.Path(filename)
            pn.touch()
            effects += 1
            if self.verbose >= 1:
                print('#VersionHelper touched %s' % (filename))
        return(effects)

    def run(self):
        'run the configured actions; returns the number of effects or 0 if none'
        if self.verbose >= 1:
            print('#VersionHelper running on {repo_path}'.format(repo_path=self.args['repo_path']))
        if self.verbose >= 2:
            print('proj_version: \"%s\"' % (self.proj_version))
            print('proj_version_from: \"%s\"' % (self.proj_version_from))
            print('branch: \"%s\"' % (self.branch))
            print('describe: \"%s\"' % (self.describe))
            print('time: \"%s\"' % (self.time_str))

        # Run method for each supported language
        effects = 0
        effects += self.run_c()
        effects += self.run_touch()
        return effects

def main():
    default_args = {
        'repo_path': './',
        'symbol_prefix': '',
        'touch': [],
        'c_template': 'BuildHelper/c.template',
        'py_template': 'BuildHelper/python.template',
    }

    ####################################
    # CLI general arguments
    ap = argparse.ArgumentParser(
        description='Maintain version definitions for git-controlled project',
        epilog='''
        Config is loaded from your repodir/VersionHelper.yml or the file
        specified by --cfg-file.  CLI arguments override the file.  For more
        information, see https://github.com/jeffsw/buildhelper/
        '''
        )
    ap.add_argument('--cfg-file', '-c', type=str, dest='cfg_file', action='store', default=argparse.SUPPRESS,
                    help='Configuration file in YAML format', metavar='VersionHelper.yml')
    ap.add_argument('--quiet', dest='quiet', action='count', default=0,
                    help="Don't print to stdout unless encountering errors")
    ap.add_argument('--repo-path', type=str, dest='repo_path', action='store', default=argparse.SUPPRESS,
                    help='Path to the git repository', metavar='repodir')
    ap.add_argument('--symbol-prefix', type=str, dest='symbol_prefix', action='store', default=argparse.SUPPRESS,
                    help='Prefix for variable names in output source files', metavar='MYPROJ_')
    ap.add_argument('--touch', type=str, dest='touch', action='append', default=argparse.SUPPRESS,
                    help='File to `touch` (update mtime) (option may be repeated)', metavar='version.c')
    ap.add_argument('--verbose', '-v', dest='verbose', action='count', default=0,
                    help='Increase verbosity')
    ap.add_argument('--version', dest='version', action='count', default=0,
                    help='Display BuildHelper version and exit')

    # CLI C language arguments
    apc = ap.add_argument_group(title='C language argmuents')
    apc.add_argument('--c-file', type=str, dest='c_file', action='store', default=argparse.SUPPRESS,
                     help='output filename', metavar='version.h')
    apc.add_argument('--c-template', type=str, dest='c_template', action='store', default=argparse.SUPPRESS,
                     help='template', metavar='c.template')
    apc.add_argument('--c-symbol-prefix', type=str, dest='c_symbol_prefix', action='store', default=argparse.SUPPRESS)

    # CLI Python language arguments
    apc = ap.add_argument_group(title='Python language arguments')
    apc.add_argument('--py-file', type=str, dest='py_file', action='store', default=argparse.SUPPRESS,
                     help='output filename', metavar='__version__.py')
    apc.add_argument('--py-template', type=str, dest='py_template', action='store', default=argparse.SUPPRESS,
                     help='template', metavar='python.template')

    cli_args = vars(ap.parse_args())
    # Finished with argparse
    ####################################

    if cli_args['version']:
        print('#VersionHelper version %s' % __version__)
        sys.exit(0)
    # If the user put --version on command line, just print the BuildHelper version and exit


    # Get configuration from YAML file (if there is one)
    cfg_fileobj = None
    yaml_args = {}
    if 'cfg_file' in cli_args:
        # If CLI supplied a config file we want open failure to raise an uncaught exception
        cfg_fileobj = open(cli_args['cfg_file'], 'r')
    else:
        # We're just looking in default place for config file; don't raise if config file not found
        if 'repo_path' in cli_args:
            repo_path = cli_args['repo_path']
        else:
            repo_path = default_args['repo_path']
        try:
            cfg_fileobj = open(repo_path + '/VersionHelper.yml', 'r')
        except FileNotFoundError:
            pass
    if cfg_fileobj:
        yaml_args = yaml.safe_load(cfg_fileobj)
        cfg_fileobj.close()

    # Merge the configs; CLI overrides YAML which overrides Defaults
    final_args = {}
    final_args.update(default_args)
    final_args.update(yaml_args)
    final_args.update(cli_args)

    # The real work happens in the VersionHelper class
    vh = VersionHelper(final_args)
    effects = vh.run()
    if effects == 0:
        print('#VersionHelper DID NOT DO ANYTHING.  CHECK YOUR CONFIG.')
    if effects > 0 and final_args['quiet'] == 0:
        print('#VersionHelper had %d effects' % (effects))

if __name__ == '__main__':
    main()
