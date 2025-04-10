import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class State(Enum):
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"

@dataclass
class LogEntry:
    term: int
    command: Any

@dataclass
class RequestVoteRequest:
    term: int
    candidate_id: int
    last_log_index: int
    last_log_term: int

@dataclass
class RequestVoteResponse:
    term: int
    vote_granted: bool

@dataclass
class AppendEntriesRequest:
    term: int
    leader_id: int
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int

@dataclass
class AppendEntriesResponse:
    term: int
    success: bool

class RaftNode:
    def __init__(self, node_id: int, peer_ids: List[int]):
        self.node_id = node_id
        self.peer_ids = peer_ids
        
        # Persistent state
        self.current_term = 0
        self.voted_for = None
        self.log: List[LogEntry] = []
        
        # Volatile state
        self.commit_index = 0
        self.last_applied = 0
        
        # Leader state
        self.next_index: Dict[int, int] = {}
        self.match_index: Dict[int, int] = {}
        
        # Node state
        self.state = State.FOLLOWER
        self.election_timeout = random.uniform(7.5, 10.0)  # Random timeout between 7.5-10.0 seconds
        self.last_heartbeat = time.time()
        
        # Event loop
        self.loop = asyncio.get_event_loop()
        
        # Start the node
        self.loop.create_task(self.run())

    async def run(self):
        """Main node loop"""
        while True:
            if self.state == State.FOLLOWER:
                await self.run_follower()
            elif self.state == State.CANDIDATE:
                await self.run_candidate()
            elif self.state == State.LEADER:
                await self.run_leader()
            await asyncio.sleep(0.1)

    async def run_follower(self):
        """Follower state logic"""
        if time.time() - self.last_heartbeat > self.election_timeout:
            logger.info(f"Node {self.node_id} election timeout, becoming candidate")
            self.state = State.CANDIDATE
            self.current_term += 1
            self.voted_for = self.node_id

    async def run_candidate(self):
        """Candidate state logic"""
        # Start election
        votes_received = 1  # Vote for self
        self.election_timeout = random.uniform(7.5, 10.0)
        self.last_heartbeat = time.time()
        
        # Request votes from all peers
        for peer_id in self.peer_ids:
            request = RequestVoteRequest(
                term=self.current_term,
                candidate_id=self.node_id,
                last_log_index=len(self.log) - 1,
                last_log_term=self.log[-1].term if self.log else 0
            )
            # In a real implementation, this would be an RPC call
            # For simplicity, we'll simulate responses
            response = await self.request_vote(peer_id, request)
            if response and response.vote_granted:
                votes_received += 1
        
        # Check if we won the election
        if votes_received > len(self.peer_ids) / 2:
            logger.info(f"Node {self.node_id} won election, becoming leader")
            self.state = State.LEADER
            # Initialize leader state
            for peer_id in self.peer_ids:
                self.next_index[peer_id] = len(self.log)
                self.match_index[peer_id] = 0

    async def run_leader(self):
        """Leader state logic"""
        start_time = time.time()
        # Send heartbeats to all followers
        for peer_id in self.peer_ids:
            request = AppendEntriesRequest(
                term=self.current_term,
                leader_id=self.node_id,
                prev_log_index=self.next_index[peer_id] - 1,
                prev_log_term=self.log[self.next_index[peer_id] - 1].term if self.next_index[peer_id] > 0 else 0,
                entries=[],
                leader_commit=self.commit_index
            )
            # In a real implementation, this would be an RPC call
            await self.append_entries(peer_id, request)
        
        # Reset heartbeat timer
        elapsed = time.time() - start_time
        logger.info(f"Node {self.node_id}: Heartbeat round took {elapsed:.3f}s")
        self.last_heartbeat = time.time()
        await asyncio.sleep(0.1)  # Heartbeat interval

    async def request_vote(self, peer_id: int, request: RequestVoteRequest) -> Optional[RequestVoteResponse]:
        """Handle vote request from candidate"""
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        if request.term < self.current_term:
            return RequestVoteResponse(term=self.current_term, vote_granted=False)
        
        if (self.voted_for is None or self.voted_for == request.candidate_id) and \
           (not self.log or request.last_log_term >= self.log[-1].term):
            self.voted_for = request.candidate_id
            return RequestVoteResponse(term=self.current_term, vote_granted=True)
        
        return RequestVoteResponse(term=self.current_term, vote_granted=False)

    async def append_entries(self, peer_id: int, request: AppendEntriesRequest) -> Optional[AppendEntriesResponse]:
        """Handle append entries request from leader"""
        start_time = time.time()
        # Simulate network delay
        delay = random.uniform(0.1, 0.3)
        await asyncio.sleep(delay)
        
        if request.term < self.current_term:
            return AppendEntriesResponse(term=self.current_term, success=False)
        
        prev_heartbeat = self.last_heartbeat
        self.last_heartbeat = time.time()
        time_since_last = self.last_heartbeat - prev_heartbeat
        
        logger.info(f"Node {self.node_id}: Received heartbeat from {request.leader_id} after {time_since_last:.3f}s (network delay: {delay:.3f}s)")
        
        if request.term > self.current_term:
            self.current_term = request.term
            self.state = State.FOLLOWER
            self.voted_for = None
        
        # Check if log is consistent
        if request.prev_log_index >= len(self.log) or \
           (request.prev_log_index >= 0 and self.log[request.prev_log_index].term != request.prev_log_term):
            return AppendEntriesResponse(term=self.current_term, success=False)
        
        # Append new entries
        if request.entries:
            self.log = self.log[:request.prev_log_index + 1] + request.entries
        
        # Update commit index
        if request.leader_commit > self.commit_index:
            self.commit_index = min(request.leader_commit, len(self.log) - 1)
        
        return AppendEntriesResponse(term=self.current_term, success=True)

    def submit_command(self, command: Any) -> bool:
        """Submit a new command to the cluster"""
        if self.state != State.LEADER:
            return False
        
        # Add command to log
        self.log.append(LogEntry(term=self.current_term, command=command))
        return True 