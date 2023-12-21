# Description
This Dockerfile is used to build an OCI image includes testflinger-agent, testflinger-cli, testfliger-device-connector inside.
Testflinger-agent is the only application that running at beginning.
# How to build
```shell
docker build -t [where is the images registry]/[image name]:[tag] .
```

# Variables
There are some environment variables that could be used to change the setting:
|Variable|description|default|
|--|--|--|
|CONFIG\_DIR|where the configuration files are|/tmp/config|
|INFLUX\_HOST|for testflinger-agent|127.0.0.1|
|INFLUX\_PORT|for testflinger-agent|8086|
|INFLUX\_USER|for testflinger-agent|testflinger-agent|
|INFLUX\_PW|for testflinger-agent|testflinger-agent|
|DC\_CONFIG|configuration file of device-connector|device-connectors.yaml|
|DC\_DUT\_IP|DUT IP that device-connector will operate|127.0.0.1|
|DC\_DUT\_SID|secure id of DUT|aabbccdd|
|DC\_NODE\_ID|where the device-connector running is||
|DC\_NODE\_NAME|where the device-connector running is|staging-tfagent-cid-REPLACE\_TO\_HOSTNAME(This defualt value will replace `REPLACE_TO_HOSTNAME` to hostname. Therefore, you could use CID as the hostname while starting container)|
|DC\_MASS\_USER|mass user|bot|
|DC\_TIMEOUT|timeout of device-connector|120|
|AGENT\_CONFIG|configuration file of testflinger-agent|agent.yaml|
|AGENT\_ID|name of agent|same with `DC_AGENT_NAME`|
|TESTFLINGER\_SERVER|where the testflinger server is|https://testflinger.canonical.com|
|AGENT\_TIMEOUT|timeout of testflinger-agent|43200|
|AGENT\_OUTPUT\_TIMEOUT| output timeout of testflinger-agent|9000|
|AGENT\_EXEC\_DIR|where the testflinger-agent to store running info is|/testflinger/run/|
|AGENT\_LOG\_DIR|where the testflinger-agent to store log info is|/testflinger/log/|
|AGENT\_RESULT\_DIR|where the testflinger-agent to store result info is|/testflinger/result/|
|AGENT\_LOG\_LEVEL|log level of testflinger-agent|DEBUG|
|AGENT\_JOB\_QUEUE|the job queue the testflinger-agent listened|staging-job-cid-REPLACE\_TO\_HOSTNAME(This defualt value will replace `REPLACE_TO_HOSTNAME` to hostname. Therefore, you could use CID as the hostname while starting container)|
|AGENT\_SET\_CMD|set command of testflinger-agent|/bin/true|
|AGENT\_PROV\_CMD|provision command of testflinger-agent|/bin/true|
|AGENT\_CLEAN\_CMD|cleanup command of testflinger-agent|/bin/true|
|AGENT\_TEST\_CMD|test command of testflinger-agent|PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 testflinger-device-connector maas2 runtest -c ${CONFIG\_DIR}/${DC\_CONFIG} testflinger.json|

# How to start this container
```shell
docker run -d --rm -e INFLUX_HOST=[where it is] --hostname [CID] [images name]
```

The user in this conatiner is `root`, you don't have to add `sudo` before the command while root-privilege being needed. For security reason, this container should be ran by `rootless` container runtime.

# How to put configuration file into this container
The start script will check the configuration files are under `CONFIG_DIR` or not, you could mount volume that contain the configuration files to use your own setting without using too much environment varialbs.

