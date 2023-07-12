# Train Ticket Workload Generator (LOCUST) Setup guide

## WARNING: Login via SSH on the node of the cluster that it's affinity has been set so no pods can be migrated!!!

## Clone repository
cd ~/trainticket/
mkdir testlocust
cd testlocust
git clone  --depth=1  https://github.com/ucy-xilab/ts-locust-load-generator

## Install Locust and numpy python packages
pip3 install locust
pip3 install numpy
source ~/.bashrc
cd ~/trainticket/testlocust/ts-locust-load-generator/
mkdir output

## Set hostname to master node, set open files limit to 10000, minimum required by locust and then run
export LOCUST_HOST=`hostname -A |awk '{print "http://"$1":32677"}'`
ulimit -n 10000
~/.local/bin/locust --class-picker

## Running using command line (where amd205.utah.cloudlab.us is the hostname of the node that we will be running Locust)

### Ammend run_load_test file with the hostname of the server that the workload generator will be running
sed -i "s/192.168.2.12/amd205.utah.cloudlab.us/g" run_load_test.py

## Running using WEB UI (where amd205.utah.cloudlab.us is the hostname of the node that we will be running Locust)
Visit http://amd205.utah.cloudlab.us:8089/ to start bench
### IMPORTANT!!!!: When Adding the URL on locust dashboard DO NOT ADD A TAILING SLASH, 
### e.g. 
### http://amd205.utah.cloudlab.us:32677 IS CORRECT!!!
### http://amd205.utah.cloudlab.us:32677/ IS WRONG!!! And will not allow the test to complete as the API pages with // will return 404 error


Microservices benchmark deployment for testing kubernetes cluster implementation on large scale microservices deployment using locust workload generator

