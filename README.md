# RAFT Protocol Implementation

A cross-language (Python & Node.js) implementation of the RAFT consensus protocol for distributed systems. RAFT enables a cluster of nodes to agree on a replicated log, ensuring consistency and fault tolerance even in the presence of node failures or network partitions.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Overview](#project-overview)
- [Tags](#tags)
- [Implementation Notes](#implementation-notes)
- [Deployment Notes](#deployment-notes)
- [Test Cases](#test-cases)
- [Future Improvements](#future-improvements)

## Features

- **Leader Election**: Automatic leader selection with randomized election timeouts.
- **Log Replication**: Consistent replication of client operations across all nodes.
- **Dynamic Cluster Membership**: Nodes can join the cluster at runtime.
- **Client Operations**: Supports distributed addition operations with leader forwarding and retry logic.
- **State Management**: Persistent and volatile state tracking (term, votedFor, logs, commit index, etc.).
- **gRPC API**: All node-to-node and client-to-node communication via gRPC.
- **Detailed Logging**: Rich, timestamped logs for all major events and state transitions.
- **Error Handling**: Robust handling of network failures, node crashes, leader changes, and split votes.
- **Test Suite**: Markdown-based test cases for leader election, node joining, failure recovery, and client operations.
- **Multi-language Support**: Both Python and Node.js implementations for educational and interoperability purposes.
- **Dockerized Deployment**: Ready-to-use Dockerfiles and docker-compose for local cluster setup and testing.

## Tech Stack

- **Languages**: Python 3.9+, Node.js 16+
- **RPC Framework**: gRPC (with Protocol Buffers)
- **Python Libraries**:
  - `grpcio`, `grpcio-tools`, `protobuf`, `asyncio`
- **Node.js Libraries**:
  - `@grpc/grpc-js`, `@grpc/proto-loader`, `winston`, `async`
- **Containerization**: Docker, Docker Compose

## Project Overview

This project implements the RAFT consensus protocol, which is used to manage a replicated log across a distributed cluster. The protocol ensures that:

- Only one node acts as the leader at any time.
- All client operations are replicated and committed in the same order on all nodes.
- The system can tolerate node failures and recover gracefully.

**Key Concepts:**
- **States**: Follower, Candidate, Leader
- **RPCs**: RequestVote, AppendEntries, JoinCluster, Add, SubmitOperation, ForwardToLeader
- **Timeouts**: Election (20-30s), Heartbeat (6s)
- **Cluster Membership**: Nodes can join dynamically; leader updates configuration.

## Tags

`raft` `consensus` `distributed-systems` `replication` `gRPC` `python` `nodejs` `docker` `fault-tolerance` `leader-election` `log-replication` `cluster` `asyncio`

## Implementation Notes

- **State Management**: Each node tracks persistent (term, votedFor, log, config) and volatile (commit index, last applied, leader ID, etc.) state.
- **Leader Election**: Randomized timeouts prevent split votes; nodes vote for candidates with up-to-date logs.
- **Log Consistency**: AppendEntries RPC ensures logs are consistent; followers reject inconsistent entries.
- **Dynamic Membership**: JoinCluster RPC allows new nodes to join; leader updates and replicates new config.
- **Client Handling**: Clients can connect to any node; non-leaders forward requests to the current leader.
- **Error Handling**: Retries, leader redirection, and robust logging for all error scenarios.
- **Testing**: Markdown test cases and a dedicated test Dockerfile for automated cluster tests.

## Deployment Notes

### Prerequisites

- Docker & Docker Compose installed
- Python 3.9+ and/or Node.js 16+ (for manual runs)

### Quick Start (Docker Compose)

1. **Build and Start Cluster:**
   ```bash
   docker-compose up --build
   ```
   This will start 5 RAFT nodes and a test node.

2. **Run Client Operations:**
   ```bash
   docker exec -it <node_container> python client.py 5 3
   ```

3. **Logs:**
   - View logs with `docker-compose logs -f node1` (or any node).

### Manual (Python)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. raft.proto
   ```

2. **Start a node:**
   ```bash
   NODE_ID=1 PEER_IDS=2,3,4,5 python node.py
   ```

3. **Run the client:**
   ```bash
   python client.py 5 3
   ```

### Manual (Node.js)

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start a node:**
   ```bash
   NODE_ID=1 PEER_IDS=2,3,4,5 node node.js
   ```

## Test Cases

- **Leader Election**: Verifies correct leader selection and state transitions.
- **Leader Failure and Recovery**: Ensures new leader is elected and cluster remains consistent.
- **New Node Joining**: Tests dynamic membership and log catch-up.
- **Follower Catch-up**: Verifies log synchronization after downtime.
- **Client Operations**: Tests distributed addition, leader forwarding, and retry logic.

See `testcases/` for detailed markdown test scenarios.

## Future Improvements

- Persistent state storage (disk-based)
- Log snapshotting and compaction
- Support for more operation types
- Cluster resizing and reconfiguration
- Improved test automation and CI integration

---

**Implementation Authors:**  
- Python: `node.py`, `raft_node.py`, `client.py`  
- Node.js: `node.js`  
- Protocol Buffers: `raft.proto`

---

**License:** MIT
