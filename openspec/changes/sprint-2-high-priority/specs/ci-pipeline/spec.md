# Delta for CI Pipeline

## ADDED Requirements

### Requirement: Lock File Install

CI MUST install dependencies from `requirements.lock` (not `requirements.txt`) to match the Docker build.

#### Scenario: Install from lock succeeds

- GIVEN `requirements.lock` exists in the repository
- WHEN the test job runs `pip install -r requirements.lock`
- THEN pip installs pinned versions from the lock file
- AND all transitive dependencies match the locked versions

## MODIFIED Requirements

### Requirement: Pip Dependency Caching

CI SHOULD cache pip dependencies to speed up runs.
(Previously: cache key referenced `requirements.txt`)

The `setup-python@v5` action with `cache: pip` auto-detects `requirements.txt`, `pyproject.toml`, `setup.py` — but NOT `requirements.lock`. The action MUST specify `cache-dependency-path: requirements.lock` to ensure the cache key derives from the lock file.

#### Scenario: Cache hit skips download

- GIVEN a cached pip directory matching `requirements.lock` checksum
- WHEN `pip install -r requirements.lock` runs
- THEN cached packages are used instead of downloading
- AND the install step completes faster than a cold cache

#### Scenario: Cache derives from lock file

- GIVEN `setup-python@v5` with `cache: pip` and `cache-dependency-path: requirements.lock`
- WHEN the cache key is computed
- THEN it SHALL hash `requirements.lock` (not `requirements.txt`)
- AND cache invalidates when the lock file changes

### Requirement: Docker Build Verification

CI SHALL build the Docker image to validate the Dockerfile and requirements.
(Previously: referenced `requirements.txt` in Dockerfile step)

#### Scenario: Build succeeds

- GIVEN the Dockerfile and `requirements.lock`
- WHEN `docker build` executes
- THEN it copies `requirements.lock` into the image
- AND produces an image without errors
