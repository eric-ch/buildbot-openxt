from buildbot.plugins import *
from buildbot.process.results import SUCCESS

# General notes:
# - Bitbake will print 'Bitbake still alive (5000s)' when busy building things
#   for a long time (webkitgtk/uim/etc), so Timeout after ~5000s
step_timeout = 5030

# Base environment:
# - Requires read access to the certificates to sign the build.
# - Requires read/write access to the download cache.
# The autobuilder tree should look like:
# | certs/
# | workdir_base/
# | workdir_base/downloads
# | workdir_base/<ver>-custom
# | workdir_base/<ver>-custom/certs -> ../../certs
# | workdir_base/<ver>-custom/downloads -> ../downloads
# | workdir_base/<ver>-stable
# | workdir_base/<ver>-stable/certs -> ../../certs
# | workdir_base/<ver>-stable/downloads -> ../downloads

# Steps wrappers.
def step_init_tree(workdir):
    return steps.ShellSequence(
        workdir=workdir,
        #hideStepIf=lambda results, s: results==SUCCESS,
        name='Initialize environment',
        haltOnFailure=True,
        commands=[
            util.ShellArg(command=['mkdir', '-p', '../downloads'],
                haltOnFailure=True, logfile='stdio'),
            util.ShellArg(command=['ln', '-sfT', '../downloads', 'downloads'],
                haltOnFailure=True, logfile='stdio'),
            util.ShellArg(command=['ln', '-sfT', '../../certs', 'certs'],
                haltOnFailure=True, logfile='stdio')
        ])

def step_remove_history(workdir):
    return steps.ShellCommand(
        workdir=workdir,
        name='Remove build history',
        haltOnFailure=True,
        command=[ '/bin/sh', '-c', util.Interpolate(" \
            find . -maxdepth 1 ! -path . -name '%(prop:buildername)s-[0-9]*' | \
            sort -V | \
            head -n-2 | \
            xargs rm -rf \
            ")])

def step_bordel_config(workdir, template, legacy=False, sstate_uri=""):
    return steps.ShellSequence(
        workdir=workdir,
        haltOnFailure=True,
        name='Configure source tree',
        commands=[
            util.ShellArg(command=[ './openxt/bordel/bordel', '-i', '0', 'config',
                '--default', '--force', '--rmwork', '-t', template ] +
                ([ '--no-repo-branch' ] if not legacy else []) +
                ([ '--sstate-mirror', sstate_uri ] if sstate_uri else []),
                haltOnFailure=True, logfile='stdio')
        ])

def step_set_build_id(workdir):
    return steps.ShellCommand(
        workdir=workdir,
        #hideStepIf=lambda results, s: results==SUCCESS,
        name='Set build ID',
        haltOnFailure=True,
        command=[ 'sed', '-i',
            '-e', util.Interpolate("s:^OPENXT_BUILD_ID\s*=.*:OPENXT_BUILD_ID=\"%(prop:buildnumber)s\":"),
            '-e', util.Interpolate("s:^OPENXT_VERSION\s*=.*:OPENXT_VERSION=\"%(prop:buildername)s\":"),
            './build-0/conf/openxt.conf'])

def step_bordel_layer_add(workdir, layer):
    return steps.ShellCommand(
        workdir=workdir,
        command=[ './openxt/bordel/bordel', 'layer', 'add', layer ],
        haltOnFailure=True,
        name='Add layer {}'.format(layer))

def step_bordel_build(workdir):
    return steps.ShellCommand(
        workdir=workdir,
        command=[ './openxt/bordel/bordel', '-i', '0', 'build' ],
        haltOnFailure=True, timeout=step_timeout,
        name='Build manifest')

def step_bordel_deploy(workdir):
    return steps.ShellCommand(
        workdir=workdir,
        command=[ './openxt/bordel/bordel', '-i', '0', 'deploy', 'iso' ],
        haltOnFailure=True,
        name='Assemble installer medium.')

# Upload the installation artefacts to the build-master.
def step_upload_installer(srcfmt, destfmt):
    destpath = destfmt + "/%(prop:buildername)s/%(prop:buildnumber)s"
    return steps.DirectoryUpload(
        name='Upload installer',
        workersrc=util.Interpolate(srcfmt + "/build-0/deploy"),
        masterdest=util.Interpolate(destpath),
        url=None)

# Upload the upgrade artefacts to the build-master.
def step_upload_upgrade(srcfmt, destfmt):
    destpath = destfmt + "/%(prop:buildername)s/%(prop:buildnumber)s"
    return steps.DirectoryUpload(
        name='Upload repository',
        workersrc=util.Interpolate(srcfmt + "/build-0/staging/repository"),
        masterdest=util.Interpolate(destpath + "/repository"),
        url=None)

# Clean sstate of recipes that cause problems as mirror
def step_clean_problematic(workfmt):
    return [
        steps.ShellSequence(
            workdir=util.Interpolate(workfmt + "/build-0"),
            name='Clean problematic sstate (dom0)',
            env={
                'BB_ENV_EXTRAWHITE': "MACHINE DISTRO BUILD_UID LAYERS_DIR",
                'LAYERS_DIR': util.Interpolate(workfmt + "/build-0/layers"),
                'BUILDDIR': util.Interpolate(workfmt + "/build-0"),
                'PATH': [ util.Interpolate(workfmt + "/build-0/layers/bitbake/bin"),
                          "${PATH}"],
                'MACHINE': "xenclient-dom0"
            },
            haltOnFailure=True,
            commands=[
                util.ShellArg(command=[ 'bitbake', 'ghc-native',
                    '-c', 'cleansstate' ],
                    haltOnFailure=True, logfile='stdio'),
                util.ShellArg(command=[ 'bitbake', 'ocaml-cross-x86_64',
                    '-c', 'cleansstate' ],
                    haltOnFailure=True, logfile='stdio'),
                util.ShellArg(command=[ 'bitbake', 'findlib-cross-x86_64',
                    '-c', 'cleansstate' ],
                    haltOnFailure=True, logfile='stdio')
            ]
        ),
        steps.ShellCommand(
            workdir=util.Interpolate(workfmt + "/build-0"),
            name='Clean problematic sstate (installer)',
            env={
                'BB_ENV_EXTRAWHITE': "MACHINE DISTRO BUILD_UID LAYERS_DIR",
                'LAYERS_DIR': util.Interpolate(workfmt + "/build-0/layers"),
                'BUILDDIR': util.Interpolate(workfmt + "/build-0"),
                'PATH': [ util.Interpolate(workfmt + "/build-0/layers/bitbake/bin"),
                          "${PATH}"],
                'MACHINE': "openxt-installer"
            },
            command=[ 'bitbake', 'xenclient-installer-image', '-c', 'cleansstate'],
            haltOnFailure=True
        )
    ]

# Flush and upload the sstate-cache to the build-master.
def step_upload_sstate(srcfmt, destfmt):
    destpath = destfmt + "/%(prop:buildername)s/sstate/"

    return [
        steps.MasterShellCommand(
            name="Remove stale shared-state.",
            hideStepIf=lambda results, s: results==SUCCESS,
            command=[ "rm", "-rf", util.Interpolate(destpath)]
        ),
        steps.MultipleFileUpload(
            name='Upload shared-state',
            workdir=util.Interpolate(srcfmt + '/sstate-cache'),
            workersrcs=['{:02x}'.format(n) for n in range(256)] + ['debian-10'],
            masterdest=util.Interpolate(destpath),
            url=None
        )
    ]

# Layout of the codebases for the different repositories for bordel.
codebase_layout = {
    'bats-suite': '/openxt/bats-suite',
    'bitbake': '/layers/bitbake',
    'bordel': '/openxt/bordel',
    'disman': '/openxt/disman',
    'fbtap': '/openxt/fbtap',
    'gene3fs': '/openxt/gene3fs',
    'glass': '/openxt/glass',
    'glassdrm': '/openxt/glassdrm',
    'icbinn': '/openxt/icbinn',
    'idl': '/openxt/idl',
    'input': '/openxt/input',
    'installer': '/openxt/installer',
    'ivc': '/openxt/ivc',
    'libedid': '/openxt/libedid',
    'libxcdbus': '/openxt/libxcdbus',
    'libxenbackend': '/openxt/libxenbackend',
    'linux-xen-argo': '/openxt/linux-xen-argo',
    'manager': '/openxt/manager',
    'meta-intel': '/layers/meta-intel',
    'meta-java': '/layers/meta-java',
    'meta-openembedded': '/layers/meta-openembedded',
    'meta-openxt-externalsrc': '/layers/meta-openxt-externalsrc',
    'meta-openxt-haskell-platform': '/layers/meta-openxt-haskell-platform',
    'meta-openxt-ocaml-platform': '/layers/meta-openxt-ocaml-platform',
    'meta-qt5': '/layers/meta-qt5',
    'meta-selinux': '/layers/meta-selinux',
    'meta-vglass': '/layers/meta-vglass',
    'meta-vglass-externalsrc': '/layers/meta-vglass-externalsrc',
    'meta-virtualization': '/layers/meta-virtualization',
    'network': '/openxt/network',
    'openembedded-core': '/layers/openembedded-core',
    'openxtfb': '/openxt/openxtfb',
    'pv-display-helper': '/openxt/pv-display-helper',
    'pv-linux-drivers': '/openxt/pv-linux-drivers',
    'resized': '/openxt/resized',
    'surfman': '/openxt/surfman',
    'sync-client': '/openxt/sync-client',
    'sync-wui': '/openxt/sync-wui',
    'toolstack': '/openxt/toolstack',
    'toolstack-data': '/openxt/toolstack-data',
    'uid': '/openxt/uid',
    'vusb-daemon': '/openxt/vusb-daemon',
    'xblanker': '/openxt/xblanker',
    'xclibs': '/openxt/xclibs',
    'xctools': '/openxt/xctools',
    'xenclient-oe': '/layers/xenclient-oe',
    'xenfb2': '/openxt/xenfb2',
    'xf86-video-openxtfb': '/openxt/xf86-video-openxtfb',
    'xsm-policy': '/openxt/xsm-policy',
}

# Factory for OpenXT+Bordel builds until stable-9.
# The bordel scripts used the bare-clone of each sub-project repository created
# by Repo-tool as a version-control mirror (SRC_URI in layer recipes).
def factory_bordel_legacy(workdir_base, deploy_base, codebases_oe):
    workdir_fmt = workdir_base + "/%(prop:buildername)s-%(prop:buildnumber)s"
    f = util.BuildFactory()
    # Clean up past artefacts (first to make space if need be).
    f.addStep(step_remove_history(workdir_base))
    # Fetch sources.
    for codebase, defaults in codebases_oe.items():
        destdir = codebase_layout.get(codebase, '/unknown/' + codebase)
        f.addStep(steps.Git(
            haltOnFailure=True,
            workdir=util.Interpolate(workdir_fmt + destdir),
            repourl=util.Interpolate('%(src:' + codebase + ':repository)s'),
            branch=util.Interpolate('%(src:' + codebase + ':branch)s'),
            codebase=codebase,
            mode='incremental', clobberOnFailure=True
        ))
        # Bordel relies on repo building bare mirrors in there.
        # This could be changed to point to the actual clones though.
        if destdir.startswith('/openxt'):
            bare_name = defaults['repository'].split('/')[-1]
            base_name = bare_name
            if bare_name.endswith('.git'):
                base_name = bare_name[:-4]
            f.addStep(steps.ShellSequence(
                workdir=util.Interpolate(workdir_fmt + '/.repo/projects/openxt'),
                name='Fake Repo bare repository mirror.',
                hideStepIf=lambda results, s: results==SUCCESS,
                haltOnFailure=True,
                commands=[
                    util.ShellArg(
                        command=['ln', '-sfT',
                            '../../../openxt/' + base_name + '/.git', bare_name ],
                        haltOnFailure=True, logfile='stdio'
                    ),
                    util.ShellArg(
                        command=['git', '-C', bare_name, 'branch', '-f', 'build-0' ],
                        haltOnFailure=True, logfile='stdio'
                    )]
            ))
    # Builder environment setup (handle first builds).
    f.addStep(step_init_tree(util.Interpolate(workdir_fmt)))
    # Build using bordel.
    f.addStep(step_bordel_config(util.Interpolate(workdir_fmt),
        util.Interpolate("%(prop:template)s"), legacy=True))
    f.addStep(step_set_build_id(util.Interpolate(workdir_fmt)))
    f.addStep(step_bordel_build(util.Interpolate(workdir_fmt)))
    f.addStep(step_bordel_deploy(util.Interpolate(workdir_fmt)))
    f.addStep(step_upload_installer(workdir_fmt, deploy_base))
    f.addStep(step_upload_upgrade(workdir_fmt, deploy_base))
    return f


# Factory for OpenXT+Bordel starting from branch "zeus" (post 9.x).
# Bordel can now use the layers directly without requiring a local mirror for
# each OpenXT sub-project. A few improvments:
# - This flavor can export a build shared-state.
# - Layers named '-externalsrc' present in codebases{}, are layered on top of
#   the given bblayers.conf provided by the template.
# - If provided, the builder will try to use the given mirror_sstate.
def factory_bordel(workdir_base, deploy_base, codebases, deploy_sstate=False,
        mirror_sstate=""):
    workdir_fmt = workdir_base + "/%(prop:buildername)s-%(prop:buildnumber)s"
    f = util.BuildFactory()
    # Remove past builds first.
    f.addStep(step_remove_history(workdir_base))
    # Fetch sources.
    for codebase, _ in codebases.items():
        destdir = codebase_layout.get(codebase, '/unknown/' + codebase)
        f.addStep(steps.Git(
            haltOnFailure=True,
            workdir=util.Interpolate(workdir_fmt + destdir),
            repourl=util.Interpolate('%(src:' + codebase + ':repository)s'),
            branch=util.Interpolate('%(src:' + codebase + ':branch)s'),
            codebase=codebase,
            mode='incremental', clobberOnFailure=True
        ))
    # Builder environment setup (handle first builds).
    f.addStep(step_init_tree(util.Interpolate(workdir_fmt)))
    # Configure the build environment.
    f.addStep(step_bordel_config(util.Interpolate(workdir_fmt),
        util.Interpolate("%(prop:template)s"), legacy=False, sstate_uri=mirror_sstate))
    # Add externalsrc layers if any.
    # Note: match '-externalsrc' in codebase name. It lets us re-use the same
    # templates as regular builds.
    for codebase, _ in { k: v for k, v in codebases.items() if '-externalsrc' in k }.items():
        f.addStep(step_bordel_layer_add(util.Interpolate(workdir_fmt), codebase))
    # Set build-id and build.
    f.addStep(step_set_build_id(util.Interpolate(workdir_fmt)))
    f.addStep(step_bordel_build(util.Interpolate(workdir_fmt)))
    f.addStep(step_bordel_deploy(util.Interpolate(workdir_fmt)))
    f.addStep(step_upload_installer(workdir_fmt, deploy_base))
    f.addStep(step_upload_upgrade(workdir_fmt, deploy_base))
    if deploy_sstate:
        f.addSteps(step_clean_problematic(workdir_fmt))
        f.addSteps(step_upload_sstate(workdir_fmt, deploy_base))
    return f
