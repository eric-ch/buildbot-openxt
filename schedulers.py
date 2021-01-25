# -*- python -*-

from buildbot.plugins import (
    schedulers,
    util
)
from config.utils import codebases_to_params

def scheduler_force_custom(name, buttonName, builders, template_dfl, codebases_custom):
    return schedulers.ForceScheduler(
        name=name,
        buttonName=buttonName,
        label="Manual Custom build",
        reason=util.StringParameter(
            name="reason", label="Reason:", required=False, size=140
        ),
        builderNames=builders,
        codebases=codebases_to_params(codebases_custom),
        properties=[
            util.StringParameter(
                name="template", label="Configuration Template:",
                default=template_dfl
            )
        ])

def scheduler_force_stable(name, builders, template_dfl, codebases_stable):
    return schedulers.ForceScheduler(
        name=name,
        buttonName="Stable build",
        label="Trigger stable build",
        reason=util.StringParameter(
            name="reason", label="Reason:", required=False, size=140
        ),
        builderNames=builders,
        codebases=codebases_to_params(codebases_stable),
        properties=[
            util.StringParameter(
                name="template", label="Configuration Template:",
                default=template_dfl
            )
        ])

def scheduler_nightly(name, builders, template_dfl, codebases, hour, minute):
    return schedulers.Nightly(
        name=name,
        codebases=codebases,
        properties={
            'template': template_dfl
        },
        builderNames=builders,
        hour=hour,
        minute=minute,
        onlyIfChanged=True)

def scheduler_force_windows_tools(name, buttonName, builders, codebases):
    return schedulers.ForceScheduler(
        name=name,
        buttonName=buttonName,
        label="Manual Windows Tools build",
        reason=util.StringParameter(
            name="reason", label="Reason:", required=False, size=140
        ),
        builderNames=builders,
        codebases=codebases_to_params(codebases),
        properties=[
            util.ChoiceStringParameter(
                name="type", label="Build type:",
                choices=[ 'free', 'checked' ],
                default='checked'
            )
        ])

def scheduler_nightly_windows_tools(name, builders, codebases, hour, minute):
    return schedulers.Nightly(
        name=name,
        codebases=codebases,
        properties={ 'type': 'free' },
        builderNames=builders,
        hour=hour,
        minute=minute,
        onlyIfChanged=True)
