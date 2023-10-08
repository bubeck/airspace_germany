#!/usr/bin/python # -*- mode: python; python-indent-offset: 4 -*-

import argparse
import io

import aerofiles.openair

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_pdf import PdfPages

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
    
    #print("plot_to", pos)
    if last_pos != None:
        plot_line(plt, last_pos[1], last_pos[0], pos[1], pos[0], color)
    
    last_pos = pos
    if label and args.show_coords:
        plt.annotate(common.strLatLon(pos), (pos[1], pos[0]), color=color)

def plot_circle(plt, element, color="black"):
    center = element["center"]
    radius_km = common.nautical_miles_to_km(element["radius"])
    plot_arc_DA(plt, center, radius_km, 0, 180, True, True, color, False)
    plot_arc_DA(plt, center, radius_km, 180, 0, True, True, color, False)
    
def plot_arc_DA(plt, center, radius_km, start_angle, end_angle, clockwise, use_edge, color="black", label=True):
    global args

    if args.fast:
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
        (lat, lon) = common.geo_destination(center[0], center[1], angle, radius_km)
        # print(f'lat={lat} lon={lon}')
        plot_to(plt, [lat, lon], color, False)
        angle = angle + dir


def plot_arc(plt, center, start, end, clockwise, color="black", label=True):

    (dist_s, bearing_s) = common.geo_distance(center[0], center[1], start[0], start[1])
    (dist_e, bearing_e) = common.geo_distance(center[0], center[1], end[0], end[1])

    dist_s_km = (dist_s / 100) / 1000
    
    plot_to(plt, start, color, label)
    plot_arc_DA(plt, center, dist_s_km, bearing_s, bearing_e, clockwise, False, color, label)
    plot_to(plt, end, color, label)

ax = None
fig = None
zoom = 1

def plot(records):
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
    # plot_arc(plt, [0,0], [1,0], [0,1], True)

    if True:
        for record in records:
            plot_reset()
            color = cmap(color_pos)
            color_pos = (color_pos + 7) % color_num
            for element in record["elements"]:
                if element["type"] == "point":
                    plot_to(plt, element["location"], color)
                elif element["type"] == "arc":
                    if not args.no_arc:
                        if "radius" in element:
                            #pprint(element)
                            plot_arc_DA(plt, element["center"], common.nautical_miles_to_km(element["radius"]), element["start"], element["end"], element["clockwise"], True, color)
                        else:
                            plot_arc(plt, element["center"], element["start"], element["end"], element["clockwise"], color)
                    else:
                        plot_to(plt, element["start"], color)
                        plot_to(plt, element["end"], color)
                elif element["type"] == "circle":
                    plot_circle(plt, element, color)
                else:
                    print(f'Unknown element type: {element["type"]}')
                    sys.exit(1)
                    
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
    
parser = argparse.ArgumentParser(description='Plot OpenAir airspace file')
parser.add_argument("-n", "--no-arc", action="store_true",
                    help="Draw arcs as straight line")
parser.add_argument("-f", "--fast", action="store_true",
                    help="Draw arcs with less quality (10 degree steps)")
parser.add_argument("-c", "--show-coords", action="store_true",
                    help="Show latitude/longitude of points in plot")
parser.add_argument("filename")
args = parser.parse_args()

# read file into a StringIO, as we have to parse it multiple times
content = io.StringIO()
with open(args.filename, encoding='latin-1', newline='') as fp:
    content.write(fp.read())

content.seek(0, io.SEEK_SET)
reader = aerofiles.openair.Reader(content)

records = []
for record, error in reader:
    if error:
        raise error
    records.append(record)

plot(records)
    
