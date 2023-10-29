# airspace_germany
Airspace of Germany in OpenAir Format

This repository contains the airspace of Germany as published by the originl author under
https://www.daec.de/fachbereiche/luftraum-flugsicherheit-betrieb/luftraumdaten/

As this way of publication does not show any changes and does not allow for collaboration
I set up this repository to re-publish it for easy access to the open source community.

It gets automatically updated by a GitHub workflow once a day, so it should be always up to date.

## Verification of airspaces

Airspaces sometimes have errors or minor tweaks, like similar
coordinates instead of identical. You can use
[check-consistency.py](bin/check-consistency.py) to check an
airspace. Use `check-consistency.py --help` for help.

## Visual control of airspaces

You can use [visualize.py](bin/visualize.py) to visualize an
airspace. Use `visualize.py --help` for help.

You can also use http://xcglobe.com/airspace to look at them in detail and find improvements. In addition https://airspaces.bargen.dev/ is also helpful. It does not show arcs, therefore all rounded airspaces are rectangular. However, as most algorithm dealing with arcs have rounding errors, this can be sometimes also useful.

Also https://www.openaip.net/map is based on the official german openair file. This page can be used to zoom into the map and read the coordinates of points in question. However, it is not possible to upload own OpenAir files.

## Changes or Pull requests

If you want to provide any changes or fixes, you can either send them to the original author mentioned
in the airspace file or issue a pull request on this repository. I will try to forward your changes
to the author of the airspace file.

Hopefully, the author will use GitHub or something similar to publish the airspace on his own in the future, so that this repository is not necessary anymore.

## Correctness of airspace

There is a GitHub Action `check.yml`, that automatically checks the
airspace file for errors whenever the airspace changes. Here is the
status of the current available airspace file in regards to this
check.  Even if there are errors, the airspace file is still helpful,
because most applications using the file are able to handle those
problems.

![example workflow](https://github.com/bubeck/airspace_germany/actions/workflows/check.yml/badge.svg)

