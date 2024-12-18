#!/bin/bash

source activate py311
celery -A tasks_conversion worker --autoscale=8,1 -Q conversion --max-tasks-per-child 1 --loglevel INFO --max-memory-per-child 3000000
