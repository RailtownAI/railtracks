---
name: Performance Issue
about: Report performance problems or request performance improvements
title: "[Performance] "
labels: ["performance", "needs-investigation"]
assignees: []

---

## Performance Issue Description
**What performance issue are you experiencing?**
- [ ] Slow execution time
- [ ] High memory usage
- [ ] High CPU usage
- [ ] Network latency issues
- [ ] Scalability problems
- [ ] Resource leaks
- [ ] Other: [please specify]

**Component affected**
- [ ] Agent execution
- [ ] LLM calls/tool usage
- [ ] Request routing
- [ ] Streaming functionality
- [ ] Visualization tools
- [ ] Debugging/logging
- [ ] Other: [please specify]

## Performance Details
**Expected performance**
Describe what performance you expected to see.

**Actual performance**
Describe the actual performance you observed.

**Performance measurements**
If you have specific metrics, please include them:
- Execution time: [e.g. 30 seconds, expected < 5 seconds]
- Memory usage: [e.g. 2GB RAM, expected < 500MB]
- CPU usage: [e.g. 100% for 10 minutes]
- Request throughput: [e.g. 1 req/sec, expected 10 req/sec]

## Reproduction Information
**Code to reproduce the issue**
Provide a minimal code example that demonstrates the performance issue:
```python
# Your code here
```

**System Configuration**
- OS: [e.g. Ubuntu 22.04]
- Python version: [e.g. 3.10.5]
- railtracks version: [e.g. 0.1.0]
- Hardware: [e.g. 8 CPU cores, 16GB RAM]
- LLM provider: [e.g. OpenAI GPT-4, local model]

**Data characteristics**
- Input size: [e.g. 1000 word document, 50 agent calls]
- Batch size: [if applicable]
- Concurrent requests: [if applicable]

## Profiling Information
**Have you done any profiling?**
- [ ] Yes, I have profiling data (please attach)
- [ ] No, but I'm willing to run profilers
- [ ] No, I need help with profiling

**Profiling data**
If you have profiling data, please attach it or paste relevant sections:
```
# Profiling output here
```

## Impact Assessment
**How critical is this performance issue?**
- [ ] Low - Minor inconvenience
- [ ] Medium - Noticeable impact on productivity
- [ ] High - Major impact, affecting usability
- [ ] Critical - System unusable due to performance

**Workarounds**
Have you found any workarounds for this issue?

## Additional Context
**Related issues**
Are there any related performance issues or discussions?

**Environment details**
Any additional environment information that might be relevant.

## Checklist
- [ ] I have searched existing issues for similar performance problems
- [ ] I have provided specific performance measurements
- [ ] I have included a reproducible example
- [ ] I have specified the impact and urgency level