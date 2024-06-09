#!/usr/bin/python # -*- mode: python; python-indent-offset: 4 -*-

import argparse
import io

import aerofiles.openair

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import Polygon, LineString
from shapely.validation import explain_validity
import shapely
import sys

from icecream import ic

import common

def plot_p(plt, p, color="black"):
    plt.plot(p[1], p[0], '.', color=color)

def plot_line(plt, x1, y1, x2, y2, color="black"):
    x = [x1, x2]
    y = [y1, y2]
    plt.plot(x, y, color=color, alpha=1.0, linewidth=0.5)
    #print(f'plot_line(x1={x1}, y1={y1}, x2={x2}, y2={y2})')

last_pos = None

def plot_reset():
    global last_pos
    
    last_pos = None
    
def plot_to(plt, pos, color="black", label=True):
    global last_pos
    global args
    
    #print(f'plot_to({common.strLatLon(pos)}')
    if last_pos != None:
        plot_line(plt, last_pos[1], last_pos[0], pos[1], pos[0], color)
        #print(f'plot_to({common.strLatLon(last_pos)} -> {common.strLatLon(pos)}')
    last_pos = pos
    if label and args.show_coords:
        plt.annotate(common.strLatLon(pos), (pos[1], pos[0]), color=color)

ax = None
fig = None
zoom = 1

def plot_shapely(plt, shape):
    if isinstance(shape, shapely.Polygon):
        y,x = shape.exterior.xy
        plt.plot(x, y, color="red")
        plt.fill(x, y, alpha=0.5, color="red")
    elif isinstance(shape, shapely.LineString) or isinstance(shape, shapely.Point):
        y,x = shape.xy
        plt.plot(x, y, color="red")
    elif isinstance(shape, shapely.MultiPolygon) or isinstance(shape, shapely.GeometryCollection):
        for polygon in shape.geoms:
            plot_shapely(plt, polygon)
    else:
        print(type(shape))
    
def plot(records, overlap):
    global args
    global ax
    global fig

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    a, = plt.plot([], [])

    color_num = 30
    cmap = plt.cm.get_cmap('hsv', color_num)
    color_pos = 25

    plot_reset()

    if args.intersects:
        for r1,r2 in overlap:
            intersection = shapely.intersection(r1["polygon"], r2["polygon"])
            # 1 degree is approx. 110km.
            # We define a maximum area for intersection. If bigger, then ignore
            area_max = 1/110 * 1/110
            if intersection.area < area_max:
                plot_shapely(plt, intersection)
            continue
        
            if isinstance(intersection, shapely.MultiPolygon) or isinstance(intersection, shapely.GeometryCollection):
                for polygon in intersection.geoms:
                    x,y = polygon.exterior.xy
                    plt.plot(x, y, color="red")
                    plt.fill(x, y, alpha=0.5, color="red")
            elif isinstance(intersection, shapely.LineString):
                plt.plot(*intersection.xy)
            else:
                x,y = intersection.exterior.xy
                plt.plot(x, y, color="red")
                plt.fill(x, y, alpha=0.5, color="red")
                    
    if True:
        for record in records:
            plot_reset()
            if args.intersects:
                color = "black"
                for r1,r2 in overlap:
                    if record == r1 or record == r2:
                        color = "blue"
                        break
            else:
                color = cmap(color_pos)
                color_pos = (color_pos + 7) % color_num

            if "color" in record:
                color = record["color"]

            first_pos = None
            for element in record["elements_resolved"]:
                if element["type"] == "point":
                    if first_pos == None:
                        first_pos = element["location"]
                    label = not ("computed" in element and element["computed"] == True)
                    plot_to(plt, element["location"], color, label)
                else:
                    print(f'Unknown element type: {element["type"]}')
                    sys.exit(1)

            if last_pos != first_pos:
                plot_to(plt, first_pos, color, False)
                
    plt.title("Airspace")
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    ax.axis('equal')
    
    plt.subplots_adjust(left=0.05, right=1.0, top=1.0, bottom=0.05)

    fig.canvas.mpl_connect('button_press_event', on_press)
    #fig.canvas.mpl_connect('pick_event', on_press)

    #with PdfPages('test.pdf') as pdf:
    #    pdf.savefig()

    plt.savefig("test.pdf")
    plt.savefig("test.svg", bbox_inches="tight")
    
    # ax.margins(x=8.877760411607648,y=48.773972056413555)
    plt.show()

def on_press(event):
    global ax, fig, zoom

    if event.button == MouseButton.LEFT:
        zoom = zoom / 2
    if event.button == MouseButton.MIDDLE or event.button == MouseButton.RIGHT:
        zoom = zoom * 2
    x,y = event.xdata, event.ydata

    lat_lon = common.strLatLon([y,x])
    
    print(f'Zooming to {y},{x} = {lat_lon}')

    ax.set_xlim(x-zoom, x+zoom)
    ax.set_ylim(y-zoom, y+zoom)
    fig.canvas.draw()

def airspace_readfile(filename):
    global args

    print("Reading openair file", filename)
    # read file into a StringIO, as we have to parse it multiple times
    content = io.StringIO()
    with open(filename, encoding='latin-1', newline='') as fp:
        content.write(fp.read())

    content.seek(0, io.SEEK_SET)
    reader = aerofiles.openair.Reader(content)

    records = []
    for record, error in reader:
        if error:
            raise error
        if args.only:
            if common.getAirspaceName2(record) in args.only:
                records.append(record)
        else:
            records.append(record)

    common.resolveRecordArcs(records)
    common.createPolygons(records)
    common.checkHeights(records)
    return records

def airspace_find_pt(record, element_searched):
    for element in record["elements_resolved"]:
        if element["type"] == "point":
            computed = ("computed" in element and element["computed"] == True)
            if computed:
                continue
            loc1 = element["location"]
            loc2 = element_searched["location"]
            if loc1[0] == loc2[0] and loc1[1] == loc2[1]:
                return element
    return None

# How similar is record2 to record1?
# 0-100%
def airspace_similar(record1, record2):
    identical = 0
    different = 0
    if record1["name"] != record2["name"]:
        return 0
    if record1["class"] != record2["class"]:
        return 0
    e1_count = 0
    e2_count = 0
    for e1 in record1["elements_resolved"]:
        computed = ("computed" in e1 and e1["computed"] == True)
        if computed:
            continue
        e1_count = e1_count + 1
        e2 = airspace_find_pt(record2, e1)
        if e2 == None:
            different = different + 1
        else:
            identical = identical + 1
    for e2 in record2["elements_resolved"]:
        computed = ("computed" in e2 and e2["computed"] == True)
        if computed:
            continue
        e2_count = e2_count + 1
        e1 = airspace_find_pt(record1, e1)
        if e2 == None:
            different = different + 1
        else:
            identical = identical + 1
    if e1_count+e2_count == 0:
        return 0          # Empty airspaces are always different
    ic(e1_count, e2_count, identical)
    return 100*identical/(e1_count+e2_count)

def airspace_find_similar(record1, records2):
    best_simular = 0
    best_simular_r2 = None
    for record2 in records2:
        simular = airspace_similar(record1, record2)
        if simular > best_simular:
            best_simular = simular
            best_simular_r2 = record2
    return (best_simular, best_simular_r2)

#matplotlib.use('Qt5Agg')
#matplotlib.use('Gtk4Agg')
matplotlib.use('TkAgg')

parser = argparse.ArgumentParser(description='Plot OpenAir airspace file')
parser.add_argument("-e", "--errors-only", action="store_true",
                    help="Print only errors and no warnings")
parser.add_argument("-n", "--no-arc", action="store_true",
                    help="Resolve arcs as straight line")
parser.add_argument("-f", "--fast-arc", action="store_true",
                    help="Resolve arcs with less quality (10 degree steps)")
parser.add_argument("-c", "--show-coords", action="store_true",
                    help="Show latitude/longitude of points in plot")
parser.add_argument("-o", "--only", action="append",
                    help="Show only given airspace")
parser.add_argument("-i", "--intersects", action="store_true",
                    help="Show intersection between airspaces")
parser.add_argument("-d", "--diff",
                    help="Show difference to the given airspace file")
parser.add_argument("filename")
args = parser.parse_args()
common.setArgs(args)

overlap = []

records = airspace_readfile(args.filename)
if args.diff:
    records_1 = airspace_readfile(args.diff)
    ic(len(records_1), len(records))
    identical = []
    deleted = []
    added = []
    for record1 in records_1:
        asn = common.getAirspaceName2(record1)
        breakpoint()
        (best_simular, best_simular_r) = airspace_find_similar(record1, records)
        if best_simular == 100:
            # They are identical
            identical.append(record1)
            best_simular_r["color"] = "grey"
        elif best_simular > 50:
            # They are similar but changed
            best_simular_r["color"] = "orange"
            record1["color"] = "blue"
            records.append(record1)
            if False:
                try:
                    print("overlap", asn)
                    intersection = shapely.intersection(record1["polygon"], record2["polygon"])
                    area = intersection.area
                    if area > 0:
                        overlap.append([record1, record2])
                except shapely.errors.GEOSException as e:
                    problem(Prio.ERR, "Invalid Overlapping Airspaces " + getAirspaceName2(record1) + ", " + getAirspaceName2(record2), e)
        else:
            # Removed
            record1["color"] = "red"
            records.append(record1)

    for record2 in records:
        asn = common.getAirspaceName2(record2)
        (best_simular, best_simular_r) = airspace_find_similar(record2, records_1)
        if best_simular < 50:
            # New entry
            record2["color"] = "green"
            records.append(record1)
    #sys.exit(0)
    
if args.intersects:
    overlap = common.getOverlappingAirspaces(records)
    
plot(records, overlap)
    
