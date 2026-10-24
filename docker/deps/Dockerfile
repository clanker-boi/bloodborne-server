# syntax=docker/dockerfile:1.7
# OCI data image: fully resolved Conan binary packages, no compilation.
# Consumers must match the checked-in Conan lockfile and GCC ABI profile.
FROM scratch
COPY conan-cache/ /conan-cache/
CMD ["/bin/true"]
