# -*- mode: python; python-indent-offset: 4 -*-
#
# This module contains all the common functions needed by the other
# python scripts in this directory.
#
# 2023-10-15: tilmann@bubecks.de
#

import math
from pprint import pprint
from shapely.geometry import Polygon, LineString
from shapely.validation import explain_validity
import shapely
import sys
from enum import Enum
import re
from icecream import ic

args = None

def LINE():
    return sys._getframe(1).f_lineno

#
# Set the global command line argument into this namespace, so
# that functions defined here, are able to access them.
#
# @param globalArgs the result from argparse
#
def setArgs(globalArgs):
    global args

    args = globalArgs

class Prio(Enum):
    OK = 0
    ERR = 1
    WARN = 2

problem_count = [0, 0, 0]

def problem(prio, message, lineno = None):
    global problem_count, prio_name, args
    
    if lineno != None:
        in_line = f', line {lineno}'
    else:
        in_line = ""

    message = f'{prio.name}{in_line}: {message}'
    
    if "ignore_errors" in args and args.ignore_errors != None and message in args.ignore_errors:
        return
    
    print_out = True
    if "errors_only" in args and args.errors_only:
        if prio.value >= Prio.WARN.value:
            print_out = False    
    if print_out:
        print(message)
        
    problem_count[prio.value] = problem_count[prio.value] + 1

def printProblemCounts():
    global problem_count, prio_name

    for prio in Prio:
        print(f'{problem_count[prio.value]} {prio.name}')

    return problem_count[prio.ERR.value] > 0

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
                    try:
                        intersection = shapely.intersection(record1["polygon"], record2["polygon"])
                        area = intersection.area
                        if area > 0:
                            overlap.append([record1, record2])
                    except shapely.errors.GEOSException as e:
                        problem(Prio.ERR, "Invalid Overlapping Airspaces " + getAirspaceName2(record1) + ", " + getAirspaceName2(record2), e)


    return overlap

def checkHeightFL(record, h):
    prio = Prio.OK
    
    height = record[h]
    unit = height[:2]
    if unit.upper() == "FL" and unit != "FL":   # FL is not spelled as FL
        if prio.value < Prio.WARN.value:
            prio = Prio.WARN
    fl = height[2:].strip()
    if fl == "":
        if prio.value < Prio.ERR.value:
            prio = Prio.ERR
    else:
        if fl.isnumeric():
            fl = int(fl)
            if int(fl / 5) * 5 != fl:
                if prio.value < Prio.WARN.value:
                    prio = Prio.WARN
            record[h + "_ft"] = fl * 100
    return prio

def checkHeightFT(record, h):
    prio = Prio.OK

    height = record[h]
    m = re.match(r"(\d+)\s*(\w+)\s*(\w+)", height)
    if m:
        if not m.group(1).isdecimal():
            return Prio.ERR
        height = int(m.group(1))
        if int(height/100)*100 != height:
            if prio.value < Prio.WARN.value:
                prio = Prio.WARN
        unit = m.group(2).upper()
        if not unit in ["FT", "M"]:
            return Prio.ERR
        if unit == "M":
            record[h + "_ft"] = height * 3.28084     # m to feet
        else:
            record[h + "_ft"] = height
        ref = m.group(3).upper()
        if ref in ["MSL", "GND", "SFC"]:
            if prio.value < Prio.WARN.value:
                prio = Prio.WARN
        elif not ref in ["AGL", "AMSL"]:
            return Prio.ERR
        return prio

    return Prio.ERR
    
def checkHeight(record, h):
    #ic(record["name"], h)
    height = record[h].strip()
    if height.upper() in ["GND", "SFC"]:
        record[h + "_ft"] = 0
        return Prio.OK
    if height.upper().startswith("FL"):
        return checkHeightFL(record, h)
    if height[0].isdecimal():
        return checkHeightFT(record, h)
    
    return Prio.ERR

def checkHeights(records):

    """
    Walk through all records and check all heights given for each airspace.
    A height must follow a convention to be valid.
    """
    
    for record in records:
        for h in ["floor", "ceiling"]:
            if h in record:
                prio = checkHeight(record, h)
                if prio.value > Prio.OK.value:
                    problem(prio, f'Height "{record[h]}" in {getAirspaceName2(record)}')
            else:
                problem(Prio.ERR, f'Missing height "{h}" in {getAirspaceName2(record)}')

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

# Converter function to convert nautical miles to km
#
# @param nm nautical miles
#
# @return corresponding value in km
def nautical_miles_to_km(nm):
    return nm * 1.852

def geo_destination(lat1, lon1, angle, distance_km):
    angle = math.radians(angle);
    dx = math.sin(angle) * distance_km;
    dy = math.cos(angle) * distance_km;
    
    (kx, ky) = get_kx_ky(lat1)
    
    lon2 = lon1 + dx / kx;
    lat2 = lat1 + dy / ky;
    
    return (lat2, lon2)

 # Compute the distance between two GPS points in 2 dimensions
 # (without altitude). Latitude and longitude parameters must be given
 # as fixed integers multiplied with GPS_COORD_MULT.
 #
 # \param lat1 the latitude of the 1st GPS point
 # \param lon1 the longitude of the 1st GPS point
 # \param lat2 the latitude of the 2nd GPS point
 # \param lon2 the longitude of the 2nd GPS point
 # \param FAI use FAI sphere instead of WGS ellipsoid
 # \param bearing pointer to bearing (NULL if not used)
 #
 # \return the distance in cm.
 #/
def geo_distance(lat1, lon1, lat2, lon2):
    d_lon = (lon2 - lon1)
    d_lat = (lat2 - lat1)

    #	DEBUG("#d_lon=%0.10f\n", d_lon);
    #	DEBUG("#d_lat=%0.10f\n", d_lat);
    
    #	DEBUG("lat1=%li\n", lat1);
    #	DEBUG("lon1=%li\n", lon1);
    #	DEBUG("lat2=%li\n", lat2);
    #	DEBUG("lon2=%li\n", lon2);

    # WGS
    # DEBUG("f=0\n");
    # DEBUG("#lat=%0.10f\n", (lat1 + lat2) / ((float)GPS_COORD_MUL * 2));
    
    (kx, ky) = get_kx_ky((lat1 + lat2) / 2)
    
    # DEBUG("#kx=%0.10f\n", kx);
    # DEBUG("#ky=%0.10f\n", ky);

    d_lon = d_lon * kx
    d_lat = d_lat * ky

    # DEBUG("#d_lon=%0.10f\n", d_lon);
    # DEBUG("#d_lat=%0.10f\n", d_lat);

    dist = math.sqrt(math.pow(d_lon, 2) + math.pow(d_lat, 2)) * 100000.0

    if d_lon == 0 and d_lat == 0:
        bearing = 0
    else:
        bearing = (math.degrees(math.atan2(d_lon, d_lat)) + 360) % 360
        # DEBUG("a=%d\n", *bearing);

    # DEBUG("d=%lu\n\n", dist);

    return (dist, bearing)

def get_kx_ky(lat):
    fcos = math.cos(math.radians(lat))
    cos2 = 2. * fcos * fcos - 1.
    cos3 = 2. * fcos * cos2 - fcos
    cos4 = 2. * fcos * cos3 - cos2
    cos5 = 2. * fcos * cos4 - cos3
    # multipliers for converting longitude and latitude
    # degrees into distance (http://1.usa.gov/1Wb1bv7)
    kx = (111.41513 * fcos - 0.09455 * cos3 + 0.00012 * cos5)
    ky = (111.13209 - 0.56605 * cos2 + 0.0012 * cos4)
    return (kx, ky)

def decimal_degrees_to_dms(decimal_degrees):
    #mnt,sec = divmod(decimal_degrees*3600,60)
    #deg,mnt = divmod(mnt, 60)
    #return (round(deg),round(mnt),round(sec))
    
    #decimals, number = math.modf(decimal_degrees)
    #deg = int(number)
    #mnt = round(decimals * 60)
    #sec = (decimal_degrees - deg - mnt / 60) * 3600.00
    # return deg,mnt,round(sec)

    decimals, number = math.modf(decimal_degrees)
    deg = int(number)
    mnt = int(decimals * 60)
    sec = round((decimal_degrees - deg - mnt / 60) * 3600.00)
    if sec == 60:
        sec = 0
        mnt += 1
        if mnt == 60:
            mnt = 0
            deg += 1
    return deg, mnt, sec

def strDegree(v, width):
    (degrees,minutes,seconds) = decimal_degrees_to_dms(abs(v))
    return f'{degrees:0{width}d}:{minutes:02d}:{seconds:02d}'
    
def strLatLon(P):
    result = strDegree(abs(P[0]), 2) + " "
    if P[0] >= 0:
        result = result + "N "
    else:
        result = result + "S "

    result = result + strDegree(abs(P[1]), 3) + " "
    if P[1] >= 0:
        result = result + "E "
    else:
        result = result + "W "
    return result

def resolveRecordArcs(records):
    for record in records:
        resolveArcs(record)
        
def resolveArcs(record):
    global args

    elements_resolved = []
    for element in record["elements"]:
        if element["type"] == "point":
            element["computed"] = False
            elements_resolved.append(element)
            #print(f'resolve(point, {strLatLon(element["location"])}')
        elif element["type"] == "arc":
            if not args.no_arc:
                if "radius" in element:
                    elements_resolved.extend(resolve_DA(element["center"], nautical_miles_to_km(element["radius"]), element["start"], element["end"], element["clockwise"], True))
                else:
                    elements_resolved.extend(resolve_DB(element["center"], element["start"], element["end"], element["clockwise"]))
            else:
                #ic(element)
                elements_resolved.append(createElementPoint(element["start"][0], element["start"][1]))
                elements_resolved.append(createElementPoint(element["end"][0], element["end"][1]))
        elif element["type"] == "circle":
            elements_resolved.extend(resolve_circle(element))
        else:
            print(f'Unknown element type: {element["type"]}')
            sys.exit(1)

    record["elements_resolved"] = elements_resolved
    return elements_resolved
                                         
def createElementPoint(lat, lon):
    element = {}
    element["type"] = "point"
    element["location"] = [ lat, lon ]
    return element

def resolve_DA(center, radius_km, start_angle, end_angle, clockwise, use_edge):
    global args
    elements = []

    if clockwise:
        reverse = False
    else:
        reverse = True
        clockwise = True
        tmp = start_angle
        start_angle = end_angle
        end_angle = tmp
        
    if args.fast_arc:
        dir = 10
    else:
        dir = 1
        
    if clockwise:
        while start_angle > end_angle:
            end_angle = end_angle + 360
    else:
        dir = -dir
        while start_angle < end_angle:
            start_angle = start_angle + 360
        
    #print("start_angle:", start_angle)
    #print("end_angle:", end_angle)
    #print("clockwise:", clockwise)

    if not use_edge:
        start_angle = start_angle + dir
        end_angle = end_angle - dir
        
    angle = start_angle
    
    while True:
        # print("loop angle:", angle)
        if clockwise:
            if angle >= end_angle:
                angle = end_angle
                break
        else:
            if angle <= end_angle:
                angle = end_angle
                break
        (lat, lon) = geo_destination(center[0], center[1], angle, radius_km)
        # print(f'lat={lat} lon={lon}')
        element = createElementPoint(lat,lon)
        element["computed"] = True
        elements.append(element)
        angle = angle + dir

    if reverse:
        elements.reverse()
        
    return elements

def resolve_circle(element):
    center = element["center"]
    radius_km = nautical_miles_to_km(element["radius"])
    elements = resolve_DA(center, radius_km, 0, 180, True, True)
    elements.extend(resolve_DA(center, radius_km, 180, 0, True, True))
    return elements

def resolve_DB(center, start, end, clockwise):

    (dist_s, bearing_s) = geo_distance(center[0], center[1], start[0], start[1])
    (dist_e, bearing_e) = geo_distance(center[0], center[1], end[0], end[1])

    dist_s_km = (dist_s / 100) / 1000
    
    elements = resolve_DA(center, dist_s_km, bearing_s, bearing_e, clockwise, False)
    element = createElementPoint(start[0], start[1])
    element["computed"] = False
    elements.insert(0, element)
    element = createElementPoint(end[0], end[1])
    element["computed"] = False
    elements.append(element)

    return elements


def createPolygons(records):
    for record in records:
        createPolygonOfRecord(record)
        
def createPolygonOfRecord(record):
    points = []

    for element in record["elements_resolved"]:
        points.append(element["location"])
    #ic(record)
    if len(points) < 3:
        return
    record["polygon"] = Polygon(points)
    if not record["polygon"].is_valid:
        print("ERR", getAirspaceName2(record), "is not valid")
        #sys.exit(1)

def find_airspace(records, name):
    for record in records:
        if getAirspaceName2(record) == name:
            return record
    return None
