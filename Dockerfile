ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python MQTT library
RUN pip install paho-mqtt

# Copy data for add-on
COPY run.sh /
COPY gateway.py /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
