#!/bin/bash

# if no testflinger-agent configuration create one
if [ ! -f "${CONFIG_DIR}/${AGENT_CONFIG}" ]; then
cat <<EOF >"${CONFIG_DIR}/${AGENT_CONFIG}"
agent_id: ${AGENT_ID}
server_address: ${TESTFLINGER_SERVER}
global_timeout: ${AGENT_TIMEOUT}
output_timeout: ${AGENT_OUTPUT_TIMEOUT}
execution_basedir: ${AGENT_EXEC_DIR}
logging_basedir: ${AGENT_LOG_DIR}
results_basedir: ${AGENT_RESULT_DIR}
logging_level: ${AGENT_LOG_LEVEL}
job_queues:
   - ${AGENT_JOB_QUEUE}
setup_command: ${AGENT_SET_CMD}
provision_command: ${AGENT_PROV_CMD}
test_command: ${AGENT_TEST_CMD}
cleanup_command: ${AGENT_CLEAN_CMD}
EOF
fi

# if no device-connectors configuration create one
if [ ! -f "${CONFIG_DIR}/${DC_CONFIG}" ]; then
cat <<EOF >"${CONFIG_DIR}/${DC_CONFIG}"
device_ip: ${DC_DUT_IP}
secure_id: ${DC_DUT_SID}
node_id: ${DC_NODE_ID}
node_name: ${DC_NODE_NAME}
agent_name: ${DC_AGENT_NAME}
maas_user: ${DC_MASS_USER}
timeout_min: ${DC_TIMEOUT}
env:
    HEXR_DEVICE_SECURE_ID: ${DC_DUT_SID}
    DEVICE_IP: ${DC_DUT_IP}
EOF
fi

# show usage
testflinger-agent -h
testflinger-cli -h
testflinger-device-connector -h

# replace placeholder "REPLACE_TO_HOSTNAME" to ${HOSTNAME}
sed -i s/REPLACE_TO_HOSTNAME/"${HOSTNAME}"/g "${CONFIG_DIR}/${AGENT_CONFIG}"
sed -i s/REPLACE_TO_HOSTNAME/"${HOSTNAME}"/g "${CONFIG_DIR}/${DC_CONFIG}"

# show agent information
echo "$(grep agent_id ${CONFIG_DIR}/${AGENT_CONFIG})" 
echo "$(grep -A 1 job_queues ${CONFIG_DIR}/${AGENT_CONFIG})"

# start testflinger-agent
if [ -z "${NO_AGENT_LOG}" ] ;then
    testflinger-agent -c "${CONFIG_DIR}/${AGENT_CONFIG}"
else
    testflinger-agent -c "${CONFIG_DIR}/${AGENT_CONFIG}" > /dev/null 2>&1
fi
