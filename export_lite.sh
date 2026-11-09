#!/bin/sh
# Builds the Linux "Lite" package (source code + INSTALLATION.txt only) as export/CoreMonitor_Lite_Linux_<date>.tar.gz
exec sh "$(dirname "$0")/tools/export.sh" Lite
