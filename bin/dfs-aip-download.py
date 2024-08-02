#!/usr/bin/python
#
# This script crawls the web pages of DFS (Deutsche Flugsicherung)
# to download AIP VFR (or others), that are published there.
# The format of publication of DFS is very strange and does not allow
# to download a PDF or use it in a simple way.
#
# By executing this script, you will receive a number of files for each page
# in PNG file format (105 DPI). By converting and combining them, you can
# easily create a PDF file for it.
#
# To create a PDF out of the files, use this (or similar):
#   bash% convert *.png aip-vfr.pdf
#
# This script is licensed under GPLv2.
#
# 2024-07-31, tilmann@bubecks.de
#

import argparse
import urllib.request
import urllib.parse
import re
import base64
import os.path
import sys

def download(url):
    page=1
    next_url_pattern = re.compile(r"myNextURL = '(.*)'")
    my_url_pattern = re.compile(r'myURL = "(.*)"')
    image_pattern = re.compile(r'src="data:image/png;base64,(.*)" alt=')

    u = urllib.parse.urlparse(url)

    while True:
        print(f'{page: 4} {url}')
        with urllib.request.urlopen(url) as f:
            html = f.read().decode('utf-8')
            for line in html.splitlines():
                #ic(line)
                match = next_url_pattern.search(line)
                if match:
                    next_url = match.group(1).strip()
                    #ic(next_url)
                match = my_url_pattern.search(line)
                if match:
                    my_url = match.group(1).strip()
                    page_name = os.path.basename(my_url)
                    #ic(my_url)
                match = image_pattern.search(line)
                if match:
                    image_base64 = match.group(1).strip()
                    #ic(image_base64)
                    image = base64.b64decode(image_base64)
                    filename = f'page-{page:04}.png'
                    #filename = f'{page_name}.png'
                    print(f'  => {page_name} => {filename}')
                    with open(filename, "wb") as file:
                        file.write(image)
                    if next_url == "#":
                        return
                    break
        url = f'{u.scheme}://{u.netloc}{os.path.dirname(u.path)}/{next_url}'
        page += 1
        
def main():
    parser = argparse.ArgumentParser(description='Download AIP from DFS')
    parser.add_argument('-u', '--url', required=False, help='URL of the first page', default="https://aip.dfs.de/BasicVFR/2024JUL25/pages/76800F16EA818CA8BB219C015086FFBD.html")
    args = parser.parse_args()
    #ic(args.anzahl)

    download(args.url)
    
if __name__ == '__main__':
    main()
