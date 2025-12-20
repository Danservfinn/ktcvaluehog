# Neo4j Docker Image for Railway Deployment
# Uses socat to proxy Railway's PORT to Neo4j's 7474

FROM neo4j:5.15-community

# Install socat for port proxying
USER root
RUN apt-get update && apt-get install -y socat && rm -rf /var/lib/apt/lists/*
USER neo4j

# Neo4j configuration
ENV NEO4J_AUTH=neo4j/dynastyedge2025
ENV NEO4J_server_memory_pagecache_size=512m
ENV NEO4J_server_memory_heap_initial__size=512m
ENV NEO4J_server_memory_heap_max__size=1g

# Network configuration
ENV NEO4J_server_bolt_enabled=true
ENV NEO4J_server_bolt_listen__address=0.0.0.0:7687
ENV NEO4J_server_http_enabled=true
ENV NEO4J_server_http_listen__address=0.0.0.0:7474
ENV NEO4J_server_default__listen__address=0.0.0.0

# APOC
ENV NEO4J_dbms_security_procedures_unrestricted=apoc.*
ENV NEO4J_dbms_security_procedures_allowlist=apoc.*

EXPOSE 7474 7687

# Start script that proxies Railway PORT to Neo4j 7474
CMD sh -c 'neo4j start && sleep 10 && socat TCP-LISTEN:${PORT:-8080},fork,reuseaddr TCP:localhost:7474'
