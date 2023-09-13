#!/bin/bash
#
# Download airspace file of germany from web page and compare it 
# with latest version in repository. If there is an update, then
# add it to the repository and commit/push.
#
# 2023-09-12: tilmann@bubecks.de
#
# MIT licence apply

if [ ! -d source ]; then
	echo "please execute from root directory of repository"
	exit 1
fi

http_prefix="https://www.daec.de"

url=$(wget -O - $http_prefix/fachbereiche/luftraum-flugsicherheit-betrieb/luftraumdaten/ | sed -n 's/.*href="\([^"]*\).*/\1/p' | grep "Luftraum_und_Flugbetrieb")

if [ "$url" != "" ]; then
	temp_file="/tmp/airspace_germany.txt"
	dest_file="source/airspace_germany.txt"
	wget -O "$temp_file" "$http_prefix/$url"
	if [ $? -eq 0 ]; then
        	if ! diff -q "$temp_file" "$dest_file" >/dev/null ; then
			cp "$temp_file" "$dest_file"
			git add "$dest_file"
			git commit -m "Update to new version of airspace file from internet"
			git push
			date | mail -s "new german airspace detected" tilmann@bubecks.de
		fi
	fi
fi

