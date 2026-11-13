# Kafka Connect with the Debezium Postgres and MySQL connectors.

# Stage 1: download the connector plugins from Maven Central (HTTPS, pinned version).
FROM alpine:3.20 AS plugins
ARG DEBEZIUM_VERSION=2.7.3.Final
RUN mkdir /plugins && cd /plugins \
 && for connector in postgres mysql; do \
      wget -qO- "https://repo1.maven.org/maven2/io/debezium/debezium-connector-${connector}/${DEBEZIUM_VERSION}/debezium-connector-${connector}-${DEBEZIUM_VERSION}-plugin.tar.gz" \
      | tar -xz; \
    done

# Stage 2: Confluent's Kafka Connect, which already includes the Avro converter.
FROM confluentinc/cp-kafka-connect:7.9.0
COPY --from=plugins /plugins /usr/share/confluent-hub-components
