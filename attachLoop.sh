#!/bin/bash

while true; do docker attach fz-s3-bulk-download.service; sleep 1; echo "WAITING 5 SECS"; sleep 5; service fz-s3-bulk-download start; sleep 2; done
