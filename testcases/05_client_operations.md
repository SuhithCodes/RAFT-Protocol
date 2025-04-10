# Test Case 5: Client Addition Operations

## Description

This test case verifies that client addition operations are properly handled, replicated, and committed across the cluster using the RaftClient implementation.

## Test Steps

1. Start a cluster with 3 nodes (Node1, Node2, Node3, Node4, Node5) on ports 50051-50055
2. Wait for leader election and cluster stabilization
3. Send a series of addition operations using the client:
   - Operation 1: Add(5, 3)
   - Operation 2: Add(10, -2)
   - Operation 3: Add(100, 200)
4. Send operations to different nodes to test leader forwarding
5. Observe log replication and commitment

## Expected Behavior

1. For operations sent to leader:

   - Leader should process the addition request
   - Leader should append operation to log
   - Leader should replicate to followers
   - Leader should return sum after majority commitment

2. For operations sent to followers:
   - Follower should forward request to leader
   - Client should retry with correct leader
   - Operation should complete successfully

## Verification Points

- Check addition results are correct
- Verify operations are logged on all nodes
- Monitor request forwarding to leader
- Test client retry mechanism
- Verify error handling for unavailable nodes

## Log Messages to Monitor

```
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Trying to send addition request to localhost:50051
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Addition successful! Result: 8
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X leader state - Time since last heartbeat: Y.YYs, Heartbeat timeout: 6.00s, Term: Z, Election attempts: W, Heartbeats sent: V
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X appending entry to log: Add(5, 3)
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X sends RPC AppendEntries to Node Y
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node Y runs RPC AppendEntries called by Node X
[YYYY-MM-DD HH:mm:ss,SSS] - WARNING - Request failed: Not the leader
[YYYY-MM-DD HH:mm:ss,SSS] - ERROR - Failed to connect to localhost:50052: Connection refused
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X: Heartbeat round took Y.YYs, N/M successful responses
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X committing entry at index Z: Add(5, 3)
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node Y applying log entry at index Z: Add(5, 3)
```

## Success Criteria

- All addition operations return correct results
- Operations are properly replicated to followers
- Client successfully handles leader changes
- Failed nodes are properly handled with retries
- No operations are lost or duplicated
- Results are consistent across all nodes
