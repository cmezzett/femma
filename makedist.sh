#!/bin/sh

python femma.py -c

filename=$(basename $(pwd))

cp settings.cfg settings.cfg.old && \
cp settings.cfg.release settings.cfg && \
zip -r $filename.zip * --exclude customRules\* --exclude makedist.sh --exclude settings.cfg.release  --exclude settings.cfg.old && \
mv settings.cfg.old settings.cfg
