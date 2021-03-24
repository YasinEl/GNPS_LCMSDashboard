#!/bin/bash

celery -A tasks worker -l info -c 8 -Q conversion --max-tasks-per-child 1 --loglevel INFO --max-memory-per-child 3000000
