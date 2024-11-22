ARG BASE_IMAGE=ubuntu:20.04
FROM ${BASE_IMAGE}
ENV container docker
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y software-properties-common expect sudo openssh-client virtualenv curl wget build-essential python3-setuptools python3-dev python3-pip python3-requests python3-psutil git
RUN pip3 install PyYaml netifaces
RUN adduser -u 1000 --disabled-password ubuntu
RUN echo "ubuntu ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    chmod 0440 /etc/sudoers.d/ubuntu
#Avoid sudo rlimit error
RUN echo "Set disable_coredump false" >> /etc/sudo.conf
USER ubuntu
WORKDIR /home/ubuntu
CMD [ "/bin/bash" ]
