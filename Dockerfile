FROM python:3.9-alpine

ENV HASSIO_DATA_PATH=/data

RUN apk add --no-cache python3

RUN mkdir /workdir
WORKDIR /workdir

COPY *.py run.sh /
RUN pip3 install pyyaml paho-mqtt pyserial
RUN chmod a+x /run.sh

CMD [ "sh", "/run.sh" ]
