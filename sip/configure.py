import os
import glob
import sipconfig
import shutil
import numpy

shutil.copyfile("lima.sip","lima_tmp.sip")

sip_processlib = '../third-party/Processlib/sip'
espia_base = '/segfs/bliss/source/driver/linux-2.6/espia'
espia_incl = espia_base + '/src'
extra_includes = ['.', espia_incl,sip_processlib]
sipFile = file("lima_tmp.sip","a")
sipFile.write('\n')
sipFile.write('%Import ../third-party/Processlib/sip/processlib_tmp.sip\n')
for root,dirs,files in os.walk('..') :
    for dirname in dirs:
        if dirname == 'include':
            extra_includes.append(os.path.join(root,dirname))

    if root.find('third-party') > -1: continue

    for filename in files:
        if filename == 'lima.sip' or filename == 'lima_tmp.sip' : continue
        base,ext = os.path.splitext(filename)
        if ext != '.sip': continue
        sipFile.write('%%Include %s\n' % os.path.join(root,filename))
sipFile.close()
# The name of the SIP build file generated by SIP and used by the build
# system.
build_file = "lima.sbf"
config = sipconfig.Configuration()

# Run SIP to generate the code.
# module's specification files using the -I flag.
cmd = " ".join([config.sip_bin,"-g", "-e","-c", '.',
                "-b", build_file,"lima_tmp.sip"])
print cmd
os.system(cmd)

#little HACK for adding source
bfile = file(build_file)
whole_line = ''
for line in bfile :
    if 'sources' in line :
        begin,end = line.split('=')
        line = '%s = lima_init_numpy.cpp %s' % (begin,end)
    whole_line += line
bfile.close()
bfile = file(build_file,'w')
bfile.write(whole_line)
bfile.close()

# We are going to install the SIP specification file for this module and
# its configuration module.
installs = []

installs.append(["lima.sip", os.path.join(config.default_sip_dir, "lima")])

installs.append(["limaconfig.py", config.default_mod_dir])

# Create the Makefile.  The QtModuleMakefile class provided by the
# pyqtconfig module takes care of all the extra preprocessor, compiler and
# linker flags needed by the Qt library.
makefile = sipconfig.ModuleMakefile(
    configuration=config,
    build_file=build_file,
    installs=installs,
  )
makefile.extra_include_dirs = extra_includes
makefile.extra_libs = ['pthread','lima']
makefile.extra_lib_dirs = ['../build']
makefile.extra_cxxflags = ['-pthread']
makefile.extra_cxxflags.extend(['-I' + x for x in extra_includes])
# Add the library we are wrapping.  The name doesn't include any platform
# specific prefixes or extensions (e.g. the "lib" prefix on UNIX, or the
# ".dll" extension on Windows).
# None (for me)

# Generate the Makefile itself.
makefile.generate()

# Now we create the configuration module.  This is done by merging a Python
# dictionary (whose values are normally determined dynamically) with a
# (static) template.
content = {
    # Publish where the SIP specifications for this module will be
    # installed.
    "lima_sip_dir":    config.default_sip_dir
}

# This creates the pixmaptoolsconfig.py module from the pixmaptoolsconfig.py.in
# template and the dictionary.
sipconfig.create_config_module("limaconfig.py", "limaconfig.py.in", content)
