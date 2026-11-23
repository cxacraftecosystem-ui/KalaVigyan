#!/usr/bin/env bash
while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done
shift
exec "$@"
