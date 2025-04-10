import os
import asyncio
import random
import time
import grpc
from concurrent import futures
import logging
from typing import List, Dict, Optional, Any
import raft_pb2
import raft_pb2_grpc

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class State:
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"

class RaftNode(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node_id: int, peer_ids: List[int]):
        self.node_id = node_id
        self.peer_ids = list(peer_ids)  # Convert to list to allow modifications
        self.state = State.FOLLOWER
        
        # Persistent state
        self.current_term = 0
        self.voted_for = None
        self.log: List[raft_pb2.LogEntry] = []
        
        # Cluster membership state
        self.cluster_config = raft_pb2.ClusterConfig()
        self.cluster_config.nodes.append(self.node_id)
        self.cluster_config.nodes.extend(self.peer_ids)
        self.cluster_config.version = 0
        self.pending_joins = set()
        
        # Initialize leader state
        self.next_index = {peer_id: 0 for peer_id in self.peer_ids}
        self.match_index = {peer_id: -1 for peer_id in self.peer_ids}
        
        # Volatile state
        self.commit_index = 0
        self.last_applied = 0
        self.leader_id = None  # Current leader's ID
        self.election_attempts = 0  # Number of times node has attempted election
        self.heartbeats_sent = 0  # Number of heartbeats sent as leader
        self.last_heartbeat_as_leader = 0  # Last time heartbeat was sent as leader
        
        # Node state
        self.election_timeout = random.uniform(20, 30)  # Random timeout between 20-30 seconds
        self.heartbeat_timeout = 6.0  # Heartbeat interval of 6 seconds
        self.last_heartbeat = time.time()
        self.log_interval = 4.0  # Log every 4 seconds
        self.last_log_time = time.time()
        
        # gRPC channels and stubs
        self.channels: Dict[int, grpc.aio.Channel] = {}
        self.stubs: Dict[int, raft_pb2_grpc.RaftServiceStub] = {}
        
        # Initialize gRPC connections
        for peer_id in peer_ids:
            channel = grpc.aio.insecure_channel(f'node{peer_id}:50051')
            self.channels[peer_id] = channel
            self.stubs[peer_id] = raft_pb2_grpc.RaftServiceStub(channel)

    async def RequestVote(self, request: raft_pb2.RequestVoteRequest, context) -> raft_pb2.RequestVoteResponse:
        logger.info(f"Node {self.node_id} runs RPC RequestVote called by Node {request.candidate_id}")
        
        if request.term < self.current_term:
            return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)
        
        if (self.voted_for is None or self.voted_for == request.candidate_id) and \
           (not self.log or request.last_log_term >= self.log[-1].term):
            self.voted_for = request.candidate_id
            return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=True)
        
        return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)

    async def AppendEntries(self, request: raft_pb2.AppendEntriesRequest, context) -> raft_pb2.AppendEntriesResponse:
        logger.info(f"Node {self.node_id} runs RPC AppendEntries called by Node {request.leader_id}")
        
        if request.term < self.current_term:
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)
        
        self.last_heartbeat = time.time()
        self.leader_id = request.leader_id  # Update leader ID
        
        if request.term > self.current_term:
            self.current_term = request.term
            self.state = State.FOLLOWER
            self.voted_for = None
        
        # Check if log is consistent
        if request.prev_log_index >= len(self.log) or \
           (request.prev_log_index >= 0 and self.log[request.prev_log_index].term != request.prev_log_term):
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)
        
        # Append new entries
        if request.entries:
            self.log = self.log[:request.prev_log_index + 1] + list(request.entries)
        
        # Update commit index
        if request.leader_commit > self.commit_index:
            self.commit_index = min(request.leader_commit, len(self.log) - 1)
        
        # Handle configuration changes
        for entry in request.entries:
            if 'CONFIG_CHANGE' in entry.command:
                config_change = entry.config_change
                if config_change:
                    self.cluster_config = config_change.new_config
                    
                    # If this is an ADD_NODE operation, setup connection to new node
                    if 'ADD_NODE' in entry.command:
                        new_node_id = config_change.node_id
                        if new_node_id not in self.peer_ids:
                            self.peer_ids.append(new_node_id)
                            channel = grpc.aio.insecure_channel(f'node{new_node_id}:50051')
                            self.channels[new_node_id] = channel
                            self.stubs[new_node_id] = raft_pb2_grpc.RaftServiceStub(channel)
        
        return raft_pb2.AppendEntriesResponse(term=self.current_term, success=True)

    async def run_follower(self):
        if time.time() - self.last_heartbeat > self.election_timeout:
            logger.info(f"Node {self.node_id} election timeout, becoming candidate")
            self.state = State.CANDIDATE
            self.current_term += 1
            self.voted_for = self.node_id

    async def run_candidate(self):
        votes_received = 1  # Vote for self
        self.election_timeout = random.uniform(20, 30)  # Fixed: Using correct timeout range
        self.last_heartbeat = time.time()
        
        # Request votes from all peers
        for peer_id in self.peer_ids:
            try:
                request = raft_pb2.RequestVoteRequest(
                    term=self.current_term,
                    candidate_id=self.node_id,
                    last_log_index=len(self.log) - 1,
                    last_log_term=self.log[-1].term if self.log else 0
                )
                logger.info(f"Node {self.node_id} sends RPC RequestVote to Node {peer_id}")
                response = await self.stubs[peer_id].RequestVote(request)
                if response.vote_granted:
                    votes_received += 1
            except Exception as e:
                logger.error(f"Error requesting vote from node {peer_id}: {e}")
        
        if votes_received > len(self.peer_ids) / 2:
            logger.info(f"Node {self.node_id} won election, becoming leader")
            self.state = State.LEADER
            for peer_id in self.peer_ids:
                self.next_index[peer_id] = len(self.log)
                self.match_index[peer_id] = 0

    async def run_leader(self):
        # Send heartbeats immediately upon becoming leader if this is our first time
        if not hasattr(self, 'last_heartbeat_as_leader'):
            self.last_heartbeat_as_leader = 0
            self.heartbeats_sent = 0
            await self.send_heartbeats()
        
        time_since_heartbeat = time.time() - self.last_heartbeat_as_leader
        time_since_log = time.time() - self.last_log_time
        
        # Log state periodically
        if time_since_log >= self.log_interval:
            logger.info(
                f"Node {self.node_id} leader state - Time since last heartbeat: {time_since_heartbeat:.2f}s, "
                f"Heartbeat timeout: {self.heartbeat_timeout:.2f}s, Term: {self.current_term}, "
                f"Election attempts: {self.election_attempts}, Heartbeats sent: {self.heartbeats_sent}"
            )
            self.last_log_time = time.time()
        
        # Send heartbeats if enough time has passed
        if time_since_heartbeat >= self.heartbeat_timeout:
            await self.send_heartbeats()
        
        # Small sleep to prevent CPU spinning, but not so long it affects heartbeat timing
        await asyncio.sleep(0.1)  # Reduced from 1.0s to 0.1s

    async def send_heartbeats(self):
        """Send heartbeats to all followers"""
        start_time = time.time()
        success_count = 0
        
        for peer_id in self.peer_ids:
            try:
                request = raft_pb2.AppendEntriesRequest(
                    term=self.current_term,
                    leader_id=self.node_id,
                    prev_log_index=self.next_index[peer_id] - 1,
                    prev_log_term=self.log[self.next_index[peer_id] - 1].term if self.next_index[peer_id] > 0 else 0,
                    entries=[],
                    leader_commit=self.commit_index
                )
                logger.info(f"Node {self.node_id} sends RPC AppendEntries to Node {peer_id}")
                response = await self.stubs[peer_id].AppendEntries(request)
                if response.success:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error sending heartbeat to node {peer_id}: {e}")
        
        elapsed = time.time() - start_time
        self.heartbeats_sent += 1
        self.last_heartbeat_as_leader = time.time()
        
        logger.info(f"Node {self.node_id}: Heartbeat round took {elapsed:.3f}s, {success_count}/{len(self.peer_ids)} successful responses")

    async def run(self):
        while True:
            if self.state == State.FOLLOWER:
                await self.run_follower()
            elif self.state == State.CANDIDATE:
                await self.run_candidate()
            elif self.state == State.LEADER:
                await self.run_leader()
            await asyncio.sleep(0.2)  # Doubled from 0.1

    async def Add(self, request, context):
        # If not leader, forward to leader
        if self.state != State.LEADER:
            if self.leader_id is not None:
                try:
                    stub = self.stubs[self.leader_id]
                    response = await stub.Add(request)
                    return response
                except Exception as e:
                    return raft_pb2.AddResponse(
                        success=False,
                        error=f"Failed to forward to leader: {str(e)}"
                    )
            else:
                return raft_pb2.AddResponse(
                    success=False,
                    error="No leader available"
                )
        
        try:
            # Perform addition
            sum_result = request.num1 + request.num2
            
            # Create log entry for the operation
            entry = raft_pb2.LogEntry(
                term=self.current_term,
                command=f"ADD {request.num1} {request.num2}",
                index=len(self.log)
            )
            
            # Append to log
            self.log.append(entry)
            
            # Return result
            return raft_pb2.AddResponse(
                sum=sum_result,
                success=True,
                error=""
            )
            
        except Exception as e:
            return raft_pb2.AddResponse(
                success=False,
                error=f"Error performing addition: {str(e)}"
            )

    async def send_heartbeat(self):
        """Send heartbeat to all followers"""
        start_time = time.time()
        for peer_id in self.peer_ids:
            try:
                request = raft_pb2.AppendEntriesRequest(
                    term=self.current_term,
                    leader_id=self.node_id,
                    prev_log_index=self.next_index[peer_id] - 1,
                    prev_log_term=self.log[self.next_index[peer_id] - 1].term if self.next_index[peer_id] > 0 else 0,
                    entries=[],
                    leader_commit=self.commit_index
                )
                logger.info(f"Node {self.node_id} sends RPC AppendEntries to Node {peer_id}")
                await self.stubs[peer_id].AppendEntries(request)
            except Exception as e:
                logger.error(f"Failed to send heartbeat to {peer_id}: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"Node {self.node_id}: Heartbeat round took {elapsed:.3f}s")
        await asyncio.sleep(self.heartbeat_timeout)  # Heartbeat interval

    async def handle_append_entries(self, leader_id: int, term: int, entries: List[Any]) -> bool:
        """Handle append entries request from leader"""
        if term < self.current_term:
            return False
        
        prev_heartbeat = self.last_heartbeat
        self.last_heartbeat = time.time()
        time_since_last = self.last_heartbeat - prev_heartbeat
        
        logger.info(f"Node {self.node_id}: Received heartbeat from {leader_id} after {time_since_last:.3f}s")
        
        # ... existing code ...

    async def JoinCluster(self, request: raft_pb2.JoinRequest, context) -> raft_pb2.JoinResponse:
        """Handle request from a new node to join the cluster"""
        logger.info(f"Node {self.node_id} received join request from Node {request.node_id}")
        
        if self.state != State.LEADER:
            return raft_pb2.JoinResponse(
                success=False,
                error="Not the leader",
                current_leader=self.leader_id if self.state == State.FOLLOWER else None
            )
        
        new_node_id = request.node_id
        
        # Check if node is already in cluster or pending
        if new_node_id in self.cluster_config.nodes:
            return raft_pb2.JoinResponse(
                success=False,
                error="Node already in cluster",
                cluster_config=self.cluster_config
            )
        
        if new_node_id in self.pending_joins:
            return raft_pb2.JoinResponse(
                success=False,
                error="Node join already in progress",
                cluster_config=self.cluster_config
            )
            
        try:
            # Add to pending joins
            self.pending_joins.add(new_node_id)
            
            # Create new configuration
            new_config = raft_pb2.ClusterConfig()
            # Copy existing nodes and add new node
            new_config.nodes.extend(self.cluster_config.nodes)
            new_config.nodes.append(new_node_id)
            new_config.version = self.cluster_config.version + 1
            
            # Create configuration change log entry
            config_entry = raft_pb2.LogEntry(
                term=self.current_term,
                command=f"CONFIG_CHANGE ADD_NODE {new_node_id}",
                index=len(self.log),
                config_change=raft_pb2.ConfigChange(
                    old_config=self.cluster_config,
                    new_config=new_config,
                    node_id=new_node_id
                )
            )
            
            # Append to log and replicate to existing nodes
            self.log.append(config_entry)
            success = await self.replicate_to_majority([config_entry])
            
            if success:
                # Update cluster configuration
                self.cluster_config = new_config
                
                # Initialize leader state for new node
                self.next_index[new_node_id] = len(self.log)
                self.match_index[new_node_id] = 0
                
                # Setup gRPC connection to new node
                channel = grpc.aio.insecure_channel(f'node{new_node_id}:50051')
                self.channels[new_node_id] = channel
                self.stubs[new_node_id] = raft_pb2_grpc.RaftServiceStub(channel)
                
                # Add to peer list
                self.peer_ids.append(new_node_id)
                
                logger.info(f"Successfully added Node {new_node_id} to cluster")
                return raft_pb2.JoinResponse(
                    success=True,
                    cluster_config=new_config,
                    current_term=self.current_term,
                    log_index=len(self.log) - 1
                )
            else:
                logger.error(f"Failed to replicate configuration change for Node {new_node_id}")
                return raft_pb2.JoinResponse(
                    success=False,
                    error="Failed to replicate configuration change"
                )
                
        except Exception as e:
            logger.error(f"Error processing join request from Node {new_node_id}: {e}")
            return raft_pb2.JoinResponse(
                success=False,
                error=f"Internal error: {str(e)}"
            )
        finally:
            # Remove from pending joins
            self.pending_joins.discard(new_node_id)

    async def replicate_to_majority(self, entries: List[raft_pb2.LogEntry]) -> bool:
        """Replicate entries to majority of nodes"""
        success_count = 1  # Count self
        majority = (len(self.cluster_config.nodes) // 2) + 1
        
        for peer_id in self.peer_ids:
            try:
                request = raft_pb2.AppendEntriesRequest(
                    term=self.current_term,
                    leader_id=self.node_id,
                    prev_log_index=self.next_index[peer_id] - 1,
                    prev_log_term=self.log[self.next_index[peer_id] - 1].term if self.next_index[peer_id] > 0 else 0,
                    entries=entries,
                    leader_commit=self.commit_index
                )
                
                response = await self.stubs[peer_id].AppendEntries(request)
                if response.success:
                    success_count += 1
                    self.next_index[peer_id] = len(self.log)
                    self.match_index[peer_id] = len(self.log) - 1
                    
                    if success_count >= majority:
                        return True
                        
            except Exception as e:
                logger.error(f"Error replicating to node {peer_id}: {e}")
                
        return success_count >= majority

async def serve():
    node_id = int(os.environ['NODE_ID'])
    peer_ids = [int(pid) for pid in os.environ['PEER_IDS'].split(',')]
    
    node = RaftNode(node_id, peer_ids)
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    raft_pb2_grpc.add_RaftServiceServicer_to_server(node, server)
    
    server.add_insecure_port('[::]:50051')
    await server.start()
    logger.info(f"Node {node_id} started on port 50051")
    
    # Start the node's main loop
    await node.run()
    
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve()) 