# Activity 3 - Flink 1.20 cluster image with PyFlink and the Kafka SQL connector.
# Same image is used for the JobManager and the TaskManager.
FROM flink:1.20.5

# Python 3.10 (Ubuntu jammy) for the PyFlink client that submits the job
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends python3 python3-pip \
 && ln -sf /usr/bin/python3 /usr/bin/python \
 && rm -rf /var/lib/apt/lists/*

# PyFlink must match the cluster version
RUN pip3 install --no-cache-dir apache-flink==1.20.5

# Kafka connector (fat SQL jar) on the cluster classpath
RUN wget -q -P /opt/flink/lib \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.4.0-1.20/flink-sql-connector-kafka-3.4.0-1.20.jar
