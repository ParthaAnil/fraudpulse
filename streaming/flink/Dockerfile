# Flink with the Kafka connector and the Avro + Schema Registry formats.

# Stage 1: download the connector jars from Maven Central and check them against pinned
# SHA-256 checksums, so a changed or tampered file stops the build.
FROM alpine:3.20 AS jars
ARG MAVEN=https://repo1.maven.org/maven2/org/apache/flink
WORKDIR /jars
RUN wget -q "$MAVEN/flink-sql-connector-kafka/5.0.0-2.2/flink-sql-connector-kafka-5.0.0-2.2.jar" \
 && wget -q "$MAVEN/flink-sql-avro-confluent-registry/2.2.1/flink-sql-avro-confluent-registry-2.2.1.jar" \
 && printf '%s  %s\n' \
      5605c691d11a501382c383fecba37a7a552467da5ab7ba904ef5d6f3d62c5616 flink-sql-connector-kafka-5.0.0-2.2.jar \
      9f37aacbbcf7c7b5dd34dd673b16f83c4f18787337cea8e6378c71a7e7405c9a flink-sql-avro-confluent-registry-2.2.1.jar \
    | sha256sum -c -

# Stage 2: the official Flink image, plus the jars.
FROM flink:2.2.1-scala_2.12-java17
COPY --from=jars --chown=flink:flink /jars/ /opt/flink/lib/
# Checkpoints are written here (a shared volume). Owned by the flink user, who runs Flink.
RUN mkdir -p /opt/flink/checkpoints && chown flink:flink /opt/flink/checkpoints
