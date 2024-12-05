#!/bin/bash

arch=$1

ps aux | grep -v grep | grep -q retracer-${arch}
if [ $? = 0 ]; then
  echo check=retracer,archictecture=${arch} up=1
else
  echo check=retracer,archictecture=${arch} up=0
fi
