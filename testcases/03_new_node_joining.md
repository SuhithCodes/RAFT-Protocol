# Test Case 3: New Node Joining the System

## Description

This test case verifies that a new node can successfully join an existing RAFT cluster and participate in the consensus protocol.

## Test Steps

1. Start a cluster with 3 nodes (Node1, Node2, Node3)
2. Wait for leader election and cluster stabilization
3. Start a new node (Node4)
4. Configure Node4 with the addresses of existing nodes
5. Start Node4 and observe its behavior

## Expected Behavior

1. Node4 should:
   - Start in FOLLOWER state
   - Receive heartbeats from the leader
   - Update its term to match the cluster
   - Eventually receive the complete log from the leader

## Verification Points

- Check Node4's state transitions
- Verify Node4 receives heartbeats
- Confirm Node4's term matches the cluster
- Verify Node4's log matches the leader's log

## Log Messages to Monitor

```
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 4 started on port 50051
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 4 sending join request to nodeX:50051
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X received join request from Node 4
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Redirecting to leader at nodeY:50051
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 4 successfully joined cluster
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Cluster config: nodes: [1, 2, 3, 4], version: Z
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 4 runs RPC AppendEntries called by Node Y
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 4 follower state - Time since last heartbeat: X.XXs, Time since last election: Y.YYs, Election timeout: Z.ZZs, Term: W, Election attempts: V
```

## Success Criteria

- Node4 successfully joins the cluster
- Node4's state is consistent with the cluster
- No disruption to existing cluster operations
