# airspace_germany
Airspace of Germany in OpenAir Format

This repository contains the airspace of Germany as published by the originl author under
https://www.daec.de/fachbereiche/luftraum-flugsicherheit-betrieb/luftraumdaten/

As this way of publication does not show any changes and does not allow for collaboration
I set up this repository to re-publish it for easy access to the open source community.

It gets automatically updated by a GitHub workflow once a day, so it should be always up to date.

## Verification of an airspace

Airspaces sometimes have minor tweaks, like similar coordinates instead of identical.
You can use http://xcglobe.com/airspace to look at them in detail and find improvements. In addition https://airspaces.bargen.dev/ is also helpful. It does not show arcs, therefore all rounded airspaces are rectangular. However, as most algorithm dealing with arcs have rounding errors, this can be sometimes also useful.

## Changes or Pull requests

If you want to provide any changes or fixes, you can either send them to the original author mentioned
in the airspace file or issue a pull request on this repository. I will try to forward your changes
to the author of the airspace file.



Hopefully, the author will use GitHub or something similar to publish the airspace on his own in the future, so that this repository is not necessary anymore.

