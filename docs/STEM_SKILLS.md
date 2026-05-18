# STEM Skills Documentation

This document describes the STEM (Science, Technology, Engineering, Mathematics) skills available in the Universal Agent Runtime (UAR).

## Overview

UAR includes three new STEM-focused skills for scientific computing, cryptography, and physics/astronomy calculations. These skills follow the same architecture pattern as existing UAR skills with graceful degradation for optional dependencies.

## Math Compute Skill (`math_compute`)

### Description
Performs symbolic mathematics, algebraic manipulation, calculus, and numerical evaluation using SymPy.

### Dependencies
- **Required**: None
- **Optional**: `sympy` (install with `pip install sympy`)

### Operations
- `solve` - Solve equations for a variable
- `simplify` - Simplify mathematical expressions
- `differentiate` - Differentiate expressions with respect to a variable
- `integrate` - Integrate expressions with respect to a variable
- `evaluate` - Evaluate mathematical expressions numerically

### Environment Variables
- `MATH_TIMEOUT_SECONDS` - Timeout for computations (default: 30)
- `MATH_MAX_EXPRESSION_SIZE` - Maximum expression complexity in characters (default: 10000)

### Goal Metadata
- `math_operation` - Operation type: 'solve', 'simplify', 'differentiate', 'integrate', 'evaluate'
- `math_expression` - Mathematical expression (string, e.g., "x**2 + 2*x + 1")
- `math_variable` - Variable for operations (default: 'x')
- `math_domain` - Optional domain specification (default: 'real')

### Examples

#### Solve an equation
```json
{
  "goal": "Solve x^2 + 2x + 1 = 0 for x",
  "skills": ["math_compute"],
  "metadata": {
    "math_operation": "solve",
    "math_expression": "x**2 + 2*x + 1 = 0",
    "math_variable": "x"
  }
}
```

#### Differentiate an expression
```json
{
  "goal": "Differentiate x^3 + 2x",
  "skills": ["math_compute"],
  "metadata": {
    "math_operation": "differentiate",
    "math_expression": "x**3 + 2*x",
    "math_variable": "x"
  }
}
```

#### Simplify an expression
```json
{
  "goal": "Simplify (x^2 - 1) / (x - 1)",
  "skills": ["math_compute"],
  "metadata": {
    "math_operation": "simplify",
    "math_expression": "(x**2 - 1) / (x - 1)"
  }
}
```

## Cipher Operations Skill (`cipher_ops`)

### Description
Performs cryptographic operations including encryption, decryption, hashing, and digital signatures using PyCryptodome.

### Dependencies
- **Required**: None
- **Optional**: `pycryptodome` (install with `pip install pycryptodome`)

### Operations
- `encrypt` - Encrypt data using AES-CBC
- `decrypt` - Decrypt data using AES-CBC
- `hash` - Hash data using SHA256 or SHA512
- `sign` - Sign data using Ed25519
- `verify` - verify signatures using Ed25519

### Environment Variables
- `CIPHER_TIMEOUT_SECONDS` - Timeout for operations (default: 30)
- `CIPHER_MAX_DATA_SIZE` - Maximum data size in bytes (default: 10485760, 10MB)

### Goal Metadata
- `cipher_operation` - Operation: 'encrypt', 'decrypt', 'hash', 'sign', 'verify'
- `cipher_algorithm` - Algorithm: 'AES', 'SHA256', 'SHA512', 'Ed25519'
- `cipher_data` - Data to process (base64 encoded string)
- `cipher_key` - Key for operations (base64 encoded)
- `cipher_iv` - IV for block ciphers (optional, base64 encoded)

### Examples

#### Hash data
```json
{
  "goal": "Hash sensitive data",
  "skills": ["cipher_ops"],
  "metadata": {
    "cipher_operation": "hash",
    "cipher_algorithm": "SHA256",
    "cipher_data": "SGVsbG8gV29ybGQ="
  }
}
```

#### Encrypt data
```json
{
  "goal": "Encrypt confidential data",
  "skills": ["cipher_ops"],
  "metadata": {
    "cipher_operation": "encrypt",
    "cipher_algorithm": "AES",
    "cipher_data": "SGVsbG8gV29ybGQ=",
    "cipher_key": "YWJjZGVmZ2hpams="  // 16-byte key base64 encoded
  }
}
```

## Physics Compute Skill (`physics_compute`)

### Description
Performs physics and astronomy computations including unit conversions, coordinate transformations, distance calculations, energy calculations, and cosmological computations using Astropy.

### Dependencies
- **Required**: None
- **Optional**: `astropy` (install with `pip install astropy`)

### Operations
- `convert` - Convert between units
- `transform` - Transform coordinates between frames
- `calculate` - Calculate physical quantities (energy, redshift, distance)
- `query` - Query physics information

### Environment Variables
- `PHYSICS_TIMEOUT_SECONDS` - Timeout for computations (default: 30)
- `PHYSICS_MAX_DATA_SIZE` - Maximum data size in bytes (default: 10485760, 10MB)

### Goal Metadata
- `physics_operation` - Operation: 'convert', 'transform', 'calculate', 'query'
- `physics_type` - Type: 'unit', 'coordinate', 'time', 'distance', 'energy'
- `physics_value` - Value to process (string or number)
- `physics_from_unit` - Source unit (for conversions)
- `physics_to_unit` - Target unit (for conversions)
- `physics_coordinate` - Coordinate data (for transformations)

### Examples

#### Unit conversion
```json
{
  "goal": "Convert 1 light-year to parsecs",
  "skills": ["physics_compute"],
  "metadata": {
    "physics_operation": "convert",
    "physics_value": "1",
    "physics_from_unit": "lyr",
    "physics_to_unit": "pc"
  }
}
```

#### Calculate photon energy
```json
{
  "goal": "Calculate photon energy for 500nm wavelength",
  "skills": ["physics_compute"],
  "metadata": {
    "physics_operation": "calculate",
    "physics_type": "energy",
    "physics_value": "500 nm"
  }
}
```

#### Calculate cosmological distance
```json
{
  "goal": "Calculate luminosity distance for redshift 0.5",
  "skills": ["physics_compute"],
  "metadata": {
    "physics_operation": "calculate",
    "physics_type": "redshift",
    "physics_value": "0.5"
  }
}
```

## Architecture Features

All STEM skills share common architectural features for maximum usability and management:

### 1. Graceful Degradation
- Skills check for library availability at runtime
- Return clear error messages if optional dependencies are missing
- Never crash due to missing optional dependencies

### 2. Circuit Breaker Pattern
- Each skill uses a circuit breaker to prevent cascading failures
- Configurable failure threshold and recovery timeout
- Automatic recovery after cooldown period

### 3. Input Validation
- Size limits on input data to prevent resource exhaustion
- Type checking and validation of parameters
- Clear error messages for invalid inputs

### 4. Environment Configuration
- Configurable timeouts via environment variables
- Configurable data size limits
- No hardcoded configuration values

### 5. Consistent Response Format
- Standardized response structure across all skills
- Success/failure status indicators
- Detailed error messages when operations fail
- Operation metadata in responses

### 6. Security Considerations
- Base64 encoding for binary data
- No raw key storage in logs
- Timeout protection against long-running computations
- Data size limits to prevent DoS attacks

## Installation

Install optional dependencies as needed:

```bash
# For math computations
pip install sympy

# For cryptographic operations
pip install pycryptodome

# For physics and astronomy
pip install astropy
```

Or install all STEM dependencies:

```bash
pip install sympy pycryptodome astropy
```

## Integration with Existing UAR

The STEM skills integrate seamlessly with the existing UAR architecture:

- **Pipeline Context**: Skills can access prior skill outputs via `ctx.data`
- **Goal Metadata**: Skills use standardized goal metadata for configuration
- **Skill Registry**: Skills are automatically registered with `@register_skill` decorator
- **Error Handling**: Skills follow UAR's error handling patterns
- **Event Streaming**: Skills emit events for real-time monitoring

## Testing

Test each skill independently:

```python
# Test math_compute
curl -X POST http://127.0.0.1:8000/api/uar/run \
  -H 'Content-Type: application/json' \
  -d '{
    "goal": "Solve x^2 + 2x + 1 = 0",
    "skills": ["math_compute"],
    "metadata": {
      "math_operation": "solve",
      "math_expression": "x**2 + 2*x + 1 = 0",
      "math_variable": "x"
    }
  }'

# Test cipher_ops
curl -X POST http://127.0.0.1:8000/api/uar/run \
  -H 'Content-Type: application/json' \
  -d '{
    "goal": "Hash data",
    "skills": ["cipher_ops"],
    "metadata": {
      "cipher_operation": "hash",
      "cipher_algorithm": "SHA256",
      "cipher_data": "SGVsbG8gV29ybGQ="
    }
  }'

# Test physics_compute
curl -X POST http://127.0.0.1:8000/api/uar/run \
  -H 'Content-Type: application/json' \
  -d '{
    "goal": "Convert 1 light-year to parsecs",
    "skills": ["physics_compute"],
    "metadata": {
      "physics_operation": "convert",
      "physics_value": "1",
      "physics_from_unit": "lyr",
      "physics_to_unit": "pc"
    }
  }'
```

## Future Enhancements

Potential future additions to the STEM skills suite:

- **Science**: Molecular dynamics simulation, quantum chemistry calculations
- **Math**: Linear algebra operations, statistical analysis, optimization
- **Cipher**: Additional algorithms (RSA, ECC), key management
- **Physics**: Particle physics calculations, fluid dynamics simulations

## Troubleshooting

### SymPy not installed
```
Error: SymPy not installed. Install with: pip install sympy
```
Solution: Install SymPy with `pip install sympy`

### PyCryptodome not installed
```
Error: PyCryptodome not installed. Install with: pip install pycryptodome
```
Solution: Install PyCryptodome with `pip install pycryptodome`

### Astropy not installed
```
Error: Astropy not installed. Install with: pip install astropy
```
Solution: Install Astropy with `pip install astropy`

### Computation timeout
```
Error: Computation timed out
```
Solution: Increase `MATH_TIMEOUT_SECONDS`, `CIPHER_TIMEOUT_SECONDS`, or `PHYSICS_TIMEOUT_SECONDS` environment variable

### Data too large
```
Error: Data too large (max X bytes)
```
Solution: Increase the respective `*_MAX_DATA_SIZE` environment variable or reduce input size
