const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");
const winston = require("winston");
const async = require("async");

// Set up logging
const logger = winston.createLogger({
  level: "info",
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message }) => {
      return `${timestamp} ${level}: ${message}`;
    })
  ),
  transports: [new winston.transports.Console()],
});

// Load proto file
const packageDefinition = protoLoader.loadSync("raft.proto", {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const raftProto = grpc.loadPackageDefinition(packageDefinition).raft;

class RaftNode {
  constructor(nodeId, peerIds) {
    this.nodeId = nodeId;
    this.peerIds = peerIds;

    // Persistent state
    this.currentTerm = 0;
    this.votedFor = null;
    this.log = [];

    // Volatile state
    this.commitIndex = 0;
    this.lastApplied = 0;

    // Leader state
    this.nextIndex = new Map();
    this.matchIndex = new Map();

    // Node state
    this.state = "FOLLOWER";
    this.electionTimeout = Math.random() * 10 + 20; // Random between 20-30 seconds
    this.heartbeatTimeout = 6.0; // Increased from 3.0 to 6.0 seconds
    this.lastHeartbeat = Date.now();
    this.lastElectionTimeout = Date.now();
    this.lastLogTime = Date.now();
    this.logInterval = 4000; // Log every 4 seconds (doubled from 2)

    // Add debug counters
    this.electionAttempts = 0;
    this.heartbeatCount = 0;
    this.termChanges = 0;

    // gRPC clients
    this.clients = new Map();

    // Initialize gRPC clients
    for (const peerId of peerIds) {
      const client = new raftProto.RaftService(
        `node${peerId}:50051`,
        grpc.credentials.createInsecure()
      );
      this.clients.set(peerId, client);
    }

    // Pending operations
    this.pendingOperations = new Map();
  }

  async start() {
    const server = new grpc.Server();
    server.addService(raftProto.RaftService.service, {
      RequestVote: this.handleRequestVote.bind(this),
      AppendEntries: this.handleAppendEntries.bind(this),
      SubmitOperation: this.handleSubmitOperation.bind(this),
      ForwardToLeader: this.handleForwardToLeader.bind(this),
      GetLeader: this.GetLeader.bind(this),
      Add: this.handleAdd.bind(this),
    });

    await new Promise((resolve, reject) => {
      server.bindAsync(
        `0.0.0.0:50051`,
        grpc.ServerCredentials.createInsecure(),
        (err, port) => {
          if (err) {
            reject(err);
          } else {
            resolve(port);
          }
        }
      );
    });

    server.start();
    logger.info(`Node ${this.nodeId} started on port 50051`);

    // Start the main loop
    this.run();
  }

  async run() {
    while (true) {
      if (this.state === "FOLLOWER") {
        await this.runFollower();
      } else if (this.state === "CANDIDATE") {
        await this.runCandidate();
      } else if (this.state === "LEADER") {
        await this.runLeader();
      }
      await new Promise((resolve) => setTimeout(resolve, 2000)); // Sleep for 2 seconds (doubled from 1)
    }
  }

  async runFollower() {
    const timeSinceLastHeartbeat = (Date.now() - this.lastHeartbeat) / 1000;
    const timeSinceLastElection =
      (Date.now() - this.lastElectionTimeout) / 1000;
    const timeSinceLastLog = (Date.now() - this.lastLogTime) / 1000;

    if (timeSinceLastLog >= this.logInterval / 1000) {
      logger.info(
        `Node ${
          this.nodeId
        } follower state - Time since last heartbeat: ${timeSinceLastHeartbeat.toFixed(
          2
        )}s, Time since last election: ${timeSinceLastElection.toFixed(
          2
        )}s, Election timeout: ${this.electionTimeout.toFixed(2)}s, Term: ${
          this.currentTerm
        }, Election attempts: ${this.electionAttempts}`
      );
      this.lastLogTime = Date.now();
    }

    if (Date.now() - this.lastHeartbeat > this.electionTimeout * 1000) {
      logger.info(
        `Node ${this.nodeId} election timeout triggered. Current term: ${
          this.currentTerm
        }, Last heartbeat: ${new Date(
          this.lastHeartbeat
        ).toISOString()}, Election attempts: ${this.electionAttempts}`
      );
      this.state = "CANDIDATE";
      this.currentTerm++;
      this.termChanges++;
      this.votedFor = this.nodeId;
      this.lastElectionTimeout = Date.now();
      this.electionAttempts++;
      logger.info(
        `Node ${this.nodeId} new term after becoming candidate: ${this.currentTerm}, Total term changes: ${this.termChanges}`
      );
    }
  }

  async runCandidate() {
    logger.info(
      `Node ${this.nodeId} running as candidate with term ${this.currentTerm}`
    );
    let votesReceived = 1; // Vote for self
    this.electionTimeout = Math.random() * 10 + 20; // Fixed: Random between 20-30 seconds
    this.lastHeartbeat = Date.now();

    const request = {
      term: this.currentTerm,
      candidate_id: this.nodeId,
      last_log_index: this.log.length - 1,
      last_log_term:
        this.log.length > 0 ? this.log[this.log.length - 1].term : 0,
    };

    logger.info(
      `Node ${this.nodeId} starting election with request: ${JSON.stringify(
        request
      )}`
    );

    for (const [peerId, client] of this.clients) {
      try {
        logger.info(
          `Node ${this.nodeId} sends RPC RequestVote to Node ${peerId} with candidate_id: ${request.candidate_id}`
        );
        const response = await new Promise((resolve, reject) => {
          client.RequestVote(request, (err, response) => {
            if (err) reject(err);
            else resolve(response);
          });
        });

        logger.info(
          `Node ${
            this.nodeId
          } received vote response from Node ${peerId}: ${JSON.stringify(
            response
          )}`
        );

        if (response.term > this.currentTerm) {
          logger.info(
            `Node ${this.nodeId} stepping down due to higher term from Node ${peerId}`
          );
          this.currentTerm = response.term;
          this.state = "FOLLOWER";
          this.votedFor = null;
          return;
        }

        if (response.vote_granted) {
          votesReceived++;
          logger.info(
            `Node ${this.nodeId} received vote from Node ${peerId}. Total votes: ${votesReceived}`
          );
        }
      } catch (err) {
        logger.error(`Error requesting vote from node ${peerId}: ${err}`);
      }
    }

    logger.info(
      `Node ${
        this.nodeId
      } election results - Votes received: ${votesReceived}, Required: ${Math.ceil(
        this.peerIds.length / 2
      )}`
    );

    if (votesReceived > this.peerIds.length / 2) {
      logger.info(`Node ${this.nodeId} won election, becoming leader`);
      this.state = "LEADER";
      this.leader_id = this.nodeId;
      this.nextIndex = new Map(this.peerIds.map((id) => [id, this.log.length]));
      this.matchIndex = new Map(this.peerIds.map((id) => [id, 0]));
    } else {
      logger.info(`Node ${this.nodeId} lost election, becoming follower`);
      this.state = "FOLLOWER";
      this.votedFor = null;
      // Wait for a new election timeout before trying again
      await new Promise((resolve) =>
        setTimeout(resolve, this.electionTimeout * 1000)
      );
    }
  }

  async runLeader() {
    const timeSinceLastHeartbeat = (Date.now() - this.lastHeartbeat) / 1000;

    // Only send heartbeats if enough time has passed
    if (timeSinceLastHeartbeat >= this.heartbeatTimeout) {
      logger.info(
        `Node ${
          this.nodeId
        } leader state - Time since last heartbeat: ${timeSinceLastHeartbeat.toFixed(
          2
        )}s, Heartbeat timeout: ${this.heartbeatTimeout.toFixed(2)}s, Term: ${
          this.currentTerm
        }, Election attempts: ${this.electionAttempts}, Heartbeats sent: ${
          this.heartbeatCount
        }`
      );

      const request = {
        term: this.currentTerm,
        leader_id: this.nodeId,
        prev_log_index: 0,
        prev_log_term: 0,
        entries: this.log,
        leader_commit: this.commitIndex,
      };

      for (const [peerId, client] of this.clients) {
        try {
          logger.info(
            `Node ${this.nodeId} sends RPC AppendEntries to Node ${peerId}`
          );
          const response = await new Promise((resolve, reject) => {
            client.AppendEntries(request, (err, response) => {
              if (err) reject(err);
              else resolve(response);
            });
          });

          if (response.success) {
            this.matchIndex.set(peerId, this.log.length - 1);
            this.nextIndex.set(peerId, this.log.length);
          } else {
            this.nextIndex.set(
              peerId,
              Math.max(0, this.nextIndex.get(peerId) - 1)
            );
          }
        } catch (err) {
          logger.error(`Error sending heartbeat to node ${peerId}: ${err}`);
        }
      }

      // Check if we can commit any operations
      this.updateCommitIndex();

      this.heartbeatCount++;
      this.lastHeartbeat = Date.now();
    }

    // Small sleep to prevent CPU spinning
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  async handleRequestVote(call, callback) {
    const request = call.request;
    logger.info(
      `Node ${this.nodeId} runs RPC RequestVote called by Node ${request.candidate_id} with term ${request.term} (current term: ${this.currentTerm})`
    );
    logger.info(`Full request object: ${JSON.stringify(request)}`);

    if (!request.candidate_id) {
      logger.error(
        `Node ${
          this.nodeId
        } received vote request with undefined candidate_id. Full request: ${JSON.stringify(
          request
        )}`
      );
      callback(null, { term: this.currentTerm, vote_granted: false });
      return;
    }

    if (request.term < this.currentTerm) {
      logger.info(
        `Node ${this.nodeId} rejecting vote request due to stale term`
      );
      callback(null, { term: this.currentTerm, vote_granted: false });
      return;
    }

    if (request.term > this.currentTerm) {
      logger.info(`Node ${this.nodeId} updating term to ${request.term}`);
      this.currentTerm = request.term;
      this.state = "FOLLOWER";
      this.votedFor = null;
      this.electionTimeout = Math.random() * 10 + 20; // Fixed: Random between 20-30 seconds
      this.lastHeartbeat = Date.now();
    }

    const canVote =
      this.votedFor === null || this.votedFor === request.candidate_id;
    const logUpToDate =
      this.log.length === 0 ||
      request.last_log_term >= this.log[this.log.length - 1].term;

    logger.info(
      `Node ${this.nodeId} vote decision details: canVote=${canVote} (votedFor=${this.votedFor}), logUpToDate=${logUpToDate}, currentTerm=${this.currentTerm}, requestTerm=${request.term}`
    );

    if (canVote && logUpToDate) {
      this.votedFor = request.candidate_id;
      logger.info(
        `Node ${this.nodeId} granting vote to ${request.candidate_id}`
      );
      callback(null, { term: this.currentTerm, vote_granted: true });
    } else {
      logger.info(`Node ${this.nodeId} rejecting vote request`);
      callback(null, { term: this.currentTerm, vote_granted: false });
    }
  }

  async handleAppendEntries(call, callback) {
    const request = call.request;
    logger.info(
      `Node ${this.nodeId} runs RPC AppendEntries called by Node ${request.leader_id}`
    );

    if (request.term < this.currentTerm) {
      callback(null, { term: this.currentTerm, success: false });
      return;
    }

    this.lastHeartbeat = Date.now();

    if (request.term > this.currentTerm) {
      this.currentTerm = request.term;
      this.state = "FOLLOWER";
      this.votedFor = null;
    }

    // Check if log is consistent
    if (
      request.prev_log_index >= this.log.length ||
      (request.prev_log_index >= 0 &&
        this.log[request.prev_log_index].term !== request.prev_log_term)
    ) {
      callback(null, { term: this.currentTerm, success: false });
      return;
    }

    // Append new entries
    if (request.entries && request.entries.length > 0) {
      this.log = this.log
        .slice(0, request.prev_log_index + 1)
        .concat(request.entries);
    }

    // Update commit index
    if (request.leader_commit > this.commitIndex) {
      this.commitIndex = Math.min(request.leader_commit, this.log.length - 1);
      this.applyCommittedOperations();
    }

    callback(null, { term: this.currentTerm, success: true });
  }

  async handleSubmitOperation(call, callback) {
    const request = call.request;
    logger.info(
      `Node ${this.nodeId} received operation from client ${request.client_id}`
    );

    if (this.state !== "LEADER") {
      // Forward to leader
      for (const [peerId, client] of this.clients) {
        try {
          logger.info(
            `Node ${this.nodeId} forwards operation to Node ${peerId}`
          );
          const response = await new Promise((resolve, reject) => {
            client.ForwardToLeader(request, (err, response) => {
              if (err) reject(err);
              else resolve(response);
            });
          });

          if (response.leader_id) {
            callback(null, {
              success: false,
              result: `Not leader. Forwarded to leader ${response.leader_id}`,
              leader_id: response.leader_id,
            });
            return;
          }
        } catch (err) {
          logger.error(`Error forwarding operation to node ${peerId}: ${err}`);
        }
      }

      callback(null, {
        success: false,
        result: "No leader found",
        leader_id: null,
      });
      return;
    }

    // Add operation to log
    const logEntry = {
      term: this.currentTerm,
      command: request.operation,
      index: this.log.length,
      committed: false,
    };

    this.log.push(logEntry);
    this.pendingOperations.set(logEntry.index, {
      operation: request.operation,
      client_id: request.client_id,
      callback: callback,
    });

    // Wait for commit
    // The response will be sent when the operation is committed
  }

  async handleForwardToLeader(call, callback) {
    const request = call.request;
    logger.info(
      `Node ${this.nodeId} received forwarded operation from client ${request.client_id}`
    );

    if (this.state === "LEADER") {
      // Process the operation
      await this.handleSubmitOperation(call, callback);
    } else {
      callback(null, {
        success: false,
        result: "Not leader",
        leader_id: this.leader_id || null,
      });
    }
  }

  updateCommitIndex() {
    // Find the highest index that has been replicated on a majority of servers
    const matchIndices = Array.from(this.matchIndex.values()).sort(
      (a, b) => a - b
    );
    const majorityIndex = matchIndices[Math.floor(this.peerIds.length / 2)];

    if (majorityIndex > this.commitIndex) {
      this.commitIndex = majorityIndex;
      this.applyCommittedOperations();
    }
  }

  applyCommittedOperations() {
    // Apply all operations up to commitIndex
    for (let i = this.lastApplied + 1; i <= this.commitIndex; i++) {
      const operation = this.pendingOperations.get(i);
      if (operation) {
        // Execute the operation
        const result = `Executed: ${operation.operation}`;
        operation.callback(null, {
          success: true,
          result: result,
          leader_id: this.nodeId,
        });
        this.pendingOperations.delete(i);
      }
      this.log[i].committed = true;
    }
    this.lastApplied = this.commitIndex;
  }

  async startElection() {
    logger.info(
      `Node ${this.nodeId} starting election for term ${this.currentTerm + 1}`
    );
    this.currentTerm++;
    this.state = "CANDIDATE";
    this.votedFor = this.nodeId;

    const request = {
      term: this.currentTerm,
      candidate_id: this.nodeId,
      last_log_index: this.log.length - 1,
      last_log_term:
        this.log.length > 0 ? this.log[this.log.length - 1].term : 0,
    };

    logger.info(
      `Node ${this.nodeId} sending vote requests with candidate_id: ${this.nodeId}`
    );
    logger.info(`Full request object: ${JSON.stringify(request)}`);

    let votesReceived = 1; // Count our own vote
    const votesNeeded = Math.floor(this.peerIds.length / 2) + 1;

    for (const [peerId, client] of this.clients) {
      try {
        logger.info(
          `Node ${this.nodeId} sending RequestVote to Node ${peerId}`
        );
        const response = await new Promise((resolve, reject) => {
          client.RequestVote(request, (err, response) => {
            if (err) reject(err);
            else resolve(response);
          });
        });

        if (response.term > this.currentTerm) {
          logger.info(
            `Node ${this.nodeId} stepping down due to higher term from Node ${peerId}`
          );
          this.currentTerm = response.term;
          this.state = "FOLLOWER";
          this.votedFor = null;
          return;
        }

        if (response.vote_granted) {
          votesReceived++;
          logger.info(
            `Node ${this.nodeId} received vote from Node ${peerId}. Total votes: ${votesReceived}`
          );
        }
      } catch (err) {
        logger.error(`Error requesting vote from node ${peerId}: ${err}`);
      }
    }

    if (votesReceived >= votesNeeded) {
      logger.info(
        `Node ${this.nodeId} won election with ${votesReceived} votes`
      );
      this.state = "LEADER";
      this.leader_id = this.nodeId;
      this.nextIndex = new Map(this.peerIds.map((id) => [id, this.log.length]));
      this.matchIndex = new Map(this.peerIds.map((id) => [id, 0]));
    } else {
      logger.info(
        `Node ${this.nodeId} lost election with ${votesReceived} votes`
      );
      this.state = "FOLLOWER";
    }
  }

  async handleClientOperation(operation) {
    if (this.state !== "LEADER") {
      // Forward to leader
      logger.info(`Node ${this.nodeId} forwarding operation to leader`);

      // Try to find the leader by asking other nodes
      for (const peerId of this.peerIds) {
        if (peerId !== this.nodeId) {
          try {
            const response = await this.clients.get(peerId).GetLeader({});
            if (response.leaderId) {
              // Forward the operation to the leader
              logger.info(
                `Node ${this.nodeId} forwarding operation to leader Node ${response.leaderId}`
              );
              await this.clients
                .get(response.leaderId)
                .SubmitOperation({ operation });
              return;
            }
          } catch (err) {
            logger.error(`Error getting leader from node ${peerId}: ${err}`);
          }
        }
      }

      logger.error(
        `Node ${this.nodeId} could not find leader to forward operation`
      );
      return;
    }

    // Append operation to log
    const logEntry = {
      term: this.currentTerm,
      operation: operation,
      index: this.log.length,
    };
    this.log.push(logEntry);

    // Send AppendEntries RPC to all followers
    for (const peerId of this.peerIds) {
      if (peerId !== this.nodeId) {
        const request = {
          term: this.currentTerm,
          leaderId: this.nodeId,
          prevLogIndex: this.nextIndex.get(peerId) - 1,
          prevLogTerm: this.log[this.nextIndex.get(peerId) - 1]?.term || 0,
          entries: this.log.slice(this.nextIndex.get(peerId)),
          leaderCommit: this.commitIndex,
        };

        try {
          logger.info(
            `Node ${this.nodeId} sends RPC AppendEntries to Node ${peerId}`
          );
          const response = await this.clients
            .get(peerId)
            .AppendEntries(request);

          if (response.success) {
            this.nextIndex.set(peerId, this.log.length);
            this.matchIndex.set(peerId, this.log.length - 1);
          } else {
            this.nextIndex.set(
              peerId,
              Math.max(0, this.nextIndex.get(peerId) - 1)
            );
          }
        } catch (err) {
          logger.error(`Error sending AppendEntries to node ${peerId}: ${err}`);
        }
      }
    }

    // Check if we can commit the operation
    const matchIndices = Array.from(this.matchIndex.values());
    const majorityIndex = matchIndices[Math.floor(this.peerIds.length / 2)];

    if (majorityIndex > this.commitIndex) {
      this.commitIndex = majorityIndex;
      // Apply committed operations
      while (this.lastApplied < this.commitIndex) {
        this.lastApplied++;
        const operation = this.log[this.lastApplied].operation;
        // Execute operation
        logger.info(`Node ${this.nodeId} executing operation: ${operation}`);
      }
    }
  }

  async GetLeader(request) {
    if (this.state === "LEADER") {
      return { leaderId: this.nodeId };
    }
    return { leaderId: null };
  }

  async SubmitOperation(request) {
    if (this.state !== "LEADER") {
      // Forward to leader
      return this.handleClientOperation(request.operation);
    }

    // Process operation as leader
    return this.handleClientOperation(request.operation);
  }

  async handleAdd(call, callback) {
    // If not leader, forward to leader
    if (this.state !== "LEADER") {
      if (this.leaderId) {
        try {
          const client = this.clients.get(this.leaderId);
          client.Add(call.request, (err, response) => {
            if (err) {
              callback(null, {
                success: false,
                error: `Failed to forward to leader: ${err.message}`,
              });
            } else {
              callback(null, response);
            }
          });
          return;
        } catch (err) {
          callback(null, {
            success: false,
            error: `Failed to forward to leader: ${err.message}`,
          });
          return;
        }
      } else {
        callback(null, {
          success: false,
          error: "No leader available",
        });
        return;
      }
    }

    try {
      // Perform addition
      const sum = call.request.num1 + call.request.num2;

      // Create log entry
      const entry = {
        term: this.currentTerm,
        command: `ADD ${call.request.num1} ${call.request.num2}`,
        index: this.log.length,
      };

      // Append to log
      this.log.push(entry);

      callback(null, {
        sum: sum,
        success: true,
        error: "",
      });
    } catch (err) {
      callback(null, {
        success: false,
        error: `Error performing addition: ${err.message}`,
      });
    }
  }
}

// Start the node
const nodeId = parseInt(process.env.NODE_ID);
const peerIds = process.env.PEER_IDS.split(",").map((id) => parseInt(id));

const node = new RaftNode(nodeId, peerIds);
node.start().catch((err) => {
  logger.error(`Error starting node ${nodeId}: ${err}`);
  process.exit(1);
});
