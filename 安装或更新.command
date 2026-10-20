#!/bin/sh
cd -- "$(dirname -- "$0")"
./install.sh --skill-only --agent both
result=$?
printf "\n安装程序已结束，退出码 %s。按回车关闭。\n" "$result"
read reply
exit "$result"
