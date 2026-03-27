#!/usr/bin/python # -*- mode: python; python-indent-offset: 4 -*-

import argparse
import io

import aerofiles.openair

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import Polygon, LineString, Point
from shapely.validation import explain_validity
import shapely
import sys

from icecream import ic

import common
mousex = None
mousey = None
mousez = 0


def plot_p(plt, p, color="black"):
    plt.plot(p[1], p[0], '.', color=color)


def plot_line(plt, x1, y1, x2, y2, color="black", linewidth=0.5):
    x = [x1, x2]
    y = [y1, y2]
    line, = plt.plot(x, y, color=color, alpha=1.0, linewidth=linewidth)
    # print(f'plot_line(x1={x1}, y1={y1}, x2={x2}, y2={y2})')
    return line


last_pos = None
plot_records = []


def plot_reset():
    global last_pos

    last_pos = None


def plot_to(plt, pos, color="black", label=True, linewidth=0.5):
    global last_pos
    global args
    line = None

    # print(f'plot_to({common.strLatLon(pos)}')
    if last_pos != None:
        line = plot_line(
            plt, last_pos[1], last_pos[0], pos[1], pos[0], color, linewidth)
        # print(f'plot_to({common.strLatLon(last_pos)} -> {common.strLatLon(pos)}')
    last_pos = pos
    if label and args.show_coords:
        plt.annotate(common.strLatLon(pos), (pos[1], pos[0]), color=color)
    return line


ax = None
fig = None
zoom = 1


def plot_shapely(plt, shape):
    if isinstance(shape, shapely.Polygon):
        y, x = shape.exterior.xy
        plt.plot(x, y, color="red")
        plt.fill(x, y, alpha=0.5, color="red")
    elif isinstance(shape, shapely.LineString) or isinstance(shape, shapely.Point):
        y, x = shape.xy
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
    global plot_records

    plot_records = records

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    a, = plt.plot([], [])

    color_num = 30
    cmap = plt.cm.get_cmap('hsv', color_num)
    color_pos = 25

    plot_reset()

    if args.intersects:
        for r1, r2 in overlap:
            intersection = shapely.intersection(r1["polygon"], r2["polygon"])
            # 1 degree is approx. 110km.
            # We define a maximum area for intersection. If bigger, then ignore
            area_max = 1/110 * 1/110
            if intersection.area < area_max:
                plot_shapely(plt, intersection)
            continue

            if isinstance(intersection, shapely.MultiPolygon) or isinstance(intersection, shapely.GeometryCollection):
                for polygon in intersection.geoms:
                    x, y = polygon.exterior.xy
                    plt.plot(x, y, color="red")
                    plt.fill(x, y, alpha=0.5, color="red")
            elif isinstance(intersection, shapely.LineString):
                plt.plot(*intersection.xy)
            else:
                x, y = intersection.exterior.xy
                plt.plot(x, y, color="red")
                plt.fill(x, y, alpha=0.5, color="red")

    if True:
        for record in records:
            plot_reset()
            if args.intersects:
                color = "black"
                for r1, r2 in overlap:
                    if record == r1 or record == r2:
                        color = "blue"
                        break
            else:
                color = cmap(color_pos)
                color_pos = (color_pos + 7) % color_num

            if "color" in record:
                color = record["color"]
            linewidth = 0.5
            if "selected" in record:
                if record["selected"]:
                    print("SELECTED")
                    linewidth = 4

            first_pos = None
            lines = []
            for element in record["elements_resolved"]:
                if element["type"] == "point":
                    if first_pos == None:
                        first_pos = element["location"]
                    label = not (
                        "computed" in element and element["computed"] == True)
                    line = plot_to(
                        plt, element["location"], color, label, linewidth)
                    if line != None:
                        lines.append(line)
                else:
                    print(f'Unknown element type: {element["type"]}')
                    sys.exit(1)

            if last_pos != first_pos:
                line = plot_to(plt, first_pos, color, False, linewidth)
                if line != None:
                    lines.append(line)
            record["lines"] = lines

    if last_pos != None:
        (dx, _) = common.geo_distance(
            last_pos[1], last_pos[0], last_pos[1] + 1, last_pos[0] + 0)
        (dy, _) = common.geo_distance(
            last_pos[1], last_pos[0], last_pos[1] + 0, last_pos[0] + 1)
        # ic(dx, dy, dx/dy)
        ratio = dy / dx
        ratio = 1.33
        ax.set_aspect(ratio, adjustable="datalim")

    plt.title("Airspace")
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')

    plt.subplots_adjust(left=0.05, right=1.0, top=1.0, bottom=0.05)
    # plt.gca().set_aspect('equal')  # Seitenverhältnis 1:1
    # ax.axis('equal')

    fig.canvas.mpl_connect('button_press_event', on_press)
    # fig.canvas.mpl_connect('pick_event', on_press)
    fig.canvas.mpl_connect('key_press_event', on_keypress)
    fig.canvas.mpl_connect('motion_notify_event', on_move)
    fig.canvas.manager.set_window_title("+".join(args.filename))

    # with PdfPages('test.pdf') as pdf:
    #    pdf.savefig()

    plt.savefig("test.pdf")
    plt.savefig("test.svg", bbox_inches="tight")

    # ax.margins(x=8.877760411607648,y=48.773972056413555)
    plt.show()


def find_under(latLon):

    print(f'Searching for {latLon}')

    r = []
    has_ft = True
    point = Point(latLon[0], latLon[1])
    for record in plot_records:
        if "polygon" in record:
            if record["polygon"].contains(point):
                r.append(record)
                if not "floor_ft" in record:
                    has_ft = False

    if has_ft:
        r.sort(reverse=False, key=lambda x: x["floor_ft"])
    return r


def print_under(latLon):
    r = find_under(latLon)
    for record in r:
        print(common.getAirspaceName2(record))


def on_move(event):
    global mousex, mousey
    if event.inaxes:  # Nur reagieren, wenn Maus im Plotbereich ist
        x, y = event.xdata, event.ydata
        mousex = x
        mousey = y


def on_press(event):
    global ax, fig, zoom
    global mousex, mousey

    x, y = event.xdata, event.ydata
    # mousex = x
    # mousey = y

    if event.button == MouseButton.LEFT:
        zoom = zoom / 2
    if event.button == MouseButton.RIGHT:
        zoom = zoom * 2
    if event.button == MouseButton.MIDDLE:
        print_under([y, x])

    lat_lon = common.strLatLon([y, x])

    print(f'Zooming to {y},{x} = {lat_lon}')

    ax.set_xlim(x-zoom, x+zoom)
    ax.set_ylim(y-zoom, y+zoom)

    fig.canvas.draw()


def set_linewidth(record, linewidth):
    for line in record["lines"]:
        line.set_linewidth(linewidth)


def on_keypress(event):
    global mousex, mousey, mousez

    r = find_under([mousey, mousex])
    for record in plot_records:
        record["selected"] = False
        set_linewidth(record, 0.5)

    if event.key == 'x':
        print_under([mousey, mousex])
    elif event.key == 'down':
        mousez -= 1
    elif event.key == 'up':
        mousez += 1

    if mousez < 0:
        mousez = 0
    if mousez >= len(r):
        mousez = len(r) - 1

    record = r[mousez]
    record["selected"] = True

    i = len(r)
    for record in reversed(r):
        if record["selected"]:
            print(f'[{i}] * {common.getAirspaceName2(record)}')
            set_linewidth(record, 4)
        else:
            print(f'[{i}]   {common.getAirspaceName2(record)}')
            set_linewidth(record, 0.5)
        i -= 1

    plt.draw()


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
                # print("Read ", common.getAirspaceName2(record))
                records.append(record)
        else:
            print(f'Read "{common.getAirspaceName2(record)}"')
            records.append(record)

    common.resolveRecordArcs(records)
    common.createPolygons(records)
    common.checkHeights(records)
    # records = airspace_find_low(records)
    return records


def airspace_find_low(records):
    r2 = []
    for r in records:
        # if "polygon" in r:
        #    print(r["polygon"].area, r["name"])
        if r["floor_ft"] < 10000:
            r2.append(r)
    return r2


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


def jaccard_similarity(poly1, poly2):
    intersection = poly1.intersection(poly2).area
    union = poly1.union(poly2).area
    return intersection / union if union > 0 else 0

# How similar is record2 to record1?
# 0-100%


def airspace_similar_shapely(record1, record2):
    p1 = record1["polygon"]
    p2 = record2["polygon"]
    if not p1.is_valid:
        # print("Ignoring", common.getAirspaceName2(record1), "because invalid")
        return 0
    if not p2.is_valid:
        # print("Ignoring", common.getAirspaceName2(record2), "because invalid")
        return 0

    if p1.equals(p2):
        return 100
    else:
        jaccard = jaccard_similarity(p1, p2)
        return jaccard * 100

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
        simular = airspace_similar_shapely(record1, record2)
        if simular > best_simular:
            best_simular = simular
            best_simular_r2 = record2
    return (best_simular, best_simular_r2)


# matplotlib.use('Qt5Agg')
# matplotlib.use('Gtk4Agg')
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
parser.add_argument("filename", nargs="+",
                    help="One or more openair filenames")
args = parser.parse_args()
common.setArgs(args)

overlap = []
records = []
for filename in args.filename:
    records.extend(airspace_readfile(filename))

if args.diff:
    records_1 = airspace_readfile(args.diff)
    ic(len(records_1), len(records))
    identical = []
    deleted = []
    added = []
    for record1 in records_1:
        asn = common.getAirspaceName2(record1)
        # breakpoint()
        (best_simular, best_simular_r) = airspace_find_similar(record1, records)
        if best_simular == 100:
            # They are identical
            # ic(common.getAirspaceName2(record1), common.getAirspaceName2(best_simular_r))
            identical.append(record1)
            best_simular_r["color"] = "grey"
        elif best_simular > 90:
            # They are similar but changed
            best_simular_r["color"] = "orange"
            record1["color"] = "blue"
            records.append(record1)
            if False:
                try:
                    print("overlap", asn)
                    intersection = shapely.intersection(
                        record1["polygon"], record2["polygon"])
                    area = intersection.area
                    if area > 0:
                        overlap.append([record1, record2])
                except shapely.errors.GEOSException as e:
                    problem(Prio.ERR, "Invalid Overlapping Airspaces " +
                            getAirspaceName2(record1) + ", " + getAirspaceName2(record2), e)
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
    # sys.exit(0)

if args.intersects:
    overlap = common.getOverlappingAirspaces(records)

plot(records, overlap)
