# Test Case 1: Leader Election

## Description

This test case verifies that the cluster correctly elects a single leader during initial startup and all nodes maintain consistent state.

## Test Steps

1. Start a cluster with 5 nodes (Node1-Node5)
2. Wait for leader election process to complete
3. Observe state transitions of all nodes
4. Verify cluster stabilization

## Expected Behavior

1. Initial cluster startup:

   - All nodes start in FOLLOWER state
   - Nodes timeout randomly and become CANDIDATES
   - One node receives majority votes and becomes LEADER
   - Other nodes recognize the leader and remain FOLLOWERS

2. After leader election:
   - Single leader sends heartbeats to all followers
   - Followers maintain consistent term numbers
   - No unnecessary term increments or elections occur

## Verification Points

- Only one node becomes leader
- All other nodes are followers
- Term numbers are consistent across nodes
- Heartbeats are being sent and received
- No split votes or election conflicts

## Log Messages to Monitor

```
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X started on port 50051
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X election timeout, becoming candidate
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X sends RPC RequestVote to Node Y
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node Y runs RPC RequestVote called by Node X
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X won election, becoming leader
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X sends RPC AppendEntries to Node Y
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node Y runs RPC AppendEntries called by Node X
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X leader state - Time since last heartbeat: Y.YYs, Heartbeat timeout: 6.00s, Term: Z, Election attempts: W, Heartbeats sent: V
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node Y follower state - Time since last heartbeat: X.XXs, Time since last election: Y.YYs, Election timeout: Z.ZZs, Term: W, Election attempts: V
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X: Heartbeat round took Y.YYs, N/M successful responses
```

## Success Criteria

- Exactly one node is elected as leader
- All other nodes are in follower state
- Term numbers are identical across all nodes
- Leader successfully sends heartbeats to all followers
- Cluster remains stable with no unnecessary elections
