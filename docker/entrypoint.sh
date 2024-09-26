#!/bin/bash

# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

set -eu

TEST=${TEST:=true}
MIN_COVERAGE=83

if [ "${TEST,,}" = true ]; then
  coverage run -m pytest --junit-xml=/coverage-results/junit.xml
  coverage combine
  coverage report --skip-empty --show-missing --fail-under="${MIN_COVERAGE}"
  coverage xml -o /coverage-results/coverage.xml
fi

exec "$@"
