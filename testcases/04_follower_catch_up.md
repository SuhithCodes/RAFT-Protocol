# Test Case 4: Follower Catch-up After Rejoining

## Description

This test case verifies that a follower node can successfully catch up with missed log entries after being temporarily down and rejoining the cluster.

## Test Steps

1. Start a cluster with 5 nodes (Node1-Node5)
2. Wait for leader election and cluster stabilization
3. Bring down one follower node (e.g., Node5)
4. Send several log entries to the leader:
   - Add multiple configuration changes
   - Send state machine commands
   - Record the number and content of entries added
5. Restart the downed follower
6. Observe catch-up behavior

## Expected Behavior

1. During follower downtime:

   - Cluster continues operating with remaining nodes
   - Leader successfully replicates entries to active followers
   - System maintains quorum and can process new requests

2. After follower restart:
   - Follower detects it has missed entries
   - Leader sends missing entries via AppendEntries
   - Follower successfully applies all missed entries
   - Follower's log matches leader's log

## Verification Points

- Monitor log indices before and after follower downtime
- Track the number of entries replicated during catch-up
- Verify log consistency between leader and rejoined follower
- Check that all entries are applied in order

## Log Messages to Monitor

```
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 5 started on port 50051
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 5 runs RPC AppendEntries called by Node X
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X leader state - Time since last heartbeat: Y.YYs, Heartbeat timeout: 6.00s, Term: Z, Election attempts: W, Heartbeats sent: V
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X sends RPC AppendEntries to Node 5
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node 5 follower state - Time since last heartbeat: Y.YYs, Time since last election: Z.ZZs, Election timeout: W.WWs, Term: V, Election attempts: U
[YYYY-MM-DD HH:mm:ss,SSS] - INFO - Node X: Heartbeat round took Y.YYs, N/M successful responses
```

## Success Criteria

- Follower detects and requests missing entries
- Leader successfully transfers missed entries
- Follower's log matches leader's log after catch-up
- All entries are applied in the correct order
- System maintains consistency throughout the process
