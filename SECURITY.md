# Security Policy

## Supported Versions

The following versions of txjsonrpc-ng are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.7.x   | :white_check_mark: |
| < 0.7.0 | :x:                |

## Reporting a Vulnerability

We take the security of txjsonrpc-ng seriously. If you discover a security vulnerability, please follow these steps:

### 1. Do Not Disclose Publicly

Please **do not** open a public GitHub issue for security vulnerabilities. Public disclosure before a fix is available could put users at risk.

### 2. Report Privately

Report security vulnerabilities by emailing the maintainers:

- **Email**: andi@tryb.de
- **Subject**: `[SECURITY] Brief description of the issue`

Include in your report:

- **Description**: Clear description of the vulnerability
- **Impact**: Potential security impact and affected components
- **Steps to Reproduce**: Detailed steps to reproduce the vulnerability
- **Proof of Concept**: Code or demonstration if available (optional)
- **Suggested Fix**: If you have ideas on how to fix it (optional)
- **Environment**: 
  - txjsonrpc-ng version
  - Python version
  - Twisted version
  - Operating system

### 3. Response Timeline

You can expect:

- **Initial Response**: Within 48 hours acknowledging receipt
- **Assessment**: Within 7 days with initial assessment
- **Updates**: Regular updates on progress toward a fix
- **Resolution**: Security patch released as soon as possible

### 4. Disclosure Process

Once a fix is available:

1. A security patch will be released
2. A security advisory will be published
3. Credit will be given to the reporter (unless anonymity is requested)
4. CVE will be requested if appropriate

## Security Best Practices

When using txjsonrpc-ng:

### Authentication

- Always use authentication for production JSON-RPC endpoints
- Use strong credentials and consider rate limiting
- Example authentication is available in `examples/webAuth/`

### Network Security

- Use HTTPS/TLS for HTTP-based JSON-RPC (see `examples/ssl/`)
- Use TLS for TCP-based JSON-RPC when transmitting sensitive data
- Restrict network access to JSON-RPC endpoints
- Use firewalls and network segmentation

### Input Validation

- Validate all input parameters in your RPC methods
- Set reasonable limits on request size and complexity
- Implement timeouts for long-running operations
- Be careful with methods that perform file system or network operations

### Error Handling

- Don't expose sensitive information in error messages
- Log security-relevant events
- Monitor for suspicious activity patterns

### Example: Secure Handler Implementation

```python
from txjsonrpc_ng.web.jsonrpc import Handler
from twisted.python import log

class SecureHandler(Handler):
    def jsonrpc_sensitiveOperation(self, user_input):
        """Example of input validation"""
        # Validate input
        if not isinstance(user_input, str):
            raise ValueError("Invalid input type")
        
        if len(user_input) > 1000:
            raise ValueError("Input too large")
        
        # Sanitize input
        sanitized = user_input.strip()
        
        # Log the operation
        log.msg(f"Sensitive operation called with input length: {len(sanitized)}")
        
        # Process safely
        return self._process_safely(sanitized)
```

### Dependency Security

- Keep txjsonrpc-ng updated to the latest version
- Regularly update Twisted and other dependencies
- Monitor security advisories for dependencies
- Use tools like `safety` or Dependabot to check for vulnerabilities

### Deployment Considerations

- Run with minimal privileges (avoid root)
- Use process isolation (containers, VMs)
- Enable security features of your hosting environment
- Implement request rate limiting
- Set up monitoring and alerting

## Known Security Considerations

### JSON-RPC Protocol

- JSON-RPC does not include built-in authentication
- Version 1.0 does not support batch requests (DoS consideration)
- Large batch requests in version 2.0 could cause resource exhaustion

### Twisted Framework

- Keep Twisted updated for security patches
- Be aware of async execution model when handling concurrent requests
- Properly handle Deferred errors to avoid information leakage

## Security Updates

Security updates will be:

- Released as patch versions (e.g., 0.7.4 → 0.7.5)
- Announced in release notes with `[SECURITY]` prefix
- Documented in GitHub Security Advisories
- Published to PyPI immediately

## Contact

For security concerns, contact:

- **Primary**: andi@tryb.de
- **GitHub**: [@wuan](https://github.com/wuan)

For general questions (non-security), please use [GitHub Issues](https://github.com/wuan/txjsonrpc/issues).

## Acknowledgments

We appreciate responsible disclosure of security vulnerabilities and will acknowledge security researchers who report issues responsibly.

---

**Last Updated**: 2025-10-30
