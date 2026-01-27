#!/bin/bash

# go into container

dir=$(pwd)/ansible/
cd $dir

INVENTORY_NAME=bjw3
PDU_ACTION=pdu_status
PDU_ACTION=pdu_reboot
# DEVICE_NAME=bjw3-can-8300-1
DEVICE_NAME=bjw3-can-720dt-9
./devutils -i ${INVENTORY_NAME} -a ${PDU_ACTION} -j -l ${DEVICE_NAME}
