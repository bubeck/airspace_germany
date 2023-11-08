#!/usr/bin/python # -*- mode: python; python-indent-offset: 4 -*-

import aerofiles.openair
from pprint import pprint
import math
import io
import argparse
import sys
from datetime import datetime
import os
import common
from shapely.geometry import Polygon
import re

def findLatLon(p):
    global records
    
    elements = []
    for record in records:
        for element in record["elements"]:
            if element["type"] == "circle":
                if element["center"] == p:
                    elements.append(element)
            if element["type"] == "point":
                if element["location"] == p:
                    elements.append(element)
            if element["type"] == "arc":
                if element["start"] == p:
                    elements.append(element)
                if element["end"] == p:
                    elements.append(element)
    return elements

def findNearCircles(record_base, element_base):
    global records
    global args
    for record in records:
        for element in record["elements"]:
            if element["type"] == "circle":
                if element != element_base:
                    (distance_m, bearing) = common.geo_distance(element_base["center"][0], element_base["center"][1],
                                                         element["center"][0], element["center"][1])
                    distance_m = int(distance_m / 100)         # convert cm to m
                    if distance_m > 0 and distance_m < args.distance:
                        findingForTwoPoints(f'Airspaces with near circles ({distance_m}m)', record_base, record, element_base["center"], element["center"])

def checkCircles(records):

    """
    Walk through all center points and check, if there are close center points, that are not identical.
    """
    
    for record in records:
        #pprint(record)
        #print("Checking", record["name"])
        for element in record["elements"]:
            if element["type"] == "circle":
                #pprint(element)
                findNearCircles(record, element)

def getAirspaceName(record):
    n1 = f'{record["name"]}:{record["class"]}'
    if "floor" in record and "ceiling" in record:
        h1 = f'({record["floor"]}-{record["ceiling"]})'
    else:
        h1 = ""
    return (n1, h1)

def getAirspaceName2(record):
    (n,h) = getAirspaceName(record)
    return f'{n} {h}'

def findingForTwoPoints(message, record1, record2, p1, p2):
    global records
    global findings

    for f in findings:
        if f["message"] == message:
            if (f["record1"] == record1 and f["record2"] == record2) or (f["record1"] == record2 and f["record2"] == record1):
                if (f["p1"] == p1 and f["p2"] == p2) or (f["p1"] == p2 and f["p2"] == p1):
                    return

    f = {}
    f["message"] = message
    f["record1"] = record1
    f["record2"] = record2
    f["p1"]      = p1
    f["p2"]      = p2
    findings.append(f)
    
    message = message + "\n"
    n1 = f'{record1["name"]}:{record1["class"]}'
    if "floor" in record1 and "ceiling" in record1:
        h1 = f'({record1["floor"]}-{record1["ceiling"]})'
    else:
        h1 = ""
    n2 = f'{record2["name"]}:{record2["class"]}'
    if "floor" in record2 and "ceiling" in record2:
        h2 = f'({record2["floor"]}-{record2["ceiling"]})'
    else:
        h2 = ""
    l1 = max(len(n1), len(n2))
    l2 = max(len(h1), len(h2))

    ll1 = common.strLatLon(p1)
    ll2 = common.strLatLon(p2)
    p1s = findLatLon(p1)
    p2s = findLatLon(p2)
    c1 = len(p1s)
    c2 = len(p2s)
    p1ss = []
    for element in p1s:
        if "lineno" in element:
            p1ss.append(element["lineno"])
    p2ss = []
    for element in p2s:
        if "lineno" in element:
            p2ss.append(element["lineno"])

    message = message + f'  {n1:{l1}} {h1:{l2}}: {ll1} ({c1}x: lineno {p1ss})' + "\n"
    message = message + f'  {n2:{l1}} {h2:{l2}}: {ll2} ({c2}x: lineno {p2ss})' + "\n"
    problem(2, message)
    
def findNearPoints(record_base, p1):
    global records
    global args
    for record in records:
        for element in record["elements"]:
            if element["type"] == "point":
                (distance_m, bearing) = common.geo_distance(p1[0], p1[1], element["location"][0], element["location"][1])
                distance_m = distance_m / 100        # convert cm to m
                if distance_m > 0 and distance_m < args.distance:
                    findingForTwoPoints(f'Airspaces with close points ({int(distance_m)}m):', record_base, record, p1, element["location"])
            if element["type"] == "arc" and not "radius" in element:
                # Only go for DB and not DA
                (distance_m, bearing) = common.geo_distance(p1[0], p1[1], element["start"][0], element["start"][1])
                distance_m = distance_m / 100        # convert cm to m
                if distance_m > 0 and distance_m < args.distance:
                    findingForTwoPoints(f'Airspaces with close points ({int(distance_m)}m):', record_base, record, p1, element["start"])
                (distance_m, bearing) = common.geo_distance(p1[0], p1[1], element["end"][0], element["end"][1])
                distance_m = distance_m / 100        # convert cm to m
                if distance_m > 0 and distance_m < args.distance:
                    findingForTwoPoints(f'Airspaces with close points ({int(distance_m)}m):', record_base, record, p1, element["end"])

def checkPoints(records):

    """
    Walk through all points and find other points which are close but not identical.
    """
    
    for record in records:
        #pprint(record)
        #print("Checking", record["name"])
        for element in record["elements"]:
            if element["type"] == "point":
                #pprint(element)
                findNearPoints(record, element["location"])
            if element["type"] == "arc":
                #pprint(element)
                if not "radius" in element:
                    findNearPoints(record, element["start"])
                    findNearPoints(record, element["end"])

def checkDB(records):

    """
    Walk through all DB entries and check if the radius of the first
    and last point are identical.
    """
    
    for record in records:
        for element in record["elements"]:
            if element["type"] == "arc":
                if not "radius" in element:
                    (dist1_cm, bearing) = common.geo_distance(element["center"][0],element["center"][1], element["start"][0], element["start"][1])
                    (dist2_cm, bearing) = common.geo_distance(element["center"][0],element["center"][1], element["end"][0], element["end"][1])
                    diff_m = abs(dist1_cm-dist2_cm)/100
                    if diff_m > 40:
                        if diff_m > 100:
                            prio = 1
                        else:
                            prio = 2
                        lineno = None
                        if "lineno" in element:
                            lineno = element["lineno"]
                        problem(prio, f'DB has a big difference radius between start and end of {diff_m:.0f}m', lineno)
                                
def getFirstPoint(element):
    if element["type"] == "point":
        return element["location"]
    if element["type"] == "arc":
        return element["start"]
    return None

def getLastPoint(element):
    if element["type"] == "point":
        return element["location"]
    if element["type"] == "arc":
        return element["end"]
    return None

def findOpenAirspaces(records):
    open_records = []
    
    for record in records:
        #pprint(record)
        #print("Checking", record["name"])
        firstElement = record["elements"][0]
        lastElement = record["elements"][-1]
        firstPoint = getFirstPoint(firstElement)
        lastPoint = getLastPoint(lastElement)
        if firstPoint != lastPoint:
            open_records.append(record)
    return open_records

def checkOpenAirspaces(records):

    """
    Walk through all records and check if they are closed.
    """
    
    records = findOpenAirspaces(records)
    for record in records:
        #pprint(record)
        #print("Checking", record["name"])
        firstElement = record["elements"][0]
        lastElement = record["elements"][-1]
        firstPoint = getFirstPoint(firstElement)
        lastPoint = getLastPoint(lastElement)
        if firstPoint != lastPoint:
            (gap_cm, bearing) = common.geo_distance(firstPoint[0], firstPoint[1], lastPoint[0], lastPoint[1])
            gap_km = gap_cm / 100000
            (name,dimension) = getAirspaceName(record)
            line_start = None
            if "lineno" in firstElement:
                line_start = firstElement["lineno"]
            problem(2, f'airspace "{name},{dimension}" is not closed with a gap of {gap_km:.1f}km.', line_start)

problem_count = [0, 0, 0]
prio_name = [ "fatal", "error", "warning" ]

def problem(prio, message, lineno = None):
    global problem_count, prio_name, args
    
    if lineno != None:
        in_line = f', line {lineno}'
    else:
        in_line = ""

    message = f'{prio_name[prio]}{in_line}: {message}'
    if args.ignore_errors != None and message in args.ignore_errors:
        return
    
    print_out = True
    if args.errors_only:
        if prio >= 2:
            print_out = False    
    if print_out:
        print(message)
        
    problem_count[prio] = problem_count[prio] + 1

def printProblemCounts():
    global problem_count, prio_name

    for prio in range(1,3):
        print(f'{problem_count[prio]} {prio_name[prio]}')

    return problem_count[1] > 0

def checkNameEncoding(records):

    """
    Walk through all records and check, if the name parameter is ASCII.
    """
    
    for record in records:
        if not record["name"].isascii():
            name = record["name"]
            lineno = None
            if "lineno" in record:
                lineno = record["lineno"]
            problem(1, f'Airspace name contains non-ascii characters: "{name}"', lineno)
  
def checkEncoding(fp):

    """
    Read in the file and search for non-ascii characters.
    """
    
    banner_printed = False
    lineno = 0
    for line in fp:
        line = line.strip()
        # print(line)
        lineno = lineno + 1
        if not line.isascii():
            if not banner_printed:
                banner_printed = True
                problem(2, "Use of non-ascii characters detected. Please switch to ASCII as some embedded devices do not have full character set.\nUsing 'iconv -f iso-8859-1 -t ascii//TRANSLIT' on the linux command line may help.")
            message = "Use of non-ascii characters detected.\n"
            message = message + line + "\n"
            for char in line:
                if char.isascii():
                    message = message + " "
                else:
                    message = message + "^"
            message = message + "\n"
            problem(2, message, lineno)

def checkInvalidPolygons(records):

    """
    Walk through all records and check if the polygon is valid.
    It is considered invalid, if https://shapely.readthedocs.io/en/stable/reference/shapely.Polygon.html#shapely.Polygon.is_valid is not true.
    """
    
    for record in records:
        if not record["polygon"].is_valid:
            problem(1, "Invalid Polygon for " + getAirspaceName2(record))

def checkHeightFL(height):
    fl = height[:2]
    if fl.upper() == "FL" and fl != "FL":
        return 2
    h = height[2:].strip()
    if h == "":
        return 1
    else:
        if h.isnumeric():
            fl = int(h)
            if int(fl / 5) * 5 != fl:
                return 2
    return 0

def checkHeightFT(height):
    m = re.match("(\d+)\s*(\w+)\s*(\w+)", height)
    if m:
        if not m.group(1).isdecimal():
            return 1
        h = int(m.group(1))
        if int(h/100)*100 != h:
            return 2
        unit = m.group(2).upper()
        if not unit in ["FT"]:
            return 1
        ref = m.group(3).upper()
        if ref == "MSL":
            return 2
        if not ref in ["AGL", "AMSL"]:
            return 1
        return 0
    return 1
    
def checkHeight(height):
    if height.upper() in ["GND", "SFC"]:
        return 0
    if height.upper().startswith("FL"):
        return checkHeightFL(height)
    if height[0].isdecimal():
        return checkHeightFT(height)
    
    return 1

def checkHeights(records):

    """
    Walk through all records and check all heights given for each airspace.
    A height must follow a convention to be valid.
    """
    
    for record in records:
        for h in ["floor", "ceiling"]:
            if h in record:
                prio = checkHeight(record[h])
                if prio > 0:
                    problem(prio, f'Incorrect height "{record[h]}" in {getAirspaceName2(record)}')
            else:
                problem(1, f'Missing height "{h}" in {getAirspaceName2(record)}')

                
def fixOpenAirspaces(fp, records):

    """
    Read in from the given file and write out a new file
    with all open airspaces closed. This fixes airspaces,
    where the first and the last point of the polygon are not the same.

    The filename of the new file is derived from args.filename by
    inserting the current date into the filename.
    """
    
    (root, ext) = os.path.splitext(args.filename)
    now_iso = datetime.now().isoformat(timespec='seconds')
    filename_fixed = f'{root}-{now_iso}{ext}'
    print(f'Fixing into {filename_fixed}')

    records = findOpenAirspaces(records)
    
    lineno = 0
    with open(filename_fixed, "w", newline='') as fp_f:
        for line in fp:
            fp_f.write(line)
            lineno = lineno + 1
            for record in records:
                lastElement = record["elements"][-1]
                if "lineno" in lastElement:
                    if lastElement["lineno"] == lineno:
                        firstElement = record["elements"][0]
                        firstPoint = getFirstPoint(firstElement)
                        firstPoint_latlon = common.strLatLon(firstPoint)
                        fp_f.write(f'DP {firstPoint_latlon}\n')
                        
records = []
findings = []

parser = argparse.ArgumentParser(description='Check OpenAir airspace file for consistency')
parser.add_argument("-e", "--errors-only", action="store_true",
                    help="Print only errors and no warnings")
parser.add_argument("-d", "--distance",
                    help="Specify the distance in meters to see two points as close",
                    type=int, default=100)
parser.add_argument("-i", "--ignore-errors",
                    help="Specify a error message, that is a false alert and should be ignored",
                    nargs='*')
parser.add_argument("-p", "--point", 
                    help="Find all other points near this point.")
parser.add_argument("-F", "--fix-closing", action="store_true",
                    help="Fix all open airspaces by inserting a closing point")
parser.add_argument("-n", "--no-arc", action="store_true",
                    help="Resolve arcs as straight line")
parser.add_argument("-f", "--fast-arc", action="store_true",
                    help="Resolve arcs with less quality (10 degree steps)")
parser.add_argument("filename")
args = parser.parse_args()
common.setArgs(args)

# read file into a StringIO, as we have to parse it multiple times
content = io.StringIO()
with open(args.filename, encoding='latin-1', newline='') as fp:
    content.write(fp.read())

content.seek(0, io.SEEK_SET)
reader = aerofiles.openair.Reader(content)

for record, error in reader:
    if error:
        raise error
    records.append(record)
    #pprint(record)

if args.point != None:
    args.pointLatLon = aerofiles.openair.reader.coordinate(args.point)
    record = {}
    record["name"] = "POINT " + common.strLatLon(args.pointLatLon)
    record["class"] = ""
    findNearPoints(record, args.pointLatLon)
    sys.exit(0)

content.seek(0, io.SEEK_SET)

if args.fix_closing:
    fixOpenAirspaces(content, records)
    sys.exit(0)

common.resolveRecordArcs(records)
common.createPolygons(records)

checkInvalidPolygons(records)
checkHeights(records)
checkDB(records)
checkEncoding(content)
checkOpenAirspaces(records)
checkNameEncoding(records)
checkCircles(records)
checkPoints(records)

ret = printProblemCounts()

sys.exit(ret)

