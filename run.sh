#!/bin/sh

docker run -p 127.0.0.1:80:8091 --env-file=/home/fz-gallery/bulk-download/.env -v /home/fz-gallery/bulk-download/data:/code/data fz-s3-bulk-download
