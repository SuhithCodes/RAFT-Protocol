# RAFT Protocol Implementation

This is a simplified implementation of the RAFT consensus protocol in Python. RAFT is a protocol that helps multiple computers (nodes) agree on a single value or state, even if some of them fail or have network issues.

## What is RAFT?

Imagine you have a group of friends trying to decide where to eat. RAFT is like a democratic system where:

1. One person becomes the "leader" (elected by the group)
2. The leader makes decisions and shares them with others
3. If the leader disappears, a new leader is elected
4. Everyone keeps track of what decisions have been made

## How It Works

### States

Each node can be in one of three states:

- **Follower**: Waits for instructions from the leader
- **Candidate**: Trying to become the leader
- **Leader**: Makes decisions and tells others what to do

### Election Process

1. If a follower doesn't hear from the leader for 20-30 seconds (random time), it becomes a candidate
2. The candidate asks others to vote for it
3. If it gets votes from most nodes, it becomes the leader
4. If not, it goes back to being a follower

### Heartbeats

- The leader sends "heartbeats" every 6 seconds
- If followers don't get heartbeats, they start a new election

### Log Replication

- When a client wants to perform an operation (e.g., addition), it tells any node
- If the node is not the leader, it redirects to the current leader
- The leader adds the operation to its log and tells followers
- Once most followers have it, the operation is "committed" and executed

## Implementation Details

### Timeouts

- **Election Timeout**: 20-30 seconds (random for each node)
- **Heartbeat Timeout**: 6.0 seconds

### RPC Methods

1. **RequestVote**: Used during elections

   - Candidates ask for votes
   - Followers decide whether to vote

2. **AppendEntries**: Used for:

   - Heartbeats (empty messages)
   - Log replication (with actual data)

3. **JoinCluster**: Used for dynamic membership

   - New nodes can join an existing cluster
   - Leader updates cluster configuration

4. **Add**: Handles addition operations
   - If received by leader: processes the addition
   - If received by follower: redirects to leader with hint

### Client Implementation

The client (`client.py`) provides:

- Connection to multiple nodes
- Automatic leader discovery
- Operation retry logic
- Detailed operation status:
  - Leader identification
  - Operation node tracking
  - Result reporting

Example client usage:

```bash
python client.py 5 3

Operation Summary:
Leader: Node 1
Operation performed on: Node 1
Result: 5 + 3 = 8
```

### Log Management

- Each node maintains a log of operations
- Log entries contain:
  - Term number
  - Operation details (e.g., Add request)
  - Index (position in log)
  - Configuration changes (for cluster membership)

### State Management

- **Persistent State**:

  - Current term
  - Voted for
  - Log entries
  - Cluster configuration

- **Volatile State**:
  - Commit index
  - Last applied
  - Leader ID
  - Election attempts
  - Heartbeats sent

## Test Cases

The system includes several test cases:

1. **Leader Election**

   - Verifies correct leader selection
   - Checks term consistency
   - Monitors state transitions

2. **New Node Joining**

   - Tests dynamic cluster membership
   - Verifies configuration updates
   - Checks log replication to new nodes

3. **Follower Catch-up**

   - Tests node recovery after downtime
   - Verifies log synchronization
   - Checks entry application order

4. **Client Operations**
   - Tests addition operations
   - Verifies leader forwarding
   - Checks operation consistency

## Logging

The system provides detailed logging:

```
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X started on port 50051
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X election timeout, becoming candidate
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X won election, becoming leader
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X leader state - Time since last heartbeat: Y.YYs
```

## Error Handling

The system handles:

- Network failures
- Node crashes
- Leader changes
- Split votes
- Client retries
- Invalid operations

## Future Improvements

1. Add persistence (save state to disk)
2. Implement snapshotting (compress log)
3. Add more operation types
4. Add cluster resizing
5. Implement log compaction
