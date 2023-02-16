
Basic configuration:

```
[default]

# Affects response headers
ADD_CACHE_HEADERS = true

# Sets the allowed origins for CORS. Should be a list of allowed origins or '*' for any
ALLOWED_ORIGINS = []

# OPTIONS requests bypass all checks other than against ALLOWED_ORIGINS when this is true
SHORTCIRCUIT_OPTIONS = true

# Handle trailing slash redirects outside the regular Flask mechanism
# RELATIVE_REDIRECTS = true

# Default CSP policy that we want in place
CSP_DEFAULT_SRC = [
    'https:',
    'self'
]
CSP_UPGRADE_INSECURE_REQUESTS = true
```
