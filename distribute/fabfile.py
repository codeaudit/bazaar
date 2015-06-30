from fabric.api import *
from fabric.tasks import execute
import os

def get_platform():
    with hide('everything'):
        return run("uname -s")

def is_installed(cmd):
    with settings(warn_only=True):
        with hide('everything'):
            result = run('command -v ' + cmd)
            return result.return_code == 0
    
def install_git():
    platform = get_platform()
    with hide():
        if platform == 'Darwin':
            run('sudo brew -y install git')
        if platform == 'Linux':
            run('sudo apt-get -y install git')

#def check_azure_credentials():
#    CRED_FILE="conf/credentials.publishsettings"
#    if not os.path.isfile(CRED_FILE):
#        print "Cannot find azure credentials at $CRED_FILE. Aborting."
#        print "You can download that file at "
#        print "         https://manage.windowsazure.com/publishsettings"
#        exit(1)
#    print "Using credentials at %s" % CRED_FILE

#def check_ec2_credentials():
#    CRED_FILE=os.getenv("HOME") + "/.aws/credentials"
#    if not os.path.isfile(CRED_FILE):
#        print "Cannot find ec2 credentials at $CRED_FILE. Aborting."
#        print "For more info, see "
#        print "       http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html"
#        exit(1)
#    CONF_FILE=os.getenv("HOME") + "/.aws/config"
#    if not os.path.isfile(CONF_FILE):
#        print "Cannot find ec2 config file $CONF_FILE. Aborting."
#        print "Make sure that the file contains the 'region' parameter. For more info, see "
#        print "       http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html"
#        exit(1)

@task
@hosts('localhost')
def launch(cloud, num):
    if cloud == "azure":
        #check_azure_credentials()
        local('./azure-client.py launch -n ' + num)
    if cloud == "ec-2" or cloud == "ec2":
        #check_ec2_credentials()
        local('./ec2-client.py launch -n ' + num)



@task 
@parallel
def install():
    ensure_hosts()
    platform = get_platform()
    #if not is_installed('git'):
    #    print('Node ' + env.host + ' does not have git installed!')
    #    install_git()
    #r = run('git clone https://github.com/hazyresearch/bazaar.git')
    #if not r.return_code == 0:
    #    print('ERROR. Aborting')
    #    sys.exit()
    #run('mkdir -p ~/parser')
    #put(local_path='../parser', remote_path='~')
    #r = run('cd ~/parser; chmod +x *.sh sbt/sbt; ./setup.sh')
    #if not r.return_code == 0:
    #    print('ERROR. Borting')
    #    sys.exit()
    put(local_path='installer/install-parser', remote_path='~/install-parser')
    r = run('cd ~; chmod +x ~/install-parser; ./install-parser')
    if not r.return_code == 0:
        print('ERROR. Aborting')
        sys.exit()    

@task
@parallel
def copy(input='test/INPUT',batch_size=1000):
    ensure_hosts()
    local('mkdir -p segments')
    local('split -a 5 -l ' + str(batch_size) + ' ' + input + ' segments/')
    run('mkdir -p ~/segments')
    num_machines = len(env.all_hosts)
    print(env.all_hosts)
    print(env.host_string)
    machine = env.all_hosts.index(env.host_string)

    output = local('find segments -type f', capture=True)
    files = output.split('\n')
    for f in files:
        file_num = hash(f) 
        file_machine = file_num % num_machines
        if file_machine == machine:
            print "put %s on machine %d" % (f, file_machine)
            put(local_path=f, remote_path='~/segments')

@task
@parallel
def echo():
    ensure_hosts()
    run('echo "$HOSTNAME"')

@task
@parallel
def parse():
    ensure_hosts()
    with prefix('export PATH=~/jdk1.8.0_45/bin:$PATH'):
        run('find ~/segments -name "*" -type f 2>/dev/null -print0 | xargs -0 -P 2 -L 1 bash -c \'cd ~/parser; ./run.sh -i json -k item_id -v content -f \"$0\"\'')

@task
@parallel
def collect():
    ensure_hosts()
    # collect all files ending in .parsed and .failed
    output = run('find ~/segments/ -name "*.*" -type f')
    if output == '':
       print('Warning: No result segments on node') 
    else:
       files = output.rstrip().split('\r\n')
       for f in files:
           path = f 
           get(local_path='segments', remote_path=path)
       local('rm -f result')
       local('find ./segments -name "*.parsed" -type f -print0 | xargs -P 1 -L 1 bash -c \'cat "$0" >> result\'')
       print('Done. You can now load the result into your database.')

@task
@hosts('localhost')
def terminate():
    ensure_hosts()
    cloud = read_cloud()
    if cloud == 'azure':
        local('./azure-client.py terminate')
    elif cloud == 'ec-2':
        local('./ec2-client.py terminate')
    else:
        print('Unknown cloud: ' + cloud)
        exit(1)

def read_cloud():
    if not os.path.isfile('.state/CLOUD'): 
        print('Could not find .state/CLOUD. Did you launch your machines already?')
        exit(1)
    return open('.state/CLOUD', 'r').readlines()[0].rstrip()

def read_hosts():
    if os.path.isfile('.state/HOSTS'):
        env.hosts = open('.state/HOSTS', 'r').readlines()
        env.user = "ubuntu"
        env.key_filename = "./ssh/bazaar.key"
    else:
        env.hosts = []

def ensure_hosts():
    if not os.path.isfile('.state/HOSTS'): 
        print('Could not find .state/HOSTS. Did you launch your machines already?')
        exit(1)

read_hosts()
