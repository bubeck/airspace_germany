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
from shapely.geometry import Polygon, LineString
from shapely.validation import explain_validity
import shapely
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

    n1 = common.getAirspaceName2(record1)
    n2 = common.getAirspaceName2(record2)
    h1 = ""
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
    common.problem(common.Prio.WARN, message)
    
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
                        if diff_m > 500:
                            prio = common.Prio.ERR
                        else:
                            prio = common.Prio.WARN
                        lineno = None
                        if "lineno" in element:
                            lineno = element["lineno"]
                        common.problem(prio, f'DB has a big difference radius between start and end of {diff_m:.0f}m', lineno)
                                
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
            (name,dimension) = common.getAirspaceName(record)
            line_start = None
            if "lineno" in firstElement:
                line_start = firstElement["lineno"]
            common.problem(common.Prio.WARN, f'airspace "{name},{dimension}" is not closed with a gap of {gap_km:.1f}km.', line_start)

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
            common.problem(common.Prio.ERR, f'Airspace name contains non-ascii characters: "{name}"', lineno)
  
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
                common.problem(common.Prio.WARN, "Use of non-ascii characters detected. Please switch to ASCII as some embedded devices do not have full character set.\nUsing 'iconv -f iso-8859-1 -t ascii//TRANSLIT' on the linux command line may help.")
            message = "Use of non-ascii characters detected.\n"
            message = message + line + "\n"
            for char in line:
                if char.isascii():
                    message = message + " "
                else:
                    message = message + "^"
            message = message + "\n"
            common.problem(common.Prio.WARN, message, lineno)

def isSelfIntersecting(polygon):
    
    for i in range(0, len(polygon.exterior.coords)-1):
        line1 = LineString([polygon.exterior.coords[i],
                           polygon.exterior.coords[i+1]])
        #print(line1)
        for j in range(i+1, len(polygon.exterior.coords)-1):
            line2 = LineString([polygon.exterior.coords[j],
                               polygon.exterior.coords[j+1]])
            if line1.crosses(line2):
                message = f'Illegal line crossing:\n'
                message += common.strLatLon(polygon.exterior.coords[i]) + " " + common.strLatLon(polygon.exterior.coords[i+1]) + "\n"
                message += common.strLatLon(polygon.exterior.coords[j]) + " " + common.strLatLon(polygon.exterior.coords[j+1])
                common.problem(common.Prio.WARN, message)
                return True
            
    return False
    
def checkInvalidPolygons(records):

    """
    Walk through all records and check if the polygon is valid.
    It is considered invalid, if https://shapely.readthedocs.io/en/stable/reference/shapely.Polygon.html#shapely.Polygon.is_valid is not true.
    """
    
    for record in records:
        #print("checkInvalidPolygon(",common.getAirspaceName2(record))
        # "is_valid" is a very fast check, that sometimes gives false positives
        if not record["polygon"].is_valid:
            #common.problem(common.Prio.ERR, "Invalid Polygon for " + common.getAirspaceName2(record) + ": " + explain_validity(record["polygon"]))
            # In that case do the slow check, to give only real problems:
            if isSelfIntersecting(record["polygon"]):
                common.problem(common.Prio.ERR, "Invalid (selfintersect) Polygon for " + common.getAirspaceName2(record) + ": " + explain_validity(record["polygon"]))

def iH(record1, record2):
    if record1["ceiling_ft"] > record2["floor_ft"] and record1["ceiling_ft"] < record2["ceiling_ft"]:
        return True
    if record1["floor_ft"] >= record2["floor_ft"] and record1["floor_ft"] < record2["ceiling_ft"]:
        return True
    if record1["floor_ft"] >= record2["floor_ft"] and record1["ceiling_ft"] < record2["ceiling_ft"]:
        return True
    return False

def intersectsInHeight(record1, record2):
    return iH(record1, record2) or iH(record2, record1)

def getOverlappingAirspaces(records):
    overlap = []
    num_records = len(records)
    for i in range(0, num_records):
        record1 = records[i]
        for j in range(i+1, num_records):
            record2 = records[j]
            if intersectsInHeight(record1, record2):
                if record1["polygon"].intersects(record2["polygon"]):
                    #print("Check Overlapping Airspaces " + common.getAirspaceName2(record1) + ", " + common.getAirspaceName2(record2))
                    intersection = shapely.intersection(record1["polygon"], record2["polygon"])
                    area = intersection.area
                    if area > 0:
                        overlap.append([record1, record2])

    return overlap

def checkOverlappingAirspaces(records):
    overlap = common.getOverlappingAirspaces(records)
    for record1,record2 in overlap:
        common.problem(common.Prio.ERR, "Overlapping Airspaces " + common.getAirspaceName2(record1) + ", " + common.getAirspaceName2(record2))

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
parser.add_argument("-o", "--check-overlap", action="store_true",
                    help="Check, if airspaces overlap")
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
common.checkHeights(records)

checkInvalidPolygons(records)
if args.check_overlap:
    checkOverlappingAirspaces(records)
checkDB(records)
checkEncoding(content)
checkOpenAirspaces(records)
checkNameEncoding(records)
checkCircles(records)
checkPoints(records)

ret = common.printProblemCounts()

sys.exit(ret)

