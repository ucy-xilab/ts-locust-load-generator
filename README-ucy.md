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
cd ts-locust-load-generator/
mkdir output
~/.local/bin/locust

## Running using command line (where c220g1-030813.wisc.cloudlab.us is the hostname of the node that we will be running Locust)

### Ammend run_load_test file with the hostname of the server that the workload generator will be running
sed -i "s/192.168.2.12/c220g1-030813.wisc.cloudlab.us/g" run_load_test.py

## Running using WEB UI (where c220g1-030813.wisc.cloudlab.us is the hostname of the node that we will be running Locust)
Visit http://c220g1-030813.wisc.cloudlab.us:8089/ to start bench
### IMPORTANT!!!!: When Adding the URL on locust dashboard DO NOT ADD A TAILING SLASH, 
### e.g. 
### http://c220g1-030813.wisc.cloudlab.us:32677 IS CORRECT!!!
### http://c220g1-030813.wisc.cloudlab.us:32677/ IS WRONG!!! And will not allow the test to complete as the API pages with // will return 404 error
