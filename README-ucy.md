# Train Ticket Workload Generator (LOCUST) Setup guide
## Introduction
The workload generator has the following characteristics:
- Implements a random dataset generator to create multiple users that can be used to access the benchmark during execution. This is achieved using the function InitCreateUsers. This implementation can be extended to randomly generate other models of the dataset, such as routes, search dates, types of foods, etc. 
- It is parameterized to scale the dataset to any number of users. Currently the user create parameter is --userCreate and can be used during the command line run of the workload generator, e.g.
  - ~/.local/bin/locust --class-picker --userCreate 1000
to create 1000 users. The default db users is 500 if it's not defined in the commandline.
- It implements the Poisson distribution of X user arrival times within a given time T. The rate of the poisson distribution is dynamically calculated as X/T.
- It allows to have multiple stages of the execution. This can be achieved by editing the "StagesShapeWithCustomUsers" and adding more stages. Examples in the source code demostrate how this can be done.
- It allows to set a drop query timeout time. This means that if a query takes longer than DROPQUERY_TIMEOUT for the response it will be considered as failed. If DROPQUERY_TIMEOUT is set to 0 then this feature is disabled. An example of this feature is demonstrated on the home function.
  
## WARNING: Login via SSH on the node, in our case is Node 1, the master, of the cluster that it's taint has been set so no trainticket service pods can be migrated to!!!

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

