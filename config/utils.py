from buildbot.plugins import changes, util

# That's annoying....
def codebases_to_params(codebases):
    codebases_params = []
    for name, defaults in codebases.items():
        codebases_params.append(
            util.CodebaseParameter(
                codebase=name,
                repository=util.StringParameter(name='repository', default=defaults['repository']),
                branch=util.StringParameter(name='branch', default=defaults['branch']),
                revision=util.StringParameter(name='revision', default=defaults['revision']),
                project=None
            ))
    return codebases_params

#
# codebaseGenerator and dictionary generation from codebases configurations.
#
from config.custom_9 import codebases_custom_9
from config.custom_zeus import codebases_custom_zeus
from config.stable_zeus import codebases_stable_zeus
from config.custom_master import (
    codebases_custom_master,
)
from config.stable_master import codebases_stable_master

from config.windows_tools import (
    codebases_windows_tools_8_2_0,
    codebases_windows_tools_9_0_0,
)

all_repositories = {}
repo_branches = {}
for cb in [
        codebases_custom_9,
        codebases_custom_zeus,
        codebases_stable_zeus,
        codebases_custom_master,
        codebases_stable_master,
        codebases_windows_tools_8_2_0,
        codebases_windows_tools_9_0_0 ]:
    for name, defaults in cb.items():
        all_repositories[defaults['repository']] = name
        repo_branches.setdefault(defaults['repository'], []).append(defaults['branch'])

def codebaseGenerator(chdict):
    return all_repositories[chdict['repository']]

#
# Change tracking.
# Poll upstream codebases for changes every 4h.
#
pollinterval = 4 * 60 * 60
change_source = []
for repourl, branches in repo_branches.items():
    change_source.append(changes.GitPoller(
        repourl=repourl,
        branches=branches,
        pollinterval=pollinterval
    ))
