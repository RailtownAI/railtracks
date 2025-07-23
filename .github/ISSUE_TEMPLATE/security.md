---
name: Security Issue
about: Report security vulnerabilities or concerns (use private reporting for sensitive issues)
title: "[Security] "
labels: ["security", "priority-high"]
assignees: []

---

⚠️ **IMPORTANT**: For sensitive security vulnerabilities, please use GitHub's private vulnerability reporting feature instead of creating a public issue.

## Security Issue Type
**What type of security issue is this?**
- [ ] Potential vulnerability in code
- [ ] Insecure default configuration
- [ ] Dependency vulnerability
- [ ] Data exposure risk
- [ ] Authentication/authorization issue
- [ ] Input validation problem
- [ ] Information disclosure
- [ ] Other: [please specify]

## Issue Description
**Summary**
Provide a brief summary of the security concern.

**Detailed description**
Describe the security issue in detail. What could an attacker potentially do?

**Affected components**
- [ ] LLM integration layer
- [ ] Agent execution system
- [ ] Request routing
- [ ] Configuration management
- [ ] Logging/debugging features
- [ ] Dependencies
- [ ] Documentation/examples
- [ ] Other: [please specify]

## Severity Assessment
**How would you rate the severity?**
- [ ] Low - Minimal security impact
- [ ] Medium - Moderate security impact
- [ ] High - Significant security impact
- [ ] Critical - Severe security impact

**Potential impact**
- [ ] Information disclosure
- [ ] Unauthorized access
- [ ] Data manipulation
- [ ] Service disruption
- [ ] Remote code execution
- [ ] Privilege escalation
- [ ] Other: [please specify]

## Technical Details
**Steps to reproduce (if applicable)**
Provide steps to reproduce the issue, but avoid including actual exploit code in public issues.

**Environment**
- railtracks version: [e.g. 0.1.0]
- Python version: [e.g. 3.10.5]
- Operating system: [e.g. Ubuntu 22.04]
- LLM providers used: [e.g. OpenAI, local models]

**Code example (sanitized)**
If relevant, provide a sanitized code example that demonstrates the issue:
```python
# Sanitized example - do not include actual exploits
```

## Mitigation
**Suggested fixes**
If you have suggestions for how to fix this issue, please include them.

**Temporary workarounds**
Are there any temporary workarounds users can implement?

## Additional Information
**References**
Any relevant CVE numbers, security advisories, or other references.

**Discovery method**
How was this security issue discovered?
- [ ] Code review
- [ ] Security testing
- [ ] Vulnerability scanner
- [ ] User report
- [ ] Dependency audit
- [ ] Other: [please specify]

## Checklist
- [ ] I have verified this is a legitimate security concern
- [ ] I have checked if this issue has been reported before
- [ ] I have not included sensitive exploit details in this public report
- [ ] I understand that security issues are handled with high priority
- [ ] I have considered using private vulnerability reporting for sensitive issues