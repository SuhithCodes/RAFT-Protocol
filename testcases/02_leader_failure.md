# Test Case 2: Leader Failure and Recovery

## Description

This test case verifies that the cluster can handle leader failure and elect a new leader while maintaining consistency.

## Test Steps

1. Start a cluster with 5 nodes (Node1-Node5)
2. Wait for leader election and cluster stabilization
3. Note the current leader (e.g., Node2)
4. Simulate leader failure by stopping Node2
5. Observe the election process
6. Verify cluster operations continue with new leader

## Expected Behavior

1. After leader failure:
   - Followers should detect missing heartbeats
   - New election should be triggered
   - New leader should be elected
   - Cluster should continue operating normally

## Verification Points

- Check election timeout behavior
- Verify new leader election
- Confirm log consistency across nodes
- Test client operations during transition

## Log Messages to Monitor

```
[timestamp] Node X detects missing heartbeat from leader
[timestamp] Node X becomes CANDIDATE
[timestamp] Node X wins election and becomes LEADER
[timestamp] New leader starts sending heartbeats
```

## Success Criteria

- New leader is elected within expected time
- No data loss during transition
- Client operations continue to work
- Cluster maintains consistency
